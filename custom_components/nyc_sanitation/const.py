"""Constants for NYC Sanitation integration."""

from datetime import timedelta

DOMAIN = "nyc_sanitation"

DSNY_BASE_URL = "https://dsnypublic.nyc.gov/dsny/api/geocoder/DSNYCollection"
ID_FOR_SERVICE = "CE3C8015-22F0-4906-A2C5-031D95733F16"

NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

UPDATE_INTERVAL = timedelta(hours=12)

PANEL_TITLE = "Sanitation"
PANEL_ICON = "mdi:trash-can"
PANEL_URL_PATH = "nyc_sanitation"

NYC_BOROUGH_CODES = frozenset({"BK", "MN", "QN", "BX", "SI"})
NYC_BOROUGH_NAMES = frozenset(
    {
        "MANHATTAN",
        "BRONX",
        "BROOKLYN",
        "QUEENS",
        "STATEN ISLAND",
    }
)

WS_TYPE_GET_COLLECTION = f"{DOMAIN}/get_collection_data"

ATTR_RESIDENTIAL_ROUTING = "residential_routing_times"
ATTR_COLLECTION_TYPES_TODAY = "collection_types_today"
ATTR_FORMATTED_ADDRESS = "formatted_address"
ATTR_COMMUNITY_BOARD = "community_board"
