# Software Defined Network

A centralized SDN controller with distributed switches communicating over UDP. The controller computes shortest-path routing tables using Dijkstra's algorithm and pushes them to switches. Switches exchange `KEEP_ALIVE` heartbeats with neighbors and report topology changes to the controller, which recomputes routes only when the network topology changes. All messages use a `struct`-based binary protocol.

## Quick Start

Launch an entire network (macOS only, opens separate Terminal windows):
```
python3 run_network.py <port> <config_file>
```
Example:
```
python3 run_network.py 9000 Config/graph_3.txt
```

## Manual Start

Start the controller and each switch individually. The controller must be started first.

```
python3 controller.py <port> <config_file>
python3 switch.py <switch_id> <controller_host> <controller_port>
```

Example: run a 3-switch network:
```
python3 controller.py 9000 Config/graph_3.txt
python3 switch.py 0 localhost 9000
python3 switch.py 1 localhost 9000
python3 switch.py 2 localhost 9000
```

Simulate a link failure with the `-f` flag. The switch will not send or process `KEEP_ALIVE` messages to/from the specified neighbor:

```
python3 switch.py <switch_id> <controller_host> <controller_port> -f <neighbor_id>
```
Example:
```
python3 switch.py 0 localhost 9000 -f 1
```
This simulates a failed link between switch 0 and switch 1. After `TIMEOUT` (6s), both sides detect the dead link and the controller recomputes routes. To simulate a full switch failure, kill the switch process (Ctrl+C). Restarting a switch with the same ID will re-register it with the controller and rejoin the network.

Run `perf.py` alongside the network to log message rates, estimated bandwidth, and propagation delays to `Performance.log`:
```
python3 perf.py <config_file> [--interval SECONDS]
```
The default reporting interval is 10 seconds. With the automated launcher, pass `-p`:
```
python3 run_network.py 9000 Config/graph_3.txt -p
```

## Details

Each switch sends a `REGISTER_REQUEST` to the controller on startup. Once all switches have registered, the controller responds with neighbor information and computes initial routing tables using Dijkstra's algorithm.

Every 2 seconds, each switch sends `KEEP_ALIVE` messages to its alive neighbors and a `TOPOLOGY_UPDATE` to the controller. If no `KEEP_ALIVE` is received from a neighbor for 6 seconds, the link is marked dead and the controller is notified. The controller also monitors for full switch death if no `TOPOLOGY_UPDATE` arrives within 6 seconds.

The controller caches routing tables and only recomputes when the topology hash changes. Updated routes are pushed to all alive switches.

Each switch writes to `switch<id>.log` and the controller writes to `Controller.log`. Logged events include register requests and responses, neighbor and switch dead/alive transitions, link failures, and routing table updates.
