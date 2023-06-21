"""Support for Xiaomi Yeelight WiFi color bulb."""
from __future__ import annotations

import logging
from functools import partial

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, Entity

from . import util
from .const import DOMAIN, MANUFACTURER_NAME
from .cyltek.cylcontroller_ex import CYLControllerEx
from .cyltek.cylexception import CYLTekException

_LOGGER = logging.getLogger(__name__)

class CYLDeviceEntity(Entity):
    """Represents single CYLDevice entity."""

    def __init__(self, cyl_device: CYLControllerEx) -> None:
        """Initialize the device."""
        self._device = cyl_device
        self._attr_device_info = self.generate_device_info()

    def generate_device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return DeviceInfo(
            connections={("IPv6", self._device.host)},
            identifiers={(DOMAIN, self._device.MAC)},
            manufacturer=MANUFACTURER_NAME,
            model=self._device.model,
            name=self._device.alias,
            sw_version=self._device.config.get("server-version"),
            # configuration_url="",
        )

    async def _async_try_command(self, msg_failed, func, *args, **kwargs):
        """Call a cyl device command handling error messages."""
        try:
            result = await self.hass.async_add_executor_job(
                partial(func, *args, **kwargs)
            )
            if result is False:
                _LOGGER.warning(msg_failed)  

        except CYLTekException as exc:
            _LOGGER.error(msg_failed, exc)
            return False

        return result
