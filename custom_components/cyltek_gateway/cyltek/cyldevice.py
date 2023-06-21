import logging

from . import util
from .cylcontroller_ex import CYLControllerEx
from .Interface import IPower
from .IOThings import IOThings

_LOGGER = logging.getLogger(__name__)

class CYLOnOffDevice(IOThings, IPower):
    """The Base Class for CYL-Tek on-off device which has 'switch-on' or 'switch-off' abilities"""

    def __init__(
        self,
        cyl_controller: CYLControllerEx,
        channels: dict,
        auto_on=False,
        model=None
    ) -> None:

        super().__init__(cyl_controller, channels)

        self._offline_retry = 0

        self.auto_on = auto_on
        self._model = model

    # @override(IPower)
    @property
    def power(self):
        return self.get_last_attribute('power')

    def ensure_on(self):
        """Turn the device on if it is off."""
        if self.auto_on is False:
            return

        self.update_attributes()

        if self._last_attributes["power"] is False:
            self.turn_on()

    # @override(IOThings)
    def update_attributes(self):
        return self.update_power()

    # @override(IPower)
    def update_power(self):
        channel = self.channels['on-off']
        if channel == 0:
            return False

        target_id = util.make_target_id(self.MAC, channel)
        cmd = util.make_cmd('read-attr', target_id=target_id, attr='on-off-state')
        ret, out = self._cyl_controller.send_cmd(cmd, False)

        if ret is True:
            self._offline_retry = 0

            if out.get('value') != None:
                self._last_attributes['power'] = out['value']
        else:
            _LOGGER.warning(f'{self.alias} {self.unique_id}, Failed to get on-off-state')

            if self._offline_retry >= 3:
                return False

            if isinstance (out, dict) and out.get('code') == 13 and out.get('reason') == 'device offline(unavailable)':
                _LOGGER.warning(f'{self.alias}, {self.MAC} device offline(unavailable) send enumerate !')
                self._cyl_controller.send_cmd(util.make_cmd("enumerate", refresh=True), True)
                self._offline_retry += 1
            else:
                return False

        return True

    # @override(IPower)
    def turn_on(self):
        if self.channels['on-off'] == 0:
            return False

        target_id = util.make_target_id(self.MAC, self.channels['on-off'])
        command = util.make_cmd("switch-on", target_id=target_id)

        ret, out = self._cyl_controller.send_cmd(command, just_send=False)
        if ret:
            self._last_attributes['power'] = True
        return ret

    # @override(IPower)
    def turn_off(self):
        if self.channels['on-off'] == 0:
            return False

        target_id = util.make_target_id(self.MAC, self.channels['on-off'])
        command = util.make_cmd("switch-off", target_id=target_id)

        ret, out = self._cyl_controller.send_cmd(command, just_send=False)
        if ret:
            self._last_attributes['power'] = False
        return ret


