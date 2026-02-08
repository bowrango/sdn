#!/usr/bin/env python

"""Standalone Performance Monitor for ECE50863 Network
Passively monitors Controller.log and switch*.log to measure
bandwidth (message rates) and propagation delay.

Usage: python perf.py <config_file> [--interval 10]

Author: Matt Bowring
Email: mbowring@purdue.edu
"""

import sys
import os
import struct
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from common import (
    LOCALHOST,
    BIN_REGISTER_REQUEST, BIN_REGISTER_RESPONSE,
    BIN_ROUTING_UPDATE, BIN_KEEP_ALIVE, BIN_TOPOLOGY_UPDATE,
)

PERF_LOG_FILE = "Performance.log"

# Per-message sizes derived from common.py struct format strings
MSG_SIZE_FIXED = {
    BIN_REGISTER_REQUEST: struct.calcsize('!Bii'),
    BIN_KEEP_ALIVE: struct.calcsize('!Bi'),
}
MSG_SIZE_HEADER = {
    BIN_REGISTER_RESPONSE: struct.calcsize('!BH'),
    BIN_ROUTING_UPDATE: struct.calcsize('!BH'),
    BIN_TOPOLOGY_UPDATE: struct.calcsize('!BiH'),
}
MSG_SIZE_PER_ITEM = {
    BIN_REGISTER_RESPONSE: struct.calcsize('!iBi') + len(LOCALHOST.encode() + b'\x00'),
    BIN_ROUTING_UPDATE: struct.calcsize('!iiii'),
    BIN_TOPOLOGY_UPDATE: struct.calcsize('!iB'),
}

# Log line -> BIN_* message type (3-word keys checked before 2-word)
_EVENT_MAP: Dict[str, int] = {
    "Register Request Sent":      BIN_REGISTER_REQUEST,
    "Register Response Received": BIN_REGISTER_RESPONSE,
    "Register Request":           BIN_REGISTER_REQUEST,
    "Register Response":          BIN_REGISTER_RESPONSE,
    "Routing Update":             BIN_ROUTING_UPDATE,
    "Link Dead":                  BIN_TOPOLOGY_UPDATE,
    "Switch Dead":                BIN_TOPOLOGY_UPDATE,
    "Switch Alive":               BIN_TOPOLOGY_UPDATE,
    "Neighbor Dead":              BIN_KEEP_ALIVE,
    "Neighbor Alive":             BIN_KEEP_ALIVE,
}


class LogTailer:
    """Tails a log file, yielding new lines as they appear."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._pos: int = 0
        self._exists = False

    def read_new_lines(self) -> List[str]:
        if not os.path.exists(self.path):
            return []
        if not self._exists:
            self._exists = True
            self._pos = 0
        try:
            with open(self.path, 'r') as f:
                f.seek(self._pos)
                new_data = f.read()
                self._pos = f.tell()
            if new_data:
                return new_data.splitlines()
        except OSError:
            pass
        return []


def parse_timestamp(ts_str: str) -> Optional[datetime]:
    ts_str = ts_str.strip()
    try:
        t = datetime.strptime(ts_str, "%H:%M:%S.%f")
        now = datetime.now()
        return t.replace(year=now.year, month=now.month, day=now.day)
    except ValueError:
        return None


def classify_event(line: str) -> Optional[int]:
    words = line.strip().split(None, 3)
    if len(words) >= 3:
        key = " ".join(words[:3])
        if key in _EVENT_MAP:
            return _EVENT_MAP[key]
    if len(words) >= 2:
        key = " ".join(words[:2])
        if key in _EVENT_MAP:
            return _EVENT_MAP[key]
    return None


class PerfMonitor:
    def __init__(self, num_switches: int, neighbor_counts: Dict[int, int],
                 interval: float) -> None:
        self._interval = interval
        self._num_switches = num_switches

        # Estimated message sizes keyed by BIN_* type
        avg_nbrs = sum(neighbor_counts.values()) / num_switches if num_switches else 0
        self._msg_sizes: Dict[int, int] = {
            BIN_REGISTER_REQUEST: MSG_SIZE_FIXED[BIN_REGISTER_REQUEST],
            BIN_REGISTER_RESPONSE: MSG_SIZE_HEADER[BIN_REGISTER_RESPONSE]
                + int(avg_nbrs) * MSG_SIZE_PER_ITEM[BIN_REGISTER_RESPONSE],
            BIN_ROUTING_UPDATE: MSG_SIZE_HEADER[BIN_ROUTING_UPDATE]
                + num_switches * MSG_SIZE_PER_ITEM[BIN_ROUTING_UPDATE],
            BIN_KEEP_ALIVE: MSG_SIZE_FIXED[BIN_KEEP_ALIVE],
            BIN_TOPOLOGY_UPDATE: MSG_SIZE_HEADER[BIN_TOPOLOGY_UPDATE]
                + int(avg_nbrs) * MSG_SIZE_PER_ITEM[BIN_TOPOLOGY_UPDATE],
        }

        # Log tailers
        self._ctrl_tailer = LogTailer("Controller.log")
        self._sw_tailers: Dict[int, LogTailer] = {
            sid: LogTailer(f"switch{sid}.log") for sid in range(num_switches)
        }

        # Event counters per interval
        self._ctrl_events: Dict[int, int] = {}
        self._sw_events: Dict[int, int] = {}

        # Propagation delay tracking
        self._reg_req_sent: Dict[int, datetime] = {}
        self._reg_req_recv: Dict[int, datetime] = {}
        self._reg_rsp_sent: Dict[int, datetime] = {}
        self._reg_rsp_recv: Dict[int, datetime] = {}
        self._delays: List[Tuple[int, float, str]] = []

        # Routing update timing
        self._ctrl_routing_ts: Optional[datetime] = None
        self._routing_delays: List[Tuple[int, float]] = []

    def run(self) -> None:
        while True:
            interval_start = time.time()
            while (time.time() - interval_start) < self._interval:
                self._poll_logs()
                time.sleep(0.5)
            self._flush_summary()

    def _poll_logs(self) -> None:
        # Read controller log
        pending_ts = None
        for line in self._ctrl_tailer.read_new_lines():
            ts = parse_timestamp(line)
            if ts is not None:
                pending_ts = ts
                continue
            event = classify_event(line)
            if event is None:
                continue
            self._ctrl_events[event] = self._ctrl_events.get(event, 0) + 1

            if event == BIN_REGISTER_REQUEST and pending_ts:
                try:
                    sid = int(line.strip().split()[-1])
                    self._reg_req_recv[sid] = pending_ts
                    self._try_match_delay(sid, "req")
                except ValueError:
                    pass

            elif event == BIN_REGISTER_RESPONSE and pending_ts:
                try:
                    sid = int(line.strip().split()[-1])
                    self._reg_rsp_sent[sid] = pending_ts
                except ValueError:
                    pass

            elif event == BIN_ROUTING_UPDATE and pending_ts:
                self._ctrl_routing_ts = pending_ts

        # Read each switch log
        for sid, tailer in self._sw_tailers.items():
            pending_ts = None
            for line in tailer.read_new_lines():
                ts = parse_timestamp(line)
                if ts is not None:
                    pending_ts = ts
                    continue
                event = classify_event(line)
                if event is None:
                    continue
                self._sw_events[event] = self._sw_events.get(event, 0) + 1

                if event == BIN_REGISTER_REQUEST and pending_ts:
                    self._reg_req_sent[sid] = pending_ts
                    self._try_match_delay(sid, "req")

                elif event == BIN_REGISTER_RESPONSE and pending_ts:
                    self._reg_rsp_recv[sid] = pending_ts
                    self._try_match_delay(sid, "rsp")

                elif event == BIN_ROUTING_UPDATE and pending_ts:
                    if self._ctrl_routing_ts:
                        delay_ms = (pending_ts - self._ctrl_routing_ts).total_seconds() * 1000
                        if delay_ms >= 0:
                            self._routing_delays.append((sid, delay_ms))

    def _try_match_delay(self, sid: int, direction: str) -> None:
        if direction == "req":
            sent = self._reg_req_sent.get(sid)
            recv = self._reg_req_recv.get(sid)
            if sent and recv:
                delay_ms = (recv - sent).total_seconds() * 1000
                if delay_ms >= 0:
                    self._delays.append((sid, delay_ms, "switch->ctrl"))
                del self._reg_req_sent[sid]
                del self._reg_req_recv[sid]
        elif direction == "rsp":
            sent = self._reg_rsp_sent.get(sid)
            recv = self._reg_rsp_recv.get(sid)
            if sent and recv:
                delay_ms = (recv - sent).total_seconds() * 1000
                if delay_ms >= 0:
                    self._delays.append((sid, delay_ms, "ctrl->switch"))
                del self._reg_rsp_sent[sid]
                del self._reg_rsp_recv[sid]

    def _flush_summary(self) -> None:
        total_ctrl = sum(self._ctrl_events.values())
        total_sw = sum(self._sw_events.values())
        bw = self._estimate_bandwidth()

        lines = [
            f"{datetime.time(datetime.now())}  [{self._interval:.0f}s interval]",
            f"  events: ctrl={total_ctrl} ({total_ctrl/self._interval:.1f}/s)  "
            f"sw={total_sw} ({total_sw/self._interval:.1f}/s)  bw={bw:.0f} B/s",
        ]

        if self._delays:
            delays_ms = [d for _, d, _ in self._delays]
            avg = sum(delays_ms) / len(delays_ms)
            lines.append(f"  prop delay: avg={avg:.3f}ms  "
                         f"min={min(delays_ms):.3f}ms  max={max(delays_ms):.3f}ms  "
                         f"n={len(delays_ms)}")

        if self._routing_delays:
            r_delays = [d for _, d in self._routing_delays]
            avg = sum(r_delays) / len(r_delays)
            lines.append(f"  route delay: avg={avg:.3f}ms  "
                         f"min={min(r_delays):.3f}ms  max={max(r_delays):.3f}ms  "
                         f"n={len(r_delays)}")

        with open(PERF_LOG_FILE, 'a+') as f:
            f.write("\n".join(lines) + "\n\n")

        self._ctrl_events.clear()
        self._sw_events.clear()
        self._delays.clear()
        self._routing_delays.clear()

    def _estimate_bandwidth(self) -> float:
        total_bytes = 0.0
        for event, count in self._ctrl_events.items():
            total_bytes += count * self._msg_sizes.get(event, 0)
        for event, count in self._sw_events.items():
            total_bytes += count * self._msg_sizes.get(event, 0)
        return total_bytes / self._interval


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python perf.py <config_file> [--interval SECONDS]")
        sys.exit(1)

    config_file = sys.argv[1]
    interval = 10.0
    for i, arg in enumerate(sys.argv):
        if arg == "--interval" and i + 1 < len(sys.argv):
            interval = float(sys.argv[i + 1])

    if not os.path.exists(config_file):
        print(f"Error: Config file '{config_file}' not found")
        sys.exit(1)

    with open(config_file, 'r') as f:
        lines = f.readlines()
    num_switches = int(lines[0].strip())
    neighbor_counts: Dict[int, int] = {i: 0 for i in range(num_switches)}
    for line in lines[1:]:
        line = line.strip()
        if line:
            parts = line.split()
            s1, s2 = int(parts[0]), int(parts[1])
            neighbor_counts[s1] += 1
            neighbor_counts[s2] += 1

    monitor = PerfMonitor(num_switches, neighbor_counts, interval)
    monitor.run()


if __name__ == "__main__":
    main()
