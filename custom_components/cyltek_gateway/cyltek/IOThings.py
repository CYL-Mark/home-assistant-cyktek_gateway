import logging
from abc import ABC, abstractmethod

from . import util
from .cylcontroller_ex import CYLControllerEx

_LOGGER = logging.getLogger(__name__)

class IOThings(ABC):
    """The Base Class for CYL-Tek IOT device"""
    MAX_UNAVAILABLE_TIMES = 3

    def __init__(
        self,
        cyl_controller: CYLControllerEx,
        capability_channels: dict
    ) -> None:

        self._cyl_controller = cyl_controller
        self._is_available = True
        self._unavailable_counter = 0
        self.alias = None
        self._unique_id = None

        self._capability_channels = capability_channels
        self._last_attributes = {}  # The last set of attributes we've seen.

        self._notification_socket = None  # The socket to get update notifications
        self._is_listening = False  # Indicate if we are listening

    @abstractmethod
    def update_attributes(self):
        pass

    @property
    def MAC(self):
        return self._cyl_controller.MAC

    @property
    def host(self):
        return self._cyl_controller.host

    @property
    def cyl_controller(self):
        return self._cyl_controller

    @property
    def channels(self):
        return self._capability_channels

    @property
    def unique_id(self):
        if self._unique_id is None:
            self._unique_id = util.make_unique_id(None, self.MAC, self.channels.values())
        return self._unique_id

    @property
    def last_attributes(self):
        """
        This might potentially be out of date, as there's no background listener
        for the iot's notifications. 
        Call update_attributes() to update it.
        """
        return self._last_attributes

    def is_available(self):
        """Check is_available iot."""
        msg = 'Yes'
        ## check connection
        if self._cyl_controller.try_connect() is False:
            self._unavailable_counter = 4 if self._unavailable_counter >= IOThings.MAX_UNAVAILABLE_TIMES else (self._unavailable_counter + 1)
            msg = f'Failed to connected'
        else:
            ## update attributes data
            if self.update_attributes() is False:
                self._unavailable_counter = 4 if self._unavailable_counter >= IOThings.MAX_UNAVAILABLE_TIMES else (self._unavailable_counter + 1)
                msg = f'Failed to update_attributes'
            else:
                self._unavailable_counter = 0

        # pre_status = self._is_available
        self._is_available = False if self._unavailable_counter > IOThings.MAX_UNAVAILABLE_TIMES else True
        # if pre_status != self._is_available:
            # _LOGGER.warning(f'Check is_available: {msg} ({self.alias}, {self.unique_id})')
        if not self._is_available:
            _LOGGER.error(f'Check is_available: {msg} ({self.alias}, {self.unique_id})')
            ip_type = '4' if util.is_valid_IP(self._cyl_controller.host) else '6'
            ret, out = util.do_command(f"ping -{ip_type} -c 3 -W 1 {self._cyl_controller.host}")
            _LOGGER.warning(f'{self._cyl_controller.host}, {self.alias}, PING: ret: {ret}, out: {out}')
        return self._is_available

    def get_last_attribute(self, attr):
        return self._last_attributes.get(attr)

    def _set_last_attributes(self, attributes, update=True):
        
        if update:
            self._last_attributes.update(attributes)
