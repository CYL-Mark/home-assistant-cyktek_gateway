import logging
import os
import time

from . import COMPONENT_ABS_DIR
from . import globalvar as gl
from . import util
from .cylcontroller_ex import CYLControllerEx
from .enums import StrEnum
from .IOThings import IOThings

_LOGGER = logging.getLogger(__name__)

def create_cylcover(MAC, config_name, channels, internet="eth0", auto_on=False, model=None):
    controllers_map = gl.get_controllers_map()
    if controllers_map.get(MAC) is None:
        controllers_map[MAC] = CYLControllerEx(MAC, internet=internet)

    json_subdir = os.path.join('config', 'covers')
    json_absdir = os.path.join(COMPONENT_ABS_DIR, json_subdir)

    if not os.path.isdir(json_absdir):
        os.makedirs(json_absdir)

    json_filename = f'{config_name}.json'
    json_path = os.path.join(json_absdir, json_filename)

    if (config := util.load_config_json(json_path)):
        return CYLCover(controllers_map[MAC], config, channels, auto_on, model)
    
    return None

class CoverState(StrEnum):
    """Type of Humidifier to control."""
    Open = 'opened'
    Closed = 'closed'
    Opening = 'opening'
    Closing = 'closing'


class CoverType(StrEnum):
    """Type of Cover to control."""
    Awning = 'awning'
    Blind = 'blind'
    Curtain = 'curtain'
    Damper = 'damper'
    Door = 'door'
    Garage = 'garage'
    Gate = 'gate'
    Shade = 'shade'
    Shutter = 'shutter'
    Window = 'window'


class SignalGenerator():
    
    def __init__(
            self,
            cyl_controller: CYLControllerEx,
            channels: dict
        ) -> None:
        self._cyl_controller = cyl_controller
        self._channels = channels
        self.signal_dict = {
            "Hight":self.Signal_Hight,
            "Low":  self.Signal_Low,
            "Sleep":self.Sleep
        }

    def Signal_Hight(self, signal_info):
        channel = self._channels.get(signal_info.get("channel_key"))
        if channel is None:
            return False
        target_id = util.make_target_id(self._cyl_controller.MAC, channel)
        command = util.make_cmd("switch-on", target_id=target_id)
        ret_on, out = self._cyl_controller.send_cmd(command, just_send=False)
        return ret_on

    def Signal_Low(self, signal_info):
        channel = self._channels.get(signal_info.get("channel_key"))
        if channel is None:
            return False
        target_id = util.make_target_id(self._cyl_controller.MAC, channel)
        command = util.make_cmd("switch-off", target_id=target_id)
        ret_off, out = self._cyl_controller.send_cmd(command, just_send=False)
        return ret_off

    def Sleep(self, signal_info):
        time.sleep(float(signal_info.get("time_us"))/1000)
        return True

    def __call__(self, operation_key, signals):
        ret = True
        for s in signals:
            if self.signal_dict.get(s.get("signal")) is None:
                continue
            else:
                if s.get("channel_key") is None:
                    s["channel_key"] = operation_key
                ret &= self.signal_dict.get(s.get("signal"))(s)
        return ret

class CYLCover(IOThings):

    def __init__(
        self,
        cyl_controller: CYLControllerEx,
        config: dict,
        channels: dict,
        auto_on=False,
        model=None
    ) -> None:

        super().__init__(cyl_controller, channels)
        self._unique_id = util.make_unique_id("cover", cyl_controller.MAC, channels.values())

        self._signal_generator = SignalGenerator(cyl_controller, channels)
        self._config = config

        self._offline_retry = 0

        self.auto_on = auto_on
        self._model = model
        self._last_attributes['state'] = None

    # @override(IOThings)
    def update_attributes(self):
        return self.update_position()

    @property
    def position(self):
        return self.get_last_attribute('position')

    @property
    def state(self):
        return self.get_last_attribute('state')

    def open(self):
        """Open the cover."""
        if self.channels['open'] == 0:
            return False

        signals = self._config["operation_signals"]["open"]
        ret = self._signal_generator('open', signals)
        if ret:
            self._last_attributes['state'] = CoverState.Opening
        return ret

    def close(self):
        """Close cover."""
        if self.channels['close'] == 0:
            return False

        signals = self._config["operation_signals"]["close"]
        ret = self._signal_generator('close', signals)
        if ret:
            self._last_attributes['state'] = CoverState.Closing
        return ret

    def stop(self):
        """Stop the cover."""
        if self.channels['stop'] == 0:
            return False

        signals = self._config["operation_signals"]["stop"]
        ret = self._signal_generator('stop', signals)
        if ret:
            self._last_attributes['state'] = None
        return ret

    def update_position(self):
        channel = self.channels['level']
        if channel <= 0:
            return True

        target_id = util.make_target_id(self.MAC, channel)
        cmd = util.make_cmd('read-attr', target_id=target_id, attr='current-level')
        ret, out = self._cyl_controller.send_cmd(cmd, False)

        if ret is True:
            self._offline_retry = 0
            if out.get('value') != None:
                self._last_attributes['position'] = out['value']
        else:
            _LOGGER.warning(f'{self.alias}, Failed to get current-level')

            if self._offline_retry >= 3:
                return False

            if isinstance (out, dict) and out.get('code') == 13 and out.get('reason') == 'device offline(unavailable)':
                _LOGGER.warning(f'{self.alias}, {self.MAC} device offline(unavailable) send enumerate !')
                self._cyl_controller.send_cmd(util.make_cmd("enumerate", refresh=True), True)
                self._offline_retry += 1
            else:
                return False
                
        return True

    def set_position(self, intensity: int):
        if self.channels['level'] == 0:
            return False

        target_id = util.make_target_id(self.MAC, self.channels['level'])
        command = util.make_cmd("level-move-to", target_id=target_id, level=intensity, duration=10)
        ret, out = self._cyl_controller.send_cmd(command)
        if ret:
            self._last_attributes['position'] = intensity
        return ret


