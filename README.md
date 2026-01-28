A Simple Software Defined Network

The Controller keeps track of the entire Switch network. The switches, once started, register with the Controller, which computes shortest paths and then sends appropriate responses to the switches. The Controller caches routing tables and only recomputes when the topology changes during periodic updates. The socket messages use a `struct`-based binary format.

### Usage

The `run_network.py` script starts multiple processes for the Controller and switches. It takes a port number and network configuration
```
python3 run_network.py 9000 Config/graph_2.txt
```

### Periodic Checks (TODO)
Each switch and the Controller perform a set of routine checks:
1. Each switch sends a `KEEP_ALIVE` message every K seconds to each of its neighboring switches that it thinks is "alive".
2. Each switch sends a Topology Update message to the Controller every K seconds. The Topology Update message includes a set of "live" neighbors of that switch.
3. If a switch A has not received a `KEEP_ALIVE` message from a neighboring switch B for `TIMEOUT` seconds, then switch A designates the link connecting it to switch B as down. Immediately, it sends a Topology Update message to the Controller containing its updated view of the list of "live" neighbors.
4. Once switch A receives a `KEEP_ALIVE` message from a neighboring switch B that it previously considered unreachable, it immediately marks that neighbor as alive, updates the host/port information of the switch if needed, and sends a Topology Update to the Controller indicating its revised list of "live" neighbors

### Link Failure (TODO)
A link failure can be simulated with the `-f` flag, which kills the process corresponding to the neighboring switch. Restarting the process with the same switch ID ensures the switch can rejoin the network.
```
python switch.py <switch-ID> <Controller hostname> <Controller port> -f <neighbor-ID>
``` 
This says that the switch must run as usual, but the link to `<neighbor-ID>` failed. In this failure mode,
the switch does not send `KEEP_ALIVE` messages to the switch with ID `<neighbor-ID>`, and
should not process any `KEEP_ALIVE` messages from the switch with ID `<neighbor-ID>`.

### Logging

Each switch logs the following events:
1. When a Register Request is sent.
```
<switch-ID> Register_Request
```
2. When the Register Response is received.
```
<number-of-neighbors>
<neighbor-ID> <neighbor hostname> <neighbor port> (for each neighbor)
```
3. When any neighboring switches are considered unreachable.
4. When a previously unreachable switch is now reachable.
5. The routing table that it gets from the Controller each time that the table is updated.

The Controller logs the following events:
1. When a Register Request is received.
2. When all the Register Responses are sent (send one Register Response to each switch).
3. When it detects a change in topology (a switch or a link is down or up).
```
<switch-ID>
<neighbor-ID> <True/False indicating whether the neighbor is alive> (for all neighbors)
```
4. Whenever it recomputes (or computes for the first time) the routes.
```
<switch-ID>
<dest-ID> <Next Hop to reach dest> (for all switches in the network)
```