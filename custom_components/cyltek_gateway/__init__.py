"""The CYLTek integration."""
import asyncio
import logging
from pprint import pformat

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import CONF_ENTITY_TYPE, CONF_INTERNET, DOMAIN, PLATFORMS
from .cyltek import globalvar as gl
from .cyltek.cylcontroller_ex import CYLControllerEx

_LOGGER = logging.getLogger(__name__)


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("Configuration options updated, reloading cyltek_gateway integration")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Setup the CYL-Tek things from a config entry created in the integrations UI."""
    from . import system_health
    await system_health.setup_debug(hass, _LOGGER)

    # _LOGGER.error("async_setup_entry")

    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)
    # print(pformat(hass_data))
    # _LOGGER.debug(pformat(hass_data))

    hass.data[DOMAIN][entry.entry_id] = hass_data
    
    # Registers update listener to update config entry when options are updated.
    entry.async_on_unload(entry.add_update_listener(options_update_listener))
    # Using the above means the Listener is attached when the entry is loaded and detached at unload.
    # The Listener shall be an async function that takes the same input as async_setup_entry


    # _LOGGER.debug(pformat(entry))
    # Forward the setup to the sensor platform.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Remove config entry from domain.
        data = hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.config_entries.async_entries(DOMAIN):
            hass.data.pop(DOMAIN)

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""

    # When the user clicks the delete device button for the device and confirms it,
    # async_remove_config_entry_device will be awaited and if True is returned,
    # the config entry will be removed from the device.
    # If it was the only config entry of the device, the device will be removed from the device registry.
    controllers_map = gl.get_controllers_map()
    return not device_entry.identifiers.intersection(
        (DOMAIN, mac) for mac in controllers_map or []
    )


async def async_remove_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    # If a component needs to clean up code when an entry is removed, it can define a removal method:
    controllers_map = gl.get_controllers_map()
    mac = config_entry.data[CONF_MAC]
    if controllers_map.get(mac):
        controllers_map.pop(mac)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """initial data from configuration yaml."""
    # print(pformat(config))
    hass.data.setdefault(DOMAIN, {})
    return True
