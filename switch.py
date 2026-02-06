#!/usr/bin/env python

"""Switch Code for ECE50863 Lab Project 1
Author: Matt Bowring
Email: mbowring@purdue.edu
"""

import sys
import socket
import struct
import threading
import time
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

# Type aliases (from common.py)
RoutingEntry = List[int]
NeighborInfo = Dict[str, Any]

# Network constants
LOCALHOST: str = '127.0.0.1'
BUFFER_SIZE: int = 4096

# Binary message type codes
BIN_REGISTER_REQUEST: int = 1
BIN_REGISTER_RESPONSE: int = 2
BIN_ROUTING_UPDATE: int = 3
BIN_KEEP_ALIVE: int = 4
BIN_TOPOLOGY_UPDATE: int = 5

# Timing constants
UPDATE_DELAY: int = 2
TIMEOUT: int = 3 * UPDATE_DELAY

# Message keys
KEY_NEIGHBOR_ID: str = 'id'
KEY_ALIVE: str = 'alive'
KEY_HOST: str = 'host'
KEY_PORT: str = 'port'

def serialize_register_request(switch_id: int, port: int) -> bytes:
    return struct.pack('!Bii', BIN_REGISTER_REQUEST, switch_id, port)

def deserialize_register_response(data: bytes) -> List[NeighborInfo]:
    offset = 1
    num_neighbors = struct.unpack('!H', data[offset:offset+2])[0]
    offset += 2
    neighbors = []
    for _ in range(num_neighbors):
        nid, alive, port = struct.unpack('!iBi', data[offset:offset+9])
        offset += 9
        host_end = data.index(b'\x00', offset)
        host = data[offset:host_end].decode('utf-8')
        offset = host_end + 1
        neighbors.append({
            KEY_NEIGHBOR_ID: nid,
            KEY_ALIVE: bool(alive),
            KEY_HOST: host,
            KEY_PORT: port
        })
    return neighbors

def deserialize_routing_update(data: bytes) -> List[RoutingEntry]:
    offset = 1
    num_routes = struct.unpack('!H', data[offset:offset+2])[0]
    offset += 2
    routes = []
    for _ in range(num_routes):
        sid, did, hop, dist = struct.unpack('!iiii', data[offset:offset+16])
        offset += 16
        routes.append([sid, did, hop, dist])
    return routes

def serialize_keep_alive(switch_id: int) -> bytes:
    return struct.pack('!Bi', BIN_KEEP_ALIVE, switch_id)

def deserialize_keep_alive(data: bytes) -> int:
    _, switch_id = struct.unpack('!Bi', data[:5])
    return switch_id

def serialize_topology_update(switch_id: int, neighbors: List[Tuple[int, bool]]) -> bytes:
    data = struct.pack('!BiH', BIN_TOPOLOGY_UPDATE, switch_id, len(neighbors))
    for nid, alive in neighbors:
        data += struct.pack('!iB', nid, 1 if alive else 0)
    return data

# Please do not modify the name of the log file, otherwise you will lose points because the grader won't be able to find your log file
LOG_FILE = "switch#.log" # The log file for switches are switch#.log, where # is the id of that switch (i.e. switch0.log, switch1.log). The code for replacing # with a real number has been given to you in the main function.

# Those are logging functions to help you follow the correct logging standard

# "Register Request" Format is below:
#
# Timestamp
# Register Request Sent

def register_request_sent() -> None:
    log: List[str] = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Register Request Sent\n")
    write_to_log(log)

# "Register Response" Format is below:
#
# Timestamp
# Register Response Received

def register_response_received() -> None:
    log: List[str] = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Register Response Received\n")
    write_to_log(log)

# For the parameter "routing_table", it should be a list of lists in the form of [[...], [...], ...]. 
# Within each list in the outermost list, the first element is <Switch ID>. The second is <Dest ID>, and the third is <Next Hop>.
# "Routing Update" Format is below:
#
# Timestamp
# Routing Update 
# <Switch ID>,<Dest ID>:<Next Hop>
# ...
# ...
# Routing Complete
# 
# You should also include all of the Self routes in your routing_table argument -- e.g.,  Switch (ID = 4) should include the following entry: 		
# 4,4:4

def routing_table_update(routing_table: List[RoutingEntry]) -> None:
    log: List[str] = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append("Routing Update\n")
    for row in routing_table:
        log.append(f"{row[0]},{row[1]}:{row[2]}\n")
    log.append("Routing Complete\n")
    write_to_log(log)

# "Unresponsive/Dead Neighbor Detected" Format is below:
#
# Timestamp
# Neighbor Dead <Neighbor ID>

def neighbor_dead(switch_id: int) -> None:
    log: List[str] = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Neighbor Dead {switch_id}\n")
    write_to_log(log)

# "Unresponsive/Dead Neighbor comes back online" Format is below:
#
# Timestamp
# Neighbor Alive <Neighbor ID>

def neighbor_alive(switch_id: int) -> None:
    log: List[str] = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Neighbor Alive {switch_id}\n")
    write_to_log(log)

def write_to_log(log: List[str]) -> None:
    with open(LOG_FILE, 'a+') as log_file:
        log_file.write("\n\n")
        # Write to log
        log_file.writelines(log)

def register_with_controller(sid: int, host: str, port: int) -> Optional[Tuple[socket.socket, List[NeighborInfo]]]:
    # Create a UDP socket for communication with controller and other switches
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Bind to localhost
    sock.bind((LOCALHOST, 0))
    sport = sock.getsockname()[1]

    # Send Register Request to controller via UDP (binary format)
    sock.sendto(
        serialize_register_request(sid, sport),
        (host, port)
    )
    register_request_sent()

    # Receive Register Response from controller (binary format)
    data, _ = sock.recvfrom(BUFFER_SIZE)
    msg_type = struct.unpack('!B', data[:1])[0]

    if msg_type == BIN_REGISTER_RESPONSE:
        register_response_received()
        nbrs = deserialize_register_response(data)
        return sock, nbrs

    return None

def main() -> None:
    global LOG_FILE

    # Check for number of arguments and exit if host/port not provided
    if len(sys.argv) < 4:
        print("switch.py <Id_self> <Controller hostname> <Controller Port>\n")
        sys.exit(1)

    sid: int = int(sys.argv[1])
    host: str = sys.argv[2]
    port: int = int(sys.argv[3])

    LOG_FILE = 'switch' + str(sid) + ".log"

    # Register with controller and get neighbor information
    result = register_with_controller(sid, host, port)
    if result is None:
        sys.exit(1)

    sock, nbrs = result

    # Receive routing update (binary format)
    data, _ = sock.recvfrom(BUFFER_SIZE)
    msg_type = struct.unpack('!B', data[:1])[0]
    if msg_type == BIN_ROUTING_UPDATE:
        routes = deserialize_routing_update(data)
        routing_table_update(routes)

    # Parse -f flag for link failure simulation
    failed_neighbor: Optional[int] = None
    if len(sys.argv) >= 6 and sys.argv[4] == '-f':
        failed_neighbor = int(sys.argv[5])

    # Initialize neighbor state from register response
    lock = threading.Lock()
    neighbors: Dict[int, Dict[str, Any]] = {}
    for nbr in nbrs:
        neighbors[nbr[KEY_NEIGHBOR_ID]] = {
            KEY_HOST: nbr[KEY_HOST],
            KEY_PORT: nbr[KEY_PORT],
            KEY_ALIVE: True,
            'last_heard': time.time()
        }
    controller_addr = (host, port)

    def send_topology_update() -> None:
        nbr_list = [(nid, info[KEY_ALIVE]) for nid, info in neighbors.items()]
        sock.sendto(
            serialize_topology_update(sid, nbr_list),
            controller_addr
        )

    def periodic_tasks() -> None:
        while True:
            time.sleep(UPDATE_DELAY)
            with lock:
                now = time.time()

                # Check for timed-out neighbors
                for nid, info in neighbors.items():
                    if info[KEY_ALIVE] and (now - info['last_heard']) >= TIMEOUT:
                        info[KEY_ALIVE] = False
                        neighbor_dead(nid)

                # Send KEEP_ALIVE to each alive neighbor (skip failed)
                for nid, info in neighbors.items():
                    if not info[KEY_ALIVE]:
                        continue
                    if failed_neighbor is not None and nid == failed_neighbor:
                        continue
                    sock.sendto(
                        serialize_keep_alive(sid),
                        (info[KEY_HOST], info[KEY_PORT])
                    )

                # Send Topology Update to controller
                send_topology_update()

    # Start periodic timer thread
    timer = threading.Thread(target=periodic_tasks, daemon=True)
    timer.start()

    # Main thread: recv loop
    while True:
        data, addr = sock.recvfrom(BUFFER_SIZE)
        msg_type = struct.unpack('!B', data[:1])[0]

        if msg_type == BIN_KEEP_ALIVE:
            sender_id = deserialize_keep_alive(data)

            # Ignore keep-alive from failed neighbor
            if failed_neighbor is not None and sender_id == failed_neighbor:
                continue

            with lock:
                if sender_id in neighbors:
                    was_dead = not neighbors[sender_id][KEY_ALIVE]
                    neighbors[sender_id]['last_heard'] = time.time()

                    if was_dead:
                        neighbors[sender_id][KEY_ALIVE] = True
                        neighbors[sender_id][KEY_HOST] = addr[0]
                        neighbors[sender_id][KEY_PORT] = addr[1]
                        neighbor_alive(sender_id)
                        send_topology_update()

        elif msg_type == BIN_ROUTING_UPDATE:
            routes = deserialize_routing_update(data)
            routing_table_update(routes)

if __name__ == "__main__":
    main()