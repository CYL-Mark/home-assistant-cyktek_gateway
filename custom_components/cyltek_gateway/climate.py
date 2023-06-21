"""CYL-Tek Climate Platform"""
from __future__ import annotations

import logging
from datetime import timedelta
from pprint import pformat

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.climate import (ATTR_FAN_MODE, ATTR_HVAC_MODE,
                                              ATTR_PRESET_MODE,
                                              ATTR_SWING_MODE,
                                              DEFAULT_MAX_TEMP,
                                              DEFAULT_MIN_TEMP,
                                              ENTITY_ID_FORMAT, HVAC_MODES,
                                              PLATFORM_SCHEMA, PRESET_AWAY,
                                              PRESET_BOOST, PRESET_NONE,
                                              ClimateEntity,
                                              ClimateEntityFeature, HVACMode)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (ATTR_TEMPERATURE, CONF_DEVICES, CONF_MAC,
                                 CONF_NAME, PRECISION_WHOLE, TEMP_CELSIUS,
                                 TEMP_FAHRENHEIT, Platform)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import util
from .const import (CONF_AC_ID, CONF_CHANNELS, CONF_CONFIG_JSON,
                    CONF_ENTITY_TYPE, CONF_INTERNET, CONF_MODEL, DEFAULT_NAMES,
                    DOMAIN)
from .cyltek import cylclimate
from .cyltek.cylclimate import CYLClimate
from .entity import CYLDeviceEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = DEFAULT_NAMES["climate"]
DEFAULT_MODEL = "Standard"
CONF_TYPE = 'type'

SCAN_INTERVAL = timedelta(seconds=10)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AC_ID):                       cv.positive_int,
        vol.Required(CONF_CONFIG_JSON):                 cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME):  cv.string,
        vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MAC):                         vol.All(cv.string, util.MAC()),
        vol.Optional(CONF_INTERNET, default='eth0'):    cv.string,
        vol.Required(CONF_DEVICES):                     vol.All(cv.ensure_list, [DEVICE_SCHEMA]),
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

        ac = cylclimate.create_cylclimate(config[CONF_MAC],
                                    dinfo[CONF_AC_ID],
                                    dinfo[CONF_CONFIG_JSON],
                                    {'default': 1},
                                    internet=config[CONF_INTERNET],
                                    auto_on=False,
                                    model=dinfo[CONF_MODEL])
        async_add_entities([CYLTekClimate(ac, dinfo[CONF_NAME])], True)
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
        if dinfo[CONF_ENTITY_TYPE] == Platform.CLIMATE:
            ac = cylclimate.create_cylclimate(config[CONF_MAC],
                                        dinfo[CONF_AC_ID],
                                        dinfo[CONF_CONFIG_JSON],
                                        dinfo[CONF_CHANNELS],
                                        internet=config[CONF_INTERNET],
                                        auto_on=False,
                                        model=dinfo[CONF_MODEL])
            async_add_entities([CYLTekClimate(ac, dinfo[CONF_NAME])], True)

class CYLTekClimate(CYLDeviceEntity, ClimateEntity):

    def __init__(self, climate, name: str="CYLTekHumi"):
        """Initialize the humidifier."""
        self._climate = climate
        self._available = True
        self._need_update = True
    
        self._current_humidity = None
        self._current_temperature = None

        self._pw_state = None
        self._is_on = None
        self._climate.alias = name

        self._swing_mode = None
        self._fan_mode = None
        self._preset_mode = None
        self._hvac_mode = None
        self._target_temperature = None
        self._attr_temperature_unit = TEMP_CELSIUS if self._climate.temperature_unit == "C" else TEMP_FAHRENHEIT

        self._attr_fan_modes = None
        self._attr_swing_modes = None
        # self._attr_preset_modes = PRESET_NONE

        valid_hvac_modes = [x for x in self._climate.available_modes() if x in HVAC_MODES]
        self._operation_modes = [HVACMode.OFF] + valid_hvac_modes

        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

        if callable(getattr(self._climate ,'set_fan_mode')):
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_modes = self._climate.available_fan_modes()
        # if callable(getattr(self._climate ,'set_swing_mode')):
        #     self._attr_supported_features |= ClimateEntityFeature.SWING_MODE
        #     self._attr_swing_modes = self._climate.available_swing_modes()

        # if (self._climate.support_away_mode
        #     or self._climate.support_advanced_modes
        # ):
        #     self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE

    @property
    def available(self) -> bool:
        return self._available

    async def async_update(self):

        if self._need_update is False:
            self._need_update = True
            return

        self._available = await self._async_try_command(
                f'{self.name}, {self.unique_id} climate is unavalible !',
                self._climate.is_available
            )
            
        if self._available is False:
            return

        if self._pw_state != self._climate.get_last_attribute('power'):
            self._pw_state = self._climate.get_last_attribute('power')
        self._is_on = self._climate.get_last_attribute('power') != 'OFF'

        if self._hvac_mode != self._climate.get_last_attribute('mode'):
            self._hvac_mode = self._climate.get_last_attribute('mode')
        if self._fan_mode != self._climate.get_last_attribute('fan_mode'):
            self._fan_mode = self._climate.get_last_attribute('fan_mode')
        if self._swing_mode != self._climate.get_last_attribute('swing_mode'):
            self._swing_mode = self._climate.get_last_attribute('swing_mode')

        unit = "C" if self._attr_temperature_unit == TEMP_CELSIUS else "F"
        if self._current_temperature != self._climate.get_last_attribute(f'temperature_{unit}'):
            self._current_temperature = self._climate.get_last_attribute(f'temperature_{unit}')
        if self._target_temperature != self._climate.get_last_attribute('target_temperature'):
            self._target_temperature = self._climate.get_last_attribute('target_temperature')


        _LOGGER.debug(f'{self.name}, {self.unique_id}: {self._climate.get_last_attribute("power")}, {self._pw_state}, {self._is_on}')
    # @property
    # def extra_state_attributes(self):
    #     """Return the extra state attributes of the device."""
    #     return self._state_attrs

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._climate.alias

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._climate.unique_id

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return self._operation_modes

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        if self.is_on:
            return self._hvac_mode
        return HVACMode.OFF

    @property
    def swing_modes(self):
        """Return the swing modes currently supported for this device."""
        return self._attr_swing_modes

    @property
    def swing_mode(self):
        """Return the current swing mode."""
        return self._swing_mode

    # @property
    # def preset_modes(self):
    #     """Return a list of available preset modes."""
    #     return 

    # @property
    # def preset_mode(self):
    #     """Return the current preset mode, e.g., home, away, temp."""
    #     return self._preset_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._climate.available_fan_modes()

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._fan_mode

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def max_temp(self):
        """Return the polling state."""
        return self._climate.max_target_temperature
        
    @property
    def min_temp(self):
        """Return the polling state."""
        return self._climate.min_target_temperature

    @property
    def target_temperature_low(self):
        """Return the polling state."""
        return self._climate.min_target_temperature
        
    @property
    def target_temperature_high(self):
        """Return the polling state."""
        return self._climate.max_target_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._climate.target_temperature_step

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._current_humidity
        
    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._attr_supported_features
  
    @property
    def is_on(self):
        """Return if the dehumidifier is on."""
        return self._is_on
  
    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if self._available is False:
            return

        # hvac_mode = kwargs.get(ATTR_HVAC_MODE)  
        temperature = kwargs.get(ATTR_TEMPERATURE)

        # if hvac_mode:
        #     await self.async_set_hvac_mode(hvac_mode)
        
        if await self._async_try_command(
            f'{self.name}, {self.unique_id} set_temperature failed.',
            self._climate.set_target_temperature,
            temperature
        ):
            self._target_temperature = temperature
            self._need_update = False

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        print(hvac_mode)
        if self._available is False:
            return

        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return
        else:
            await self.async_turn_on()
            # if hvac_mode != self._hvac_mode:
            if await self._async_try_command(
                f'{self.name}, {self.unique_id} the climate setting mode failed.',
                self._climate.set_mode,
                hvac_mode
            ):
                self._hvac_mode = hvac_mode
                self._need_update = False

    # async def async_set_preset_mode(self, preset_mode):
    #     """Set target humidity."""
    #     _LOGGER.debug('set_mode')

    #     if preset_mode == self.preset_modes[OperationMode.OFF]:
    #         self.async_turn_off()
    #         return
    #     else:
    #         self.async_turn_on()
    #         if preset_mode != self._preset_mode:
    #             if await self._async_try_command(
    #                 f'{self.name}, {self.unique_id} async_set_mode failed.',
    #                 self._climate.set_mode,
    #                 preset_mode
    #             ):
    #                 self._preset_mode = preset_mode
    #                 print(self._preset_mode)

          
    async def async_turn_on(self, **kwargs):
        """Turn the device ON."""
        if self._available is False:
            return

        # if self._is_on is False:
        if await self._async_try_command(
            f'{self.name}, {self.unique_id} Turning the climate on failed.',
            self._climate.turn_on
        ):
            self._is_on = True
            if self._climate.mode in HVAC_MODES:
                self._hvac_mode = self._climate.mode
            self._need_update = False
  
    async def async_turn_off(self, **kwargs):
        """Turn the device OFF."""
        if self._available is False:
            return
            
        # if self._is_on is True:
        if await self._async_try_command(
            f'{self.name}, {self.unique_id} Turning the climate off failed.',
            self._climate.turn_off
        ):
            self._is_on = False
            self._hvac_mode = HVACMode.OFF
            self._need_update = False

    async def async_set_fan_mode(self, fan_mode: str):
        """Set new target fan mode."""
        if self._available is False:
            return

        # if fan_mode != self._fan_mode:
        if await self._async_try_command(
            f'{self.name}, {self.unique_id} async_set_fan_mode failed.',
            self._climate.set_fan_mode,
            fan_mode
        ):
            self._fan_mode = fan_mode
            self._need_update = False
  