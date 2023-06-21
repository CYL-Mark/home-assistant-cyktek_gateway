import logging
import time

from . import globalvar as gl
from . import util
from .cylcontroller_ex import CYLControllerEx
from .cyldevice import CYLOnOffDevice
from .Interface import IBrightness

_LOGGER = logging.getLogger(__name__)

def create_cylight(MAC, channels, internet="eth0", auto_on=False, model=None):
    controllers_map = gl.get_controllers_map()
    if controllers_map.get(MAC) is None:
        controllers_map[MAC] = CYLControllerEx(MAC, internet=internet)

    return CYLight(controllers_map[MAC], channels, auto_on, model)


class CYLight(CYLOnOffDevice, IBrightness):

    def __init__(
        self,
        cyl_controller: CYLControllerEx,
        channels: dict,
        auto_on=False,
        model=None
    ) -> None:

        super().__init__(cyl_controller, channels, auto_on, model)
        self._unique_id = util.make_unique_id("light", cyl_controller.MAC, channels.values())
        self._target_level_update = True

        if channel := self.channels['level']:
            if self._cyl_controller.capabilities.get("code") == 0:
                device_capabilities = {d['id']: d for d in self._cyl_controller.capabilities["devices"]}
                target_id = util.make_target_id(self.MAC, channel)
                attrs = [a['attr'] for a in device_capabilities[target_id]["attrs"]]
                if 'target-level' not in attrs:
                    self._target_level_update = False

    # @override(CYLOnOffDevice)
    def update_attributes(self):
        return super().update_attributes() and self.update_brightness()

    # @override(IBrightness)
    @property
    def brightness(self):
        return self.get_last_attribute('brightness')

    # @override(IBrightness)
    def update_brightness(self):
        channel = self.channels['level']
        if channel <= 0:
            return True

        target_id = util.make_target_id(self.MAC, channel)
        attr = 'target-level' if self._target_level_update else 'current-level'
        cmd = util.make_cmd('read-attr', target_id=target_id, attr=attr)
        ret, out = self._cyl_controller.send_cmd(cmd, False)

        if ret is True:
            self._offline_retry = 0
            if out.get('value') != None:
                self._last_attributes['brightness'] = out['value']
        else:
            _LOGGER.warning(f'{self.alias}, Failed to get {attr}')

            if self._offline_retry >= 3:
                return False

            if isinstance (out, dict) and out.get('code') == 13 and out.get('reason') == 'device offline(unavailable)':
                _LOGGER.warning(f'{self.alias}, {self.MAC} device offline(unavailable) send enumerate !')
                self._cyl_controller.send_cmd(util.make_cmd("enumerate", refresh=True), True)
                self._offline_retry += 1
            else:
                # if attr == 'target-level':
                #     if isinstance (out, dict) and out.get('code') == 15 and out.get('reason') == 'unsupported attribute':
                #         self._target_level_update = False
                return False

        _LOGGER.debug(f'{self.alias}, {self.unique_id}: {self.last_attributes}')
        return True

    # @override(IBrightness)
    def set_brightness(self, intensity: int):
        if self.channels['level'] == 0:
            return False

        target_id = util.make_target_id(self.MAC, self.channels['level'])
        command = util.make_cmd("level-move-to", target_id=target_id, level=intensity, duration=50)
        ret, out = self._cyl_controller.send_cmd(command, just_send=False)
        if ret:
            self._last_attributes['brightness'] = intensity
        return ret

