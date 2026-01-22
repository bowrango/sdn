"""Constants for Controller and Switches
Author: Matt Bowring
Email: mbowring@purdue.edu
"""

from typing import Dict, List, Tuple, Any

# Type aliases
Topology = Dict[int, List[Tuple[int, int]]]  # {switch_id: [(neighbor_id, cost), ...]}
SwitchInfo = Dict[str, Any]  # {'host': str, 'port': int}
RoutingEntry = List[int]  # [switch_id, dest_id, next_hop, distance]
NeighborInfo = Dict[str, Any]  # {'id': int, 'alive': bool, 'host': str, 'port': int}

# Network constants
LOCALHOST: str = '127.0.0.1'
BUFFER_SIZE: int = 4096
UPDATE_DELAY: int = 2  # (seconds)
TIMEOUT: int = 3 * UPDATE_DELAY

# Distance constants
UNREACHABLE_DISTANCE: int = 9999
UNREACHABLE_HOP: int = -1
SELF_DISTANCE: int = 0

# Message types
MSG_REGISTER_REQUEST: str = 'REGISTER_REQUEST'
MSG_REGISTER_RESPONSE: str = 'REGISTER_RESPONSE'
MSG_ROUTING_UPDATE: str = 'ROUTING_UPDATE'
MSG_KEEP_ALIVE: str = 'KEEP_ALIVE'
MSG_TOPOLOGY_UPDATE: str = 'TOPOLOGY_UPDATE'

# Message keys
KEY_TYPE: str = 'type'
KEY_SWITCH_ID: str = 'switch_id'
KEY_PORT: str = 'port'
KEY_NEIGHBORS: str = 'neighbors'
KEY_ROUTES: str = 'routes'
KEY_NEIGHBOR_ID: str = 'id'
KEY_ALIVE: str = 'alive'
KEY_HOST: str = 'host'