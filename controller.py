#!/usr/bin/env python

"""Controller Code for ECE50863 Lab Project 1
Author: Matt Bowring
Email: mbowring@purdue.edu
"""

import sys
import socket
import json
from datetime import date, datetime
import networkx as nx
from common import *

# Please do not modify the name of the log file, otherwise you will lose points because the grader won't be able to find your log file
LOG_FILE = "Controller.log"

# Those are logging functions to help you follow the correct logging standard

# "Register Request" Format is below:
#
# Timestamp
# Register Request <Switch-ID>

def register_request_received(switch_id):
    log = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Register Request {switch_id}\n")
    write_to_log(log)

# "Register Response" Format is below (for every switch):
#
# Timestamp
# Register Response <Switch-ID>

def register_response_sent(switch_id):
    log = []
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

def routing_table_update(routing_table):
    log = []
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

def topology_update_link_dead(switch_id_1, switch_id_2):
    log = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Link Dead {switch_id_1},{switch_id_2}\n")
    write_to_log(log) 

# "Topology Update: Switch Dead" Format is below:
#
#  Timestamp
#  Switch Dead <Switch ID>

def topology_update_switch_dead(switch_id):
    log = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Switch Dead {switch_id}\n")
    write_to_log(log) 

# "Topology Update: Switch Alive" Format is below:
#
#  Timestamp
#  Switch Alive <Switch ID>

def topology_update_switch_alive(switch_id):
    log = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Switch Alive {switch_id}\n")
    write_to_log(log) 

def write_to_log(log):
    with open(LOG_FILE, 'a+') as log_file:
        log_file.write("\n\n")
        # Write to log
        log_file.writelines(log)

def bootstrap(port, config_file):
    # Register Switches with the Controller

    # Parse the config file to get topology information
    topology = {}  # {switch_id: [list of (neighbor_id, dist)]}
    num_switches = 0
    with open(config_file, 'r') as f:
        lines = f.readlines()
        num_switches = int(lines[0].strip())

        # Initialize topology for all switches
        for i in range(num_switches):
            topology[i] = []

        # Parse topology edges
        for line in lines[1:]:
            line = line.strip()
            if line:
                parts = line.split()
                switch1 = int(parts[0])
                switch2 = int(parts[1])
                dist = int(parts[2])
                # Bidirectional
                topology[switch1].append((switch2, dist))
                topology[switch2].append((switch1, dist))

    # Controller binds to a well-known port number
    controller = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    controller.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    controller.bind((LOCALHOST, port))

    print(f"Controller listening on port {port} (UDP)")

    # Store information about registered switches
    switches = {}  # {switch_id: {'host': host, 'port': port}}

    # Receive Register Requests from all switches
    print(f"Waiting for {num_switches} switches to register...")

    while len(switches) < num_switches:
        # Receive Register Request from switch
        data, addr = controller.recvfrom(BUFFER_SIZE)
        message = json.loads(data.decode())

        if message[KEY_TYPE] == MSG_REGISTER_REQUEST:
            switch_id = message[KEY_SWITCH_ID]
            switch_port = message[KEY_PORT]

            # Log the Register Request
            register_request_received(switch_id)

            # Store switch information
            switches[switch_id] = {
                KEY_HOST: addr[0],
                KEY_PORT: switch_port
            }

            print(f"Switch {switch_id} registered from {addr[0]}:{switch_port}")

    print(f"All {num_switches} switches registered successfully")

    # Send Register Response to each switch once they've been registered
    for switch_id, switch_info in switches.items():
        # Prepare neighbor information for this switch
        neighbors = []
        for neighbor_id, dist in topology[switch_id]:
            neighbor_info = {
                KEY_NEIGHBOR_ID: neighbor_id,
                KEY_ALIVE: True,
                KEY_HOST: switches[neighbor_id][KEY_HOST],
                KEY_PORT: switches[neighbor_id][KEY_PORT]
            }
            neighbors.append(neighbor_info)

        # Send Register Response
        response = {
            KEY_TYPE: MSG_REGISTER_RESPONSE,
            KEY_NEIGHBORS: neighbors
        }
        controller.sendto(
            json.dumps(response).encode(),
            (switch_info[KEY_HOST], switch_info[KEY_PORT])
        )
        register_response_sent(switch_id)
        print(f"Sent Register Response to switch {switch_id}")

    return controller, switches, topology

def build_graph(topology, num_switches):
    """Build a networkx graph from the topology dictionary"""
    G = nx.Graph()
    G.add_nodes_from(range(num_switches))

    # Add edges with weights
    for switch_id, neighbors in topology.items():
        for neighbor_id, cost in neighbors:
            G.add_edge(switch_id, neighbor_id, weight=cost)

    return G

def compute_routing_tables(topology, num_switches):
    """Compute routing tables for all switches using networkx"""
    G = build_graph(topology, num_switches)
    routing_tables = []

    for switch_id in range(num_switches):
        # Compute shortest paths from this switch to all others
        try:
            lengths = nx.single_source_dijkstra_path_length(G, switch_id, weight='weight')
            paths = nx.single_source_dijkstra_path(G, switch_id, weight='weight')
        except nx.NodeNotFound:
            lengths = {}
            paths = {}

        for dest_id in range(num_switches):
            if dest_id == switch_id:
                # Self
                routing_tables.append([switch_id, dest_id, switch_id, SELF_DISTANCE])
            elif dest_id in lengths:
                # Reachable. Next hop is the first node in the path after source
                next_hop = paths[dest_id][1] if len(paths[dest_id]) > 1 else dest_id
                routing_tables.append([switch_id, dest_id, next_hop, int(lengths[dest_id])])
            else:
                # Unreachable
                routing_tables.append([switch_id, dest_id, UNREACHABLE_HOP, UNREACHABLE_DISTANCE])

    return routing_tables

def send_routing_updates(controller, switches, routing_tables):
    """Send routing updates to all switches"""
    # Group routing table entries by switch
    switch_routes = {}
    for entry in routing_tables:
        switch_id = entry[0]
        if switch_id not in switch_routes:
            switch_routes[switch_id] = []
        switch_routes[switch_id].append(entry)

    # Send routing update to each switch
    for switch_id, routes in switch_routes.items():
        if switch_id in switches:
            routing_update = {
                KEY_TYPE: MSG_ROUTING_UPDATE,
                KEY_ROUTES: routes
            }

            controller.sendto(
                json.dumps(routing_update).encode(),
                (switches[switch_id][KEY_HOST], switches[switch_id][KEY_PORT])
            )
            print(f"Sent Routing Update to switch {switch_id}")

def main():
    # Check for number of arguments and exit if host/port not provided
    num_args = len(sys.argv)
    if num_args < 3:
        print ("Usage: python controller.py <port> <config file>\n")
        sys.exit(1)

    port = int(sys.argv[1])
    config_file = sys.argv[2]

    # Setup socket connection to switches
    controller, switches, topology = bootstrap(port, config_file)

    # Compute routing tables
    num_switches = len(switches)
    routing_tables = compute_routing_tables(topology, num_switches)

    # Log routing update
    routing_table_update(routing_tables)

    # Send routing updates to all switches
    send_routing_updates(controller, switches, routing_tables)

    print("\nRouting computation and updates complete")

    # Keep controller running
    # TODO: Handle topology changes (switch/link failures)

if __name__ == "__main__":
    main()