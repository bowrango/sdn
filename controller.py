#!/usr/bin/env python

"""Controller Code for ECE50863 Lab Project 1
Author: Matt Bowring
Email: mbowring@purdue.edu
"""

import sys
import socket
import struct
from datetime import datetime
import heapq
import hashlib
from typing import Dict, List, Tuple, Optional
from common import *

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

def send_routing_updates(ctrl: socket.socket, sw: Dict[int, SwitchInfo], routes: List[RoutingEntry]) -> None:
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
    routes, was_recomputed = cache.get_routes(topo, n)

    # Log routing update
    routing_table_update(routes)

    # Send routing updates to all switches
    send_routing_updates(ctrl, sw, routes)

    # Keep controller running
    # TODO: Handle topology changes (switch/link failures). Only broadcast updates when the topology get recomputed

if __name__ == "__main__":
    main()