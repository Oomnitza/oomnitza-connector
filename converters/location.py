
import logging

from lib.connector import BaseConnector


LOGGER = logging.getLogger("converters/location")
MAP = {}
MAP_FIELD = None

FAILED_LOOKUP = {}


def _load_map(location_field):
    global MAP_FIELD
    global MAP
    MAP_FIELD = location_field

    LOGGER.info("Loading data for Locations converter.")
    MAP = BaseConnector.OomnitzaConnector.get_location_mappings(location_field)
    LOGGER.info("Loaded %s locations.", len(MAP))
    if not MAP:
        raise Exception("Zero locations loaded from Oomnitza.")
    return MAP


def converter(field, record, value, params):
    """
    Converts an external location to an internal location based on a custom field.
    params:
        field: Required: the Oomnitza field_id

    :param value:
    :return: nice model name
    """
    int_field = params.get('field', None)
    if not int_field:
        raise Exception("Missing Oomnitza field in Location converter.")

    if not MAP_FIELD:
        _load_map(int_field)
    else:
        if int_field != MAP_FIELD:
            raise Exception("MAP_FIELD has changed from %s to %s!" % (MAP_FIELD, int_field))

    if not value:
        return None

    if value in MAP:
        return MAP[value]
    # LOGGER.error("Failed to find location %r in Location field %r.", value, int_field)
    if value not in FAILED_LOOKUP:
        FAILED_LOOKUP[value] = 1
    else:
        FAILED_LOOKUP[value] += 1

    return "LookUp Failed: %s" % value


def cleanup():
    if FAILED_LOOKUP:
        LOGGER.error(
            "Could not lookup Location values for the following values: %s",
            ', '.join(FAILED_LOOKUP.keys())
        )
        LOGGER.warning("Counts: %r", FAILED_LOOKUP)