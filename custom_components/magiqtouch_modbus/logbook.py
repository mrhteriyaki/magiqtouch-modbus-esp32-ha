from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE

DOMAIN = "magiqtouch_modbus"

def async_describe_events(hass, async_describe_event):
    async_describe_event(DOMAIN,"magiqtouch_fan_speed_changed",describe_fan_event)
    async_describe_event(DOMAIN,"magiqtouch_mode_changed",describe_mode_event)

def describe_fan_event(event):
    return {
        LOGBOOK_ENTRY_MESSAGE: f"{event.data['name']} fan speed set to {event.data['speed']}.",
        "domain": "fan",
        "entity_id": event.data.get("entity_id"),
    }
    
def describe_mode_event(event):
    return {
        LOGBOOK_ENTRY_MESSAGE: f"{event.data['name']} System mode changed to {event.data['mode']}.",
        "domain": "mode",
        "entity_id": event.data.get("entity_id"),
    }