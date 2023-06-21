"""CYL-Tek Humidifier Platform"""
from __future__ import annotations

import logging
from datetime import timedelta
from pprint import pformat

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.humidifier import (DEVICE_CLASS_DEHUMIDIFIER,
                                                 DEVICE_CLASS_HUMIDIFIER,
                                                 PLATFORM_SCHEMA,
                                                 SUPPORT_MODES,
                                                 HumidifierEntity)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_MAC, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import util
from .const import (CONF_CHANNELS, CONF_CONFIG_JSON, CONF_ENTITY_TYPE,
                    CONF_HUMI_ID, CONF_INTERNET, CONF_MODEL, CONF_TYPE,
                    DEFAULT_NAMES, DOMAIN)
from .cyltek import cylhumidifier
from .cyltek.cylhumidifier import CYLHumidifier, HumidifierType
from .entity import CYLDeviceEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = DEFAULT_NAMES["humidifier"]
DEFAULT_MODEL = "Standard"
DEHUMIDIFIER_TYPE = HumidifierType.Dehumidifier
HUMIDIFIER_TYPE = HumidifierType.Humidifier

SCAN_INTERVAL = timedelta(seconds=10)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HUMI_ID):                    cv.string,
        vol.Required(CONF_CONFIG_JSON):                cv.string,
        vol.Optional(CONF_TYPE, default=DEHUMIDIFIER_TYPE): cv.string,
        vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): cv.string,
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

        humi = cylhumidifier.create_cylhumidifier(config[CONF_MAC],
                                                    dinfo[CONF_HUMI_ID],
                                                    dinfo[CONF_CONFIG_JSON],
                                                    {'default': 1},
                                                    internet=config[CONF_INTERNET],
                                                    auto_on=False,
                                                    model=dinfo[CONF_MODEL])
        async_add_entities([CYLTekHumidifier(humi, dinfo[CONF_NAME])], True)
    return True

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
        if dinfo[CONF_ENTITY_TYPE] == Platform.HUMIDIFIER:
            humi = cylhumidifier.create_cylhumidifier(config[CONF_MAC],
                                                        dinfo[CONF_HUMI_ID],
                                                        dinfo[CONF_CONFIG_JSON],
                                                        dinfo[CONF_CHANNELS],
                                                        internet=config[CONF_INTERNET],
                                                        auto_on=False,
                                                        model=dinfo[CONF_MODEL])
            async_add_entities([CYLTekHumidifier(humi, dinfo[CONF_NAME])], True)

class CYLTekHumidifier(CYLDeviceEntity, HumidifierEntity):

    def __init__(self, humi: CYLHumidifier, name: str="CYLTekHumi"):
        """Initialize the humidifier."""
        self._humi = humi
        self._attr_supported_features = SUPPORT_MODES if self._humi.available_modes() else None
    
        self._humidity = None
    
        self._is_on = None
        self._humi.alias = name

        self._attr_mode = None
        self._attr_target_humidity = None
        self._available = True
        self._need_update = True
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        return {
            "temperature" : self._humi.temperature,
            "current_humi" : self._humi.humidity,
        }

    @property
    def available(self) -> bool:
        return self._available

    async def async_update(self) -> None:
        """Fetch new state data for this humi.
        This is the only method that should fetch new data for Home Assistant.
        """
        """Synchronise internal state with the actual humidifier state."""

        if self._need_update is False:
            self._need_update = True
            return

        # self._available = 
        await self._async_try_command(
                f'{self.name}, {self.unique_id} humidifier is unavalible !',
                self._humi.is_available
            )

        if self._available is False:
            return

        self._is_on = self._humi.power != 'OFF'
        self._attr_mode = self._humi.mode
        self._humidity = self._humi.humidity
        self._attr_target_humidity = self._humi.target_humidity

    @property
    def name(self) -> str:
        """Return the display name of this humidifier."""
        return self._humi.alias

    @property
    def unique_id(self):
        """Return the ID of this humidifier."""
        return self._humi.unique_id

    @property
    def mode(self):
        """Return the mode of this humidifier."""
        return self._attr_mode if self.is_on else 'OFF'
  
    @property
    def min_humidity(self):
        """Return the target humidity."""
        return self._humi.min_target_humidity
  
    @property
    def max_humidity(self):
        """Return the target humidity."""
        return self._humi.max_target_humidity
  
    @property
    def available_modes(self):
        return self._humi.available_modes()
  
    @property
    def is_on(self):
        """Return if the dehumidifier is on."""
        return self._is_on
  
    @property
    def device_class(self):
        """Return Device class."""
        if self._humi.type == HumidifierType.Dehumidifier:
            return DEVICE_CLASS_DEHUMIDIFIER
        elif self._humi.type == HumidifierType.Humidifier:
            return DEVICE_CLASS_HUMIDIFIER
        return None
  
    async def async_set_humidity(self, humidity):
        """Set target humidity."""
        if self._available is False:
            return

        if await self._async_try_command(
            f'{self.name}, {self.unique_id} the humidifier setting humidity failed.',
            self._humi.set_target_humidity,
            humidity
        ):
            self._attr_target_humidity = humidity
            self._need_update = False

    async def async_set_mode(self, mode):
        """Set target humidity."""
        if self._available is False:
            return

        if mode == 'OFF':
            await self.async_turn_off()
            return
        else:
            await self.async_turn_on()
            # if mode != self._attr_mode:
            if await self._async_try_command(
                f'{self.name}, {self.unique_id} the humidifier setting mode failed.',
                self._humi.set_mode,
                mode
            ):
                self._attr_mode = mode
                self._need_update = False

          
    async def async_turn_on(self, **kwargs):
        """Turn the device ON."""
        if self._available is False:
            return

        # if self._is_on is False:
        if await self._async_try_command(
            f'{self.name}, {self.unique_id} Turning the humidifier on failed.',
            self._humi.turn_on
        ):
            self._is_on = True
            self._attr_mode = self._humi.mode
            self._need_update = False
  
    async def async_turn_off(self, **kwargs):
        """Turn the device OFF."""
        if self._available is False:
            return
            
        # if self._is_on is True:
        if await self._async_try_command(
            f'{self.name}, {self.unique_id} Turning the humidifier off failed.',
            self._humi.turn_off
        ):
            self._is_on = False
            self._attr_mode = self._humi.mode
            self._need_update = False
  