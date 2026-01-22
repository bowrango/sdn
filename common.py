"""Constants for Controller and Switches
Author: Matt Bowring
Email: mbowring@purdue.edu
"""

# Network constants
LOCALHOST = '127.0.0.1'
BUFFER_SIZE = 4096

# Distance constants
UNREACHABLE_DISTANCE = 9999
UNREACHABLE_HOP = -1
SELF_DISTANCE = 0

# Message types
MSG_REGISTER_REQUEST = 'REGISTER_REQUEST'
MSG_REGISTER_RESPONSE = 'REGISTER_RESPONSE'
MSG_ROUTING_UPDATE = 'ROUTING_UPDATE'
MSG_KEEP_ALIVE = 'KEEP_ALIVE'
MSG_TOPOLOGY_UPDATE = 'TOPOLOGY_UPDATE'

# Message keys
KEY_TYPE = 'type'
KEY_SWITCH_ID = 'switch_id'
KEY_PORT = 'port'
KEY_NEIGHBORS = 'neighbors'
KEY_ROUTES = 'routes'
KEY_NEIGHBOR_ID = 'id'
KEY_ALIVE = 'alive'
KEY_HOST = 'host'