A Simple Software Defined Network

The Controller keeps track of the entire Switch network. The switches, once started, register with the controller, which computes shortest paths and then sends appropriate responses to the switches.

### Usage

The `run_network.py` script starts multiple processes for the Controller and Switches. It takes a port number and network configuration
```
python3 run_network.py 9000 Config/graph_2.txt
```

### Logging

Each switch process must log:
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

The Controller process must log:
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