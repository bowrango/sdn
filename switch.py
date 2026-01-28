#!/usr/bin/env python

"""Switch Code for ECE50863 Lab Project 1
Author: Matt Bowring
Email: mbowring@purdue.edu
"""

import sys
import socket
import struct
from datetime import datetime
from typing import List, Tuple, Optional
from common import *

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
        # Log routing table update
        routing_table_update(routes)

    # Keep the switch running
    # TODO: Implement neighbor discovery and keep-alive protocols

if __name__ == "__main__":
    main()