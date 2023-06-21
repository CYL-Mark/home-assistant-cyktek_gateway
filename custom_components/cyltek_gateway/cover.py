"""Support for CYL-Tek Curtain."""
from __future__ import annotations

from pprint import pformat
from typing import Any, Dict, Optional

import homeassistant.helpers.config_validation as cv
# pylint: disable=import-error, no-member
import voluptuous as vol
# Import the device class
from homeassistant.components.cover import (ATTR_POSITION, DEVICE_CLASS_AWNING,
                                            DEVICE_CLASS_BLIND,
                                            DEVICE_CLASS_CURTAIN,
                                            DEVICE_CLASS_DAMPER,
                                            DEVICE_CLASS_DOOR,
                                            DEVICE_CLASS_GARAGE,
                                            DEVICE_CLASS_GATE,
                                            DEVICE_CLASS_SHADE,
                                            DEVICE_CLASS_SHUTTER,
                                            DEVICE_CLASS_WINDOW,
                                            PLATFORM_SCHEMA, SUPPORT_CLOSE,
                                            SUPPORT_OPEN, SUPPORT_SET_POSITION,
                                            SUPPORT_STOP, CoverEntity)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_DEVICES, CONF_MAC, CONF_NAME,
                                 STATE_CLOSED, STATE_CLOSING, STATE_OPEN,
                                 STATE_OPENING, Platform)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import util
from .const import (CONF_CHANNELS, CONF_CONFIG_JSON, CONF_ENTITY_TYPE,
                    CONF_INTERNET, CONF_TYPE, DEFAULT_NAMES, DOMAIN)
from .cyltek import cylcover
from .cyltek.cylcover import CoverState, CoverType, CYLCover
from .entity import CYLDeviceEntity

SWITCHBOT_WAIT_SEC = 10 #seconds
BLE_RETRY_COUNT = 5

# Initialize the logger
import logging

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = DEFAULT_NAMES["cover"]
CURTAIN_TYPE = CoverType.Curtain

VALID_CHANNEL = vol.All(cv.positive_int, vol.Range(min=0, max=96))
CHANNEL_SCHEMA = vol.Schema(
    {
        vol.Required('open',     default=1):  VALID_CHANNEL,
        vol.Required('close',    default=2):  VALID_CHANNEL,
        vol.Optional('stop',     default=0):  VALID_CHANNEL,
        vol.Optional('level',    default=0):  VALID_CHANNEL,
    }
)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CHANNELS):                   CHANNEL_SCHEMA,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TYPE, default=CURTAIN_TYPE): cv.string,
        vol.Required(CONF_CONFIG_JSON):                cv.string,
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

        cover = cylcover.create_cylcover(config[CONF_MAC],
                                       dinfo[CONF_CONFIG_JSON],
                                       dinfo[CONF_CHANNELS],
                                       internet=config[CONF_INTERNET],
                                       auto_on=False,
                                       model=None)
        async_add_entities([CYLTekCovers(cover, dinfo[CONF_TYPE], dinfo[CONF_NAME])], True)


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
        if dinfo[CONF_ENTITY_TYPE] == Platform.COVER:
            cover = cylcover.create_cylcover(config[CONF_MAC],
                                        dinfo[CONF_CONFIG_JSON],
                                        dinfo[CONF_CHANNELS],
                                        internet=config[CONF_INTERNET],
                                        auto_on=False,
                                        model=None)
            async_add_entities([CYLTekCovers(cover, dinfo[CONF_TYPE], dinfo[CONF_NAME])], True)

class CYLTekCovers(CYLDeviceEntity, CoverEntity):
    """Representation of a CYL-Tek Cover."""

    state_map = {
        CoverState.Open : STATE_OPEN,
        CoverState.Closed : STATE_CLOSED,
        CoverState.Opening : STATE_OPENING,
        CoverState.Closing : STATE_CLOSING,
    }

    device_map = {
        CoverType.Awning    : DEVICE_CLASS_AWNING,
        CoverType.Blind     : DEVICE_CLASS_BLIND,
        CoverType.Curtain   : DEVICE_CLASS_CURTAIN,
        CoverType.Damper    : DEVICE_CLASS_DAMPER,
        CoverType.Door      : DEVICE_CLASS_DOOR,
        CoverType.Garage    : DEVICE_CLASS_GARAGE,
        CoverType.Gate      : DEVICE_CLASS_GATE,
        CoverType.Shade     : DEVICE_CLASS_SHADE,
        CoverType.Shutter   : DEVICE_CLASS_SHUTTER,
        CoverType.Window    : DEVICE_CLASS_WINDOW,
    }

    def __init__(self, cover: CYLCover, type: str, name: str="CYLTekCover") -> None:
        """Initialize an CYLTekCover."""
        super().__init__(cover.cyl_controller)
        self._cover = cover
        self._cover.alias = name
        self._type = type
        self._state = None
        self._current_position = None

        self._available = True

    @property
    def available(self) -> bool:
        return self._available

    async def async_update(self) -> None:
        """Fetch new state data for this cover.
        This is the only method that should fetch new data for Home Assistant.
        """
        """Synchronise internal state with the actual cover state."""

        self._available = await self._async_try_command(
                f'{self.name}, {self.unique_id} is unavalible !',
                self._cover.is_available
            )

        if self._available is False:
            return

        self._state = self._cover.state
        self._current_position = self._cover.position

    @property
    def name(self) -> str:
        """Return the display name of this cover."""
        return self._cover.alias

    @property
    def unique_id(self):
        """Return the ID of this cover."""
        return self._cover.unique_id

    @property
    def device_class(self) -> Optional[str]:
        return self.device_map.get(self._type)

    @property
    def current_cover_position(self):
        return self._current_position

    @property
    def is_opening(self):
        return self._state == STATE_OPENING

    @property
    def is_closing(self):
        return self._state == STATE_CLOSING

    @property
    def is_closed(self):
        return self._current_position == 0

    @property
    def state(self):
        return self._state

    @property
    def supported_features(self):
        # Bitfield of features supported by the cover entity
        SUPPORTED_FEATURES = 0
        if self.support_open():
            SUPPORTED_FEATURES |= SUPPORT_OPEN
        if self.support_close():
            SUPPORTED_FEATURES |= SUPPORT_CLOSE
        if self.support_stop():
            SUPPORTED_FEATURES |= SUPPORT_STOP
        if self.support_set_position():
            SUPPORTED_FEATURES |= SUPPORT_SET_POSITION
        return SUPPORTED_FEATURES


    def support_open(self):
        return self._cover.channels['open'] != 0

    def support_close(self):
        return self._cover.channels['close'] != 0

    def support_stop(self):
        return self._cover.channels['stop'] != 0

    def support_set_position(self):
        return self._cover.channels['level'] != 0


    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        if self._available is False:
            return
            
        if self._state != CoverState.Opening:
            if await self._async_try_command(
                f'{self.name}, {self.unique_id} Turning the cover off failed.',
                self._cover.open
            ):
                self._state = self._cover.state

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        if self._available is False:
            return
            
        if self._state != CoverState.Closing:
            if await self._async_try_command(
                f'{self.name}, {self.unique_id} Turning the cover off failed.',
                self._cover.close
            ):
                self._state = self._cover.state

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        if self._available is False:
            return
            
        if self._state == CoverState.Closing or self._state == CoverState.Opening:
            if await self._async_try_command(
                f'{self.name}, {self.unique_id} Turning the cover off failed.',
                self._cover.stop
            ):
                self._state = self._cover.state

    async def async_set_cover_position(self, **kwargs):
        if self._available is False:
            return

        percent = kwargs[ATTR_POSITION]
        if await self._async_try_command(
            f'{self.name}, {self.unique_id} the cover setting position failed.',
            self._cover.set_position,
            percent
        ):
            self._current_position = percent


