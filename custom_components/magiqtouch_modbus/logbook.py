from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE

DOMAIN = "magiqtouch_modbus"

def async_describe_events(hass, async_describe_event):
    async_describe_event(DOMAIN,"magiqtouch_fan_speed_changed",describe_mtmod_fan_event)


def describe_mtmod_fan_event(event):
    return {
        LOGBOOK_ENTRY_MESSAGE: f"{event.data['name']} fan speed changed from {event.data.get('oldspeed',"Unknown")} to {event.data.get('newspeed','Unknown')}.",
        "domain": "fan",
        "entity_id": event.data.get("entity_id"),
    }
    
