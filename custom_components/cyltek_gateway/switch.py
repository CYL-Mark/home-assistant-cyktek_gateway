"""Platform for switch integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from pprint import pformat
from typing import Any, Callable, Dict, Optional

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
# These constants are relevant to the type of entity we are using.
# See below for how they are used.
from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.config_entries import ConfigEntry
# Import the device class from the component that you want to support
from homeassistant.const import CONF_DEVICES, CONF_MAC, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import util
from .const import (CONF_CHANNELS, CONF_ENTITY_TYPE, CONF_INTERNET,
                    DEFAULT_NAMES, DOMAIN)
from .cyltek import cylswitch
from .cyltek.cylswitch import CYLSwitch
from .entity import CYLDeviceEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = DEFAULT_NAMES["switch"]

SCAN_INTERVAL = timedelta(seconds=10)

VALID_CHANNEL = vol.All(cv.positive_int, vol.Range(min=0, max=96))
CHANNEL_SCHEMA = vol.Schema(
    {
        vol.Required('on-off',     default=1): VALID_CHANNEL,
    }
)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CHANNELS):                   CHANNEL_SCHEMA,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MAC):         vol.All(cv.string, util.MAC()),
        vol.Optional(CONF_INTERNET, default='eth0'):    cv.string,
        vol.Required(CONF_DEVICES):     vol.All(cv.ensure_list, [DEVICE_SCHEMA]),
    }
)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Setup the CYL-Tek things from configuration yaml."""
    # print(pformat(config))

    for dinfo in config[CONF_DEVICES]:

        switch = cylswitch.create_cylswitch(config[CONF_MAC],
                                       dinfo[CONF_CHANNELS],
                                       internet=config[CONF_INTERNET],
                                       auto_on=False,
                                       model=None)
        async_add_entities([CYLTekSwitch(switch, dinfo[CONF_NAME])], True)


# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
):
    """Setup the CYL-Tek things from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    print("async_setup_entry")
    # Update our config to include new devices and remove those that have been removed.
    if config_entry.options:
        config.update(config_entry.options)

    for dinfo in config[CONF_DEVICES]:
        if dinfo[CONF_ENTITY_TYPE] == Platform.SWITCH:
            switch = cylswitch.create_cylswitch(config[CONF_MAC],
                                        dinfo[CONF_CHANNELS],
                                        internet=config[CONF_INTERNET],
                                        auto_on=False,
                                        model=None)
            async_add_entities([CYLTekSwitch(switch, dinfo[CONF_NAME])], True)



class CYLTekSwitch(CYLDeviceEntity, SwitchEntity):
    """Representation of an CYL-Tek Switch."""

    def __init__(self, switch: CYLSwitch, name: str="CYLTekSwitch") -> None:
        """Initialize an CYLTekSwitch."""
        super().__init__(switch.cyl_controller)
        self._switch = switch
        self._switch.alias = name
        
        self._is_on = None

        self._available = True
        self._need_update = True

    @property
    def available(self) -> bool:
        return self._available

    @property
    def name(self) -> str:
        """Return the display name of this switch."""
        return self._switch.alias

    @property
    def unique_id(self):
        """Return the ID of this switch."""
        return self._switch.unique_id

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self._is_on


    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""
        # print("async_turn_on")
        if self._available is False:
            return

        # if self._is_on is False:
        if await self._async_try_command(
            f'{self.name}, {self.unique_id} Turning the switch on failed.',
            self._switch.turn_on
        ):
            self._is_on = True
            self._need_update = False


    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        # print("async_turn_off")
        if self._available is False:
            return
            
        # if self._is_on is True:
        if await self._async_try_command(
            f'{self.name}, {self.unique_id} Turning the switch off failed.',
            self._switch.turn_off
        ):
            self._is_on = False
            self._need_update = False


    async def async_update(self) -> None:
        """Fetch new state data for this switch.
        This is the only method that should fetch new data for Home Assistant.
        """
        """Synchronise internal state with the actual switches state."""

        if self._need_update is False:
            self._need_update = True
            return

        self._available = await self._async_try_command(
                f'{self.name}, {self.unique_id} switche is unavalible !',
                self._switch.is_available
            )

        if self._available is False:
            return

        if self._is_on != self._switch.get_last_attribute('power'):
            self._is_on = self._switch.get_last_attribute('power')
