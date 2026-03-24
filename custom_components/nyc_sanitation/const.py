"""Constants for NYC Sanitation integration."""

from datetime import timedelta

DOMAIN = "nyc_sanitation"

DSNY_BASE_URL = "https://dsnypublic.nyc.gov/dsny/api/geocoder/DSNYCollection"
ID_FOR_SERVICE = "CE3C8015-22F0-4906-A2C5-031D95733F16"

NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

UPDATE_INTERVAL = timedelta(hours=1)

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
WS_TYPE_GET_TTS_OPTIONS = f"{DOMAIN}/get_tts_options"
WS_TYPE_SET_TTS_OPTIONS = f"{DOMAIN}/set_tts_options"
WS_TYPE_TEST_TTS = f"{DOMAIN}/test_tts"
WS_TYPE_PREVIEW_TTS_MESSAGE = f"{DOMAIN}/preview_tts_message"

DEFAULT_TTS_OPTIONS = {
    "tts_enabled": False,
    "tts_window_start_hour": 12,
    "tts_window_end_hour": 20,
    "tts_interval_hours": 1,
    "tts_minute_offset": 0,
    "media_player_entity_id": "",
    "tts_entity_id": "",
    "volume": None,
    "tts_cache": True,
    "tts_language": "",
    "tts_options": None,
    "tts_message_prefix": "Message from Sanitation,",
    "tts_message_trash": (
        "{curb_reminder} Tomorrow, {weekday}. {type_status} {large_items_note}"
    ),
    "tts_message_recycling": (
        "{curb_reminder} Tomorrow, {weekday}. {type_status} {large_items_note}"
    ),
    "tts_message_compost": (
        "{curb_reminder} Tomorrow, {weekday}. {type_status} {large_items_note}"
    ),
    "tts_message_large_items": (
        "{curb_reminder} Tomorrow, {weekday}. {type_status} {large_items_note}"
    ),
    "tts_message_mixed": (
        "{curb_reminder} Tomorrow, {weekday}. {type_status} {large_items_note}"
    ),
}

DEFAULT_TTS_LANGUAGE = "en"

ATTR_RESIDENTIAL_ROUTING = "residential_routing_times"
ATTR_COLLECTION_TYPES_TODAY = "collection_types_today"
ATTR_COLLECTION_TYPES_TOMORROW = "collection_types_tomorrow"
ATTR_COLLECTION_TYPES = "collection_types"
ATTR_PICKUP_WEEKDAY = "weekday"
ATTR_FORMATTED_ADDRESS = "formatted_address"
ATTR_COMMUNITY_BOARD = "community_board"
