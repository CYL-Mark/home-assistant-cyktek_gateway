"""Platform for light integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from pprint import pformat
from typing import Any, Callable, Dict, Optional

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
# These constants are relevant to the type of entity we are using.
# See below for how they are used.
from homeassistant.components.light import (ATTR_BRIGHTNESS, PLATFORM_SCHEMA,
                                            SUPPORT_BRIGHTNESS, SUPPORT_COLOR,
                                            SUPPORT_COLOR_TEMP, LightEntity)
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
from .cyltek import cylight
from .cyltek.cylight import CYLight
from .entity import CYLDeviceEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = DEFAULT_NAMES["light"]
SCAN_INTERVAL = timedelta(seconds=10)

VALID_CHANNEL = vol.All(cv.positive_int, vol.Range(min=0, max=96))
CHANNEL_SCHEMA = vol.Schema(
    {
        vol.Required('on-off',     default=1): VALID_CHANNEL,
        vol.Optional('level',      default=0): VALID_CHANNEL,
        vol.Optional('color-temp', default=0): VALID_CHANNEL,
        vol.Optional('color',      default=0): VALID_CHANNEL,
    }
)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_CHANNELS):                   CHANNEL_SCHEMA,
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

        light = cylight.create_cylight(config[CONF_MAC],
                                       dinfo[CONF_CHANNELS],
                                       internet=config[CONF_INTERNET],
                                       auto_on=False,
                                       model=None)
        async_add_entities([CYLTekLights(light, dinfo[CONF_NAME])], True)

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
        if dinfo[CONF_ENTITY_TYPE] == Platform.LIGHT:
            light = cylight.create_cylight(config[CONF_MAC],
                                        dinfo[CONF_CHANNELS],
                                        internet=config[CONF_INTERNET],
                                        auto_on=False,
                                        model=None)
            async_add_entities([CYLTekLights(light, dinfo[CONF_NAME])], True)



class CYLTekLights(CYLDeviceEntity, LightEntity):
    """Representation of an CYL-Tek Light."""

    def __init__(self, light: CYLight, name: str="CYLTekLight") -> None:
        """Initialize an CYLTekLight."""
        super().__init__(light.cyl_controller)
        self._light = light
        self._light.alias = name
        
        self._is_on = None
        self._brightness = None

        self._available = True
        self._need_update = True

    @property
    def available(self) -> bool:
        return self._available

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._light.alias

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._light.unique_id


    @property
    def brightness(self):
        """Return the brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._brightness

    @property
    def supported_features(self):
        # Bitfield of features supported by the light entity
        # SUPPORT_BRIGHTNESS = 1
        # SUPPORT_COLOR_TEMP = 2
        # SUPPORT_EFFECT = 4
        # SUPPORT_FLASH = 8
        # SUPPORT_COLOR = 16
        # SUPPORT_TRANSITION = 32
        # SUPPORT_WHITE_VALUE = 128
        SUPPORTED_FEATURES = 0
        if self.support_bright():
            SUPPORTED_FEATURES |= SUPPORT_BRIGHTNESS
        if self.support_rgb():
            SUPPORTED_FEATURES |= SUPPORT_COLOR
        if self.support_color_temp():
            SUPPORTED_FEATURES |= SUPPORT_COLOR_TEMP 
        return SUPPORTED_FEATURES


    def support_bright(self):
        return self._light.channels['level'] != 0

    def support_rgb(self):
        return self._light.channels['color'] != 0

    def support_color_temp(self):
        return self._light.channels['color-temp'] != 0


    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._is_on


    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        # print("async_turn_on")
        if self._available is False:
            return

        if ATTR_BRIGHTNESS not in kwargs:
            if await self._async_try_command(
                f'{self.name}, {self.unique_id} Turning the light on failed.',
                self._light.turn_on
            ):
                self._is_on = True
                self._need_update = False

        else:
            brightness = kwargs.get(ATTR_BRIGHTNESS, 255)

            if brightness is not None:
                if await self._async_try_command(
                    f'{self.name}, {self.unique_id} set_brightness failed.',
                    self._light.set_brightness,
                    brightness
                ):
                    self._brightness = brightness
                    self._need_update = False



    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        # print("async_turn_off")
        if self._available is False:
            return
            
        # if self._is_on is True:
        if await self._async_try_command(
            f'{self.name}, {self.unique_id} Turning the light off failed.',
            self._light.turn_off
        ):
            self._is_on = False
            self._need_update = False


    async def async_update(self) -> None:
        """Fetch new state data for this light.
        This is the only method that should fetch new data for Home Assistant.
        """
        """Synchronise internal state with the actual lights state."""

        if self._need_update is False:
            self._need_update = True
            return

        self._available = await self._async_try_command(
                f'{self.name}, {self.unique_id} light is unavalible !',
                self._light.is_available
            )

        if self._available is False:
            return

        if self._is_on != self._light.get_last_attribute('power'):
            self._is_on = self._light.get_last_attribute('power')
        if self._brightness != self._light.get_last_attribute('brightness'):
            self._brightness = self._light.get_last_attribute('brightness')
