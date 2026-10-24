from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_ICON,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.core import Event, HomeAssistant, callback

from .const import DOMAIN, EVENT_FAN_SPEED_CHANGED


@callback
def async_describe_events(hass: HomeAssistant, async_describe_event) -> None:
    async_describe_event(DOMAIN, EVENT_FAN_SPEED_CHANGED, describe_mtmod_fan_event)


@callback
def describe_mtmod_fan_event(event: Event) -> dict[str, str]:
    return {
        LOGBOOK_ENTRY_NAME: event.data.get("name", "MagiqTouch"),
        LOGBOOK_ENTRY_MESSAGE: f"fan speed changed from {event.data.get('oldspeed', 'Unknown')} to {event.data.get('newspeed', 'Unknown')}",
        LOGBOOK_ENTRY_ICON: "mdi:fan",
        LOGBOOK_ENTRY_ENTITY_ID: event.data.get("entity_id"),
    }
