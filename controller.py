#!/usr/bin/env python

"""Controller Code for ECE50863 Lab Project 1
Author: Matt Bowring
Email: mbowring@purdue.edu
"""

import sys
import socket
import struct
import threading
import time
from datetime import datetime
import heapq
import hashlib
from typing import Dict, List, Tuple, Any, Optional

# Type aliases (from common.py)
Topology = Dict[int, List[Tuple[int, int]]]
SwitchInfo = Dict[str, Any]
RoutingEntry = List[int]
NeighborInfo = Dict[str, Any]

# Network constants
LOCALHOST: str = '127.0.0.1'
BUFFER_SIZE: int = 4096

# Distance constants
UNREACHABLE_DISTANCE: int = 9999
UNREACHABLE_HOP: int = -1

# Message keys
KEY_HOST: str = 'host'
KEY_PORT: str = 'port'
KEY_NEIGHBOR_ID: str = 'id'
KEY_ALIVE: str = 'alive'

# Binary message type codes
BIN_REGISTER_REQUEST: int = 1
BIN_REGISTER_RESPONSE: int = 2
BIN_ROUTING_UPDATE: int = 3
BIN_KEEP_ALIVE: int = 4
BIN_TOPOLOGY_UPDATE: int = 5

# Timing constants
UPDATE_DELAY: int = 2
TIMEOUT: int = 3 * UPDATE_DELAY

def deserialize_topology_update(data: bytes) -> Tuple[int, List[Tuple[int, bool]]]:
    offset = 1
    switch_id = struct.unpack('!i', data[offset:offset+4])[0]
    offset += 4
    num_neighbors = struct.unpack('!H', data[offset:offset+2])[0]
    offset += 2
    neighbors = []
    for _ in range(num_neighbors):
        nid, alive = struct.unpack('!iB', data[offset:offset+5])
        offset += 5
        neighbors.append((nid, bool(alive)))
    return switch_id, neighbors

def serialize_register_response(neighbors: List[NeighborInfo]) -> bytes:
    data = struct.pack('!BH', BIN_REGISTER_RESPONSE, len(neighbors))
    for nbr in neighbors:
        host_bytes = nbr[KEY_HOST].encode('utf-8') + b'\x00'
        data += struct.pack('!iBi', nbr[KEY_NEIGHBOR_ID], 1 if nbr[KEY_ALIVE] else 0, nbr[KEY_PORT])
        data += host_bytes
    return data

def serialize_routing_update(routes: List[RoutingEntry]) -> bytes:
    data = struct.pack('!BH', BIN_ROUTING_UPDATE, len(routes))
    for route in routes:
        data += struct.pack('!iiii', route[0], route[1], route[2], route[3])
    return data

def deserialize_register_request(data: bytes) -> Tuple[int, int]:
    _, switch_id, port = struct.unpack('!Bii', data[:9])
    return switch_id, port

# Please do not modify the name of the log file, otherwise you will lose points because the grader won't be able to find your log file
LOG_FILE = "Controller.log"

# Those are logging functions to help you follow the correct logging standard

# "Register Request" Format is below:
#
# Timestamp
# Register Request <Switch-ID>

def register_request_received(switch_id: int) -> None:
    log: List[str] = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Register Request {switch_id}\n")
    write_to_log(log)

# "Register Response" Format is below (for every switch):
#
# Timestamp
# Register Response <Switch-ID>

def register_response_sent(switch_id: int) -> None:
    log: List[str] = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Register Response {switch_id}\n")
    write_to_log(log)

# For the parameter "routing_table", it should be a list of lists in the form of [[...], [...], ...]. 
# Within each list in the outermost list, the first element is <Switch ID>. The second is <Dest ID>, and the third is <Next Hop>, and the fourth is <Shortest distance>
# "Routing Update" Format is below:
#
# Timestamp
# Routing Update 
# <Switch ID>,<Dest ID>:<Next Hop>,<Shortest distance>
# ...
# ...
# Routing Complete
#
# You should also include all of the Self routes in your routing_table argument -- e.g.,  Switch (ID = 4) should include the following entry: 		
# 4,4:4,0
# 0 indicates ‘zero‘ distance
#
# For switches that can’t be reached, the next hop and shortest distance should be ‘-1’ and ‘9999’ respectively. (9999 means infinite distance so that that switch can’t be reached)
#  E.g, If switch=4 cannot reach switch=5, the following should be printed
#  4,5:-1,9999
#
# For any switch that has been killed, do not include the routes that are going out from that switch. 
# One example can be found in the sample log in starter code. 
# After switch 1 is killed, the routing update from the controller does not have routes from switch 1 to other switches.

def routing_table_update(routing_table: List[RoutingEntry]) -> None:
    log: List[str] = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append("Routing Update\n")
    for row in routing_table:
        log.append(f"{row[0]},{row[1]}:{row[2]},{row[3]}\n")
    log.append("Routing Complete\n")
    write_to_log(log)

# "Topology Update: Link Dead" Format is below: (Note: We do not require you to print out Link Alive log in this project)
#
#  Timestamp
#  Link Dead <Switch ID 1>,<Switch ID 2>

def topology_update_link_dead(switch_id_1: int, switch_id_2: int) -> None:
    log: List[str] = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Link Dead {switch_id_1},{switch_id_2}\n")
    write_to_log(log)

# "Topology Update: Switch Dead" Format is below:
#
#  Timestamp
#  Switch Dead <Switch ID>

def topology_update_switch_dead(switch_id: int) -> None:
    log: List[str] = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Switch Dead {switch_id}\n")
    write_to_log(log)

# "Topology Update: Switch Alive" Format is below:
#
#  Timestamp
#  Switch Alive <Switch ID>

def topology_update_switch_alive(switch_id: int) -> None:
    log: List[str] = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Switch Alive {switch_id}\n")
    write_to_log(log)

def write_to_log(log: List[str]) -> None:
    with open(LOG_FILE, 'a+') as log_file:
        log_file.write("\n\n")
        # Write to log
        log_file.writelines(log)

class RoutingCache:
    def __init__(self) -> None:
        self._topo_hash: Optional[str] = None
        self._routes: Optional[List[RoutingEntry]] = None
        self._n: int = 0

    def get_routes(self, topo: Topology, n: int) -> Tuple[List[RoutingEntry], bool]:
        topo_hash = self._compute_topo_hash(topo)
        if self._routes is not None and self._topo_hash == topo_hash and self._n == n:
            return self._routes, False

        # Recompute new topology
        self._routes = self._compute_routing_tables(topo, n)
        self._topo_hash = topo_hash
        self._n = n
        return self._routes, True
    
    def clear(self) -> None:
        self._topo_hash = None
        self._routes = None

    def _compute_topo_hash(self, topo: Topology) -> str:
        # Sort topology for consistent hashing
        topo_str = ""
        for sid in sorted(topo.keys()):
            neighbors = sorted(topo[sid])
            topo_str += f"{sid}:{neighbors};"
        return hashlib.md5(topo_str.encode()).hexdigest()

    def _compute_routing_tables(self, topo: Topology, n: int) -> List[RoutingEntry]:
        routes: List[RoutingEntry] = []
        for sid in range(n):
            dist, hop = self._dijkstra(sid, topo, n)
            for did in range(n):
                if dist[did] == float('inf'):
                    routes.append([sid, did, UNREACHABLE_HOP, UNREACHABLE_DISTANCE])
                else:
                    routes.append([sid, did, hop[did], int(dist[did])])

        return routes

    def _dijkstra(self, src: int, topo: Topology, n: int) -> Tuple[Dict[int, float], Dict[int, int]]:
        # Compute shortest path from the source switch to all reachable switches
        dist = {i: float('inf') for i in range(n)}
        dist[src] = 0
        prev = {i: None for i in range(n)}
        vis = set()

        pq = [(0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if u in vis:
                continue

            vis.add(u)

            for v, cost in topo.get(u, []):
                alt = d + cost
                if alt < dist[v]:
                    dist[v] = alt
                    prev[v] = u
                    heapq.heappush(pq, (alt, v))

        # Build next hop table
        hop: Dict[int, int] = {}
        for dst in range(n):
            if dst == src:
                hop[dst] = src
            elif dist[dst] == float('inf'):
                hop[dst] = UNREACHABLE_HOP
            else:
                node = dst
                while prev[node] != src and prev[node] is not None:
                    node = prev[node]
                hop[dst] = node if prev[node] == src else UNREACHABLE_HOP

        return dist, hop

def bootstrap(port: int, cfg: str) -> Tuple[socket.socket, Dict[int, SwitchInfo], Topology]:
    # Register Switches with the Controller

    # Parse the config file to get topology information
    topo: Topology = {}
    n: int = 0
    with open(cfg, 'r') as f:
        lines = f.readlines()
        n = int(lines[0].strip())

        # Initialize topology for all switches
        for i in range(n):
            topo[i] = []

        # Parse topology edges
        for line in lines[1:]:
            line = line.strip()
            if line:
                parts = line.split()
                s1 = int(parts[0])
                s2 = int(parts[1])
                dist = int(parts[2])
                # Bidirectional
                topo[s1].append((s2, dist))
                topo[s2].append((s1, dist))

    # Controller binds to a well-known port number
    ctrl = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ctrl.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ctrl.bind((LOCALHOST, port))

    # Store information about registered switches
    sw: Dict[int, SwitchInfo] = {}
    while len(sw) < n:
        # Receive Register Request from switch
        data, addr = ctrl.recvfrom(BUFFER_SIZE)
        msg_type = struct.unpack('!B', data[:1])[0]

        assert msg_type == BIN_REGISTER_REQUEST

        sid, sport = deserialize_register_request(data)

        # Log the Register Request
        register_request_received(sid)

        # Store switch information
        sw[sid] = {
            KEY_HOST: addr[0],
            KEY_PORT: sport
        }

    # Send Register Response to each switch once they've been registered
    for sid, info in sw.items():
        # Prepare neighbor information for this switch
        nbrs = []
        for nid, dist in topo[sid]:
            nbr = {
                KEY_NEIGHBOR_ID: nid,
                KEY_ALIVE: True,
                KEY_HOST: sw[nid][KEY_HOST],
                KEY_PORT: sw[nid][KEY_PORT]
            }
            nbrs.append(nbr)

        # Send Register Response (binary format)
        ctrl.sendto(
            serialize_register_response(nbrs),
            (info[KEY_HOST], info[KEY_PORT])
        )
        register_response_sent(sid)

    return ctrl, sw, topo

def build_topology(topo_template: Topology, switch_alive: Dict[int, bool],
                   switch_neighbors: Dict[int, Dict[int, bool]]) -> Topology:
    current_topo: Topology = {}
    for sid in topo_template:
        if not switch_alive.get(sid, False):
            continue
        current_topo[sid] = []
        for nid, cost in topo_template[sid]:
            if not switch_alive.get(nid, False):
                continue
            a_sees_b = switch_neighbors.get(sid, {}).get(nid, True)
            b_sees_a = switch_neighbors.get(nid, {}).get(sid, True)
            if a_sees_b and b_sees_a:
                current_topo[sid].append((nid, cost))
    return current_topo

def send_routing_updates(ctrl: socket.socket, sw: Dict[int, SwitchInfo],
                         routes: List[RoutingEntry],
                         switch_alive: Optional[Dict[int, bool]] = None) -> None:
    # Group routing table entries by switch
    tbl: Dict[int, List[RoutingEntry]] = {}
    for e in routes:
        sid = e[0]
        if sid not in tbl:
            tbl[sid] = []
        tbl[sid].append(e)

    # Send routing update to each switch (binary format)
    for sid, rt in tbl.items():
        if sid in sw:
            if switch_alive is not None and not switch_alive.get(sid, False):
                continue
            ctrl.sendto(
                serialize_routing_update(rt),
                (sw[sid][KEY_HOST], sw[sid][KEY_PORT])
            )

def main() -> None:
    # Check for number of arguments and exit if host/port not provided
    num_args: int = len(sys.argv)
    if num_args < 3:
        print("Usage: python controller.py <port> <config file>\n")
        sys.exit(1)

    port = int(sys.argv[1])
    cfg = str(sys.argv[2])

    cache = RoutingCache()

    # Setup socket connection to switches
    ctrl, sw, topo = bootstrap(port, cfg)

    # Compute routing tables
    n = len(sw)
    routes, _ = cache.get_routes(topo, n)

    # Log routing update
    routing_table_update(routes)

    # Send routing updates to all switches
    send_routing_updates(ctrl, sw, routes)

    # Initialize state for topology change tracking
    topo_template = topo
    lock = threading.Lock()
    switch_alive: Dict[int, bool] = {sid: True for sid in sw}
    last_heard: Dict[int, float] = {sid: time.time() for sid in sw}
    switch_neighbors: Dict[int, Dict[int, bool]] = {}
    for sid in sw:
        switch_neighbors[sid] = {nid: True for nid, _ in topo_template[sid]}

    def recompute_and_send() -> None:
        current_topo = build_topology(topo_template, switch_alive, switch_neighbors)
        routes, was_recomputed = cache.get_routes(current_topo, n)
        if was_recomputed:
            active_routes = [r for r in routes if switch_alive.get(r[0], False)]
            routing_table_update(active_routes)
            send_routing_updates(ctrl, sw, active_routes, switch_alive)

    def periodic_check() -> None:
        while True:
            time.sleep(UPDATE_DELAY)
            with lock:
                now = time.time()
                changed = False
                for sid in list(last_heard.keys()):
                    if switch_alive.get(sid, False) and (now - last_heard[sid]) >= TIMEOUT:
                        switch_alive[sid] = False
                        topology_update_switch_dead(sid)
                        changed = True
                if changed:
                    recompute_and_send()

    # Start periodic check thread
    checker = threading.Thread(target=periodic_check, daemon=True)
    checker.start()

    # Main thread: recv loop
    while True:
        data, addr = ctrl.recvfrom(BUFFER_SIZE)
        msg_type = struct.unpack('!B', data[:1])[0]

        if msg_type == BIN_TOPOLOGY_UPDATE:
            sender_id, nbr_status = deserialize_topology_update(data)

            with lock:
                last_heard[sender_id] = time.time()

                # Update switch address (handles port changes on restart)
                sw[sender_id][KEY_HOST] = addr[0]
                sw[sender_id][KEY_PORT] = addr[1]

                # Check if switch was previously dead
                if not switch_alive.get(sender_id, True):
                    switch_alive[sender_id] = True
                    topology_update_switch_alive(sender_id)

                # Detect link deaths
                old_nbrs = switch_neighbors.get(sender_id, {})
                for nid, alive in nbr_status:
                    was_alive = old_nbrs.get(nid, True)
                    if was_alive and not alive:
                        topology_update_link_dead(sender_id, nid)

                # Update neighbor status
                switch_neighbors[sender_id] = {nid: alive for nid, alive in nbr_status}

                recompute_and_send()

        elif msg_type == BIN_REGISTER_REQUEST:
            # Handle re-registration of a restarted switch
            sid_restart, sport_restart = deserialize_register_request(data)

            with lock:
                sw[sid_restart] = {KEY_HOST: addr[0], KEY_PORT: sport_restart}

                # Send register response with current neighbor info
                nbrs = []
                for nid, _ in topo_template.get(sid_restart, []):
                    nbr = {
                        KEY_NEIGHBOR_ID: nid,
                        KEY_ALIVE: switch_alive.get(nid, False),
                        KEY_HOST: sw.get(nid, {}).get(KEY_HOST, LOCALHOST),
                        KEY_PORT: sw.get(nid, {}).get(KEY_PORT, 0)
                    }
                    nbrs.append(nbr)

                ctrl.sendto(
                    serialize_register_response(nbrs),
                    (addr[0], sport_restart)
                )
                register_request_received(sid_restart)
                register_response_sent(sid_restart)

                # Mark switch alive
                was_dead = not switch_alive.get(sid_restart, True)
                switch_alive[sid_restart] = True
                last_heard[sid_restart] = time.time()
                switch_neighbors[sid_restart] = {nid: True for nid, _ in topo_template.get(sid_restart, [])}

                if was_dead:
                    topology_update_switch_alive(sid_restart)

                recompute_and_send()

                # Send this switch its specific routes
                current_topo = build_topology(topo_template, switch_alive, switch_neighbors)
                all_routes, _ = cache.get_routes(current_topo, n)
                switch_routes = [r for r in all_routes if r[0] == sid_restart]
                ctrl.sendto(
                    serialize_routing_update(switch_routes),
                    (addr[0], sport_restart)
                )

if __name__ == "__main__":
    main()