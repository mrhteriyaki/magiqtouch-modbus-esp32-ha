from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_URL, DOMAIN
from .coordinator import MagiqtouchConfigEntry, MTMODCoordinator

PLATFORMS = [Platform.CLIMATE]

LEGACY_UNIQUE_ID_PREFIX = "magiqtouch_zone_"


async def async_setup_entry(hass: HomeAssistant, entry: MagiqtouchConfigEntry) -> bool:
    coordinator = MTMODCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MagiqtouchConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: MagiqtouchConfigEntry) -> bool:
    if entry.version > 1:
        return False #Downgrade from a future version.

    if entry.minor_version < 2:
        #1.1 -> 1.2: Entity and device IDs were global (zone number / URL), scope them to the config entry.
        @callback
        def migrate_unique_id(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
            if entity_entry.unique_id.startswith(LEGACY_UNIQUE_ID_PREFIX):
                zone = entity_entry.unique_id.removeprefix(LEGACY_UNIQUE_ID_PREFIX)
                return {"new_unique_id": f"{entry.entry_id}_zone_{zone}"}
            return None

        await er.async_migrate_entries(hass, entry.entry_id, migrate_unique_id)

        #Only look at this entry's devices, identifiers aren't unique across config entries.
        device_registry = dr.async_get(hass)
        legacy_identifier = (DOMAIN, entry.data[CONF_URL])
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
            if legacy_identifier in device.identifiers:
                device_registry.async_update_device(device.id, new_identifiers={(DOMAIN, entry.entry_id)})

        #Entries created before 1.2 had no unique ID, use the URL so the device can't be added twice.
        unique_id = entry.unique_id
        url = entry.data[CONF_URL].rstrip("/")
        if unique_id is None and not any(
            other.unique_id == url for other in hass.config_entries.async_entries(DOMAIN)
        ):
            unique_id = url
        hass.config_entries.async_update_entry(entry, unique_id=unique_id, minor_version=2)

    return True
