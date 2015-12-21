
import logging

from lib.connector import BaseConnector


LOGGER = logging.getLogger("converters/location")
MAP = {}
MAP_FIELD = None

FAILED_LOOKUP = {}


def _load_map(location_field, label_field):
    global MAP_FIELD
    global MAP
    MAP_FIELD = location_field

    LOGGER.info("Loading data for Locations converter.")
    MAP = BaseConnector.OomnitzaConnector.get_location_mappings(location_field, label_field)
    LOGGER.info("Loaded %s locations.", len(MAP))
    if not MAP:
        raise Exception("Zero locations loaded from Oomnitza.")
    return MAP


def converter(field, record, value, params):
    """
    Converts an external location to an internal location based on a custom field.
    params:
        field: Default 'location_id': the Oomnitza field_id
        label: Default 'name': the Oomnitza field to use as value.
    :return: nice Location name
    """
    internal_field = params.get('field', 'location_id')
    label_field = params.get('label', 'name')
    if not internal_field:
        raise Exception("Missing Oomnitza field in Location converter.")

    if not MAP_FIELD:
        _load_map(internal_field, label_field)
    else:
        if internal_field != MAP_FIELD:
            raise Exception("MAP_FIELD has changed from %s to %s!" % (MAP_FIELD, internal_field))

    if not value:
        return None

    if value in MAP:
        return MAP[value]
    # LOGGER.error("Failed to find location %r in Location field %r.", value, internal_field)
    if value not in FAILED_LOOKUP:
        FAILED_LOOKUP[value] = 1
    else:
        FAILED_LOOKUP[value] += 1

    return value


def cleanup():
    if FAILED_LOOKUP:
        LOGGER.error(
            "Could not lookup Location values for the following values: %s",
            ', '.join(FAILED_LOOKUP.keys())
        )
        LOGGER.warning("Counts: %r", FAILED_LOOKUP)
