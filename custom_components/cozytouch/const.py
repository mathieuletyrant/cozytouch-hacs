"""Constants for the Atlantic Cozytouch integration."""

from enum import IntEnum

DOMAIN = "cozytouch"

COZYTOUCH_ATLANTIC_API = "https://apis.groupe-atlantic.com"
COZYTOUCH_CLIENT_ID = (
    "Q3RfMUpWeVRtSUxYOEllZkE3YVVOQmpGblpVYToyRWNORHpfZHkzNDJVSnFvMlo3cFNKTnZVdjBh"
)

CONF_DUMPJSON = "dumpJSON"


class CozytouchCapabilityVariableType(IntEnum):
    """Capabilities types."""

    STRING = 0
    BOOL = 1
    FLOAT = 2
    INT = 3
    ARRAY = 4


SWING_MODE_UP = "up"
SWING_MODE_MIDDLE_UP = "middle_up"
SWING_MODE_MIDDLE_DOWN = "middle_down"
SWING_MODE_DOWN = "down"

HEATING_MODE_OFF = "off"
HEATING_MODE_MANUAL = "manual"
HEATING_MODE_ECO_PLUS = "eco_plus"
HEATING_MODE_PROG = "prog"

AIR_CIRCULATION_SPEED_LOW = "low"
AIR_CIRCULATION_SPEED_MEDIUM = "medium"
AIR_CIRCULATION_SPEED_HIGH = "high"


# The three weekly programs these devices hold, by the first capability of each
# seven-day run: heating and cooling on a boiler or an air conditioner, hot
# water on a water heater. A device gets a calendar per block it reports in
# full, which in practice means one or two of them.
#
# Deliberately its own table rather than `services.PROGRAM_FIRST_CAPABILITY`,
# which knows 196 and 203 only. Reading a program and writing one are not the
# same risk: what the second member of a hot-water slot means has never been
# confirmed against a capture, and writing a block on that basis could leave a
# water heater running a program it never had. Reading it costs nothing, and
# the prog sensors have rendered 237-243 as a time and a setpoint for as long
# as they have existed. `set_schedule` still refuses the block, and should
# until a capture says otherwise.
#
# Here rather than in calendar.py, which built it: the blocks a calendar
# covers are also the blocks whose per-day sensors arrive disabled, and the
# migration in __init__.py that disables existing ones reads the same table.
PROGRAM_BLOCKS = {"heating": 196, "cooling": 203, "hot_water": 237}
