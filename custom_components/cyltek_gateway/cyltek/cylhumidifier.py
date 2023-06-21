import logging
import os

from . import COMPONENT_ABS_DIR
from . import globalvar as gl
from . import util
from .cylcontroller_ex import CYLControllerEx
from .enums import StrEnum
from .Interface import (IFanMode, IHumidity, IMode, IPower, ITargetHumidity,
                        ITemperature)
from .IOThings import IOThings

_LOGGER = logging.getLogger(__name__)

def create_cylhumidifier(MAC, Humi_id, config_name, channels, internet="eth0", auto_on=False, model=None):
    controllers_map = gl.get_controllers_map()
    if controllers_map.get(MAC) is None:
        controllers_map[MAC] = CYLControllerEx(MAC, internet=internet)

    json_subdir = os.path.join('config', 'humidifiers')
    json_absdir = os.path.join(COMPONENT_ABS_DIR, json_subdir)

    if not os.path.isdir(json_absdir):
        os.makedirs(json_absdir)

    json_filename = f'{config_name}.json'
    json_path = os.path.join(json_absdir, json_filename)

    if (config := util.load_config_json(json_path)):
        return CYLHumidifier(controllers_map[MAC], Humi_id, config, channels, auto_on, model)
    
    return None

class HumidifierType(StrEnum):
    """Type of Humidifier to control."""
    Humidifier = 'humidifier'
    Dehumidifier = 'dehumidifier'

class CYLHumidifier(IOThings, IPower, IMode, IFanMode, IHumidity, ITargetHumidity, ITemperature):

    def __init__(
        self,
        cyl_controller: CYLControllerEx,
        Humi_id: str,
        config: dict,
        channels: dict = {'default': 1},
        auto_on=False,
        model="STANDARD", # INDUSTRIAL 
    ) -> None:
        super().__init__(cyl_controller, channels)
        self._unique_id = util.make_unique_id("humidifier", cyl_controller.MAC, channels.values(), Humi_id=Humi_id)

        self._Humi_id = Humi_id
        self._offline_retry = 0

        self.auto_on = auto_on
        self._model = model.upper()

        self.operation_modes = config.get('operation_modes')
        self.fan_modes = config.get('fan_modes')

        self._type = config.get('type')
        self._Humi_range = config.get('humidity_range').get(self._model)
        self._manufacturer = config.get('manufacturer')
        self._power_status = config.get('power_status')
        self._Temp_unit = str(config.get('temperature_unit')).upper()

    def ensure_on(self):
        """Turn the humidifier on if it is off."""
        if self.auto_on is False:
            return

        self.update_attributes()

        if self._last_attributes["mode"] == self.operation_modes.get('OFF'):
            self.set_mode('AUTO')

    @property
    def Humi_id(self):
        return self._Humi_id

    @property
    def type(self):
        return self._type

    @property
    def model(self):
        return self._model

    # @override(IPower)
    def update_power(self):
        if self.channels['default'] == 0:
            return False
        
        ret, out = self.supply_raw_data(util.ascii_to_decimal(f'{self.Humi_id.upper()} POWER\n'))

        if ret:
            data = util.decimal_to_ascii(out['response-raw-data'])
            token = data.strip().split(' ')
            token.pop(0)
            token_str = ' '.join(token)
            if token_str in self._power_status:
                self._last_attributes['power'] = token_str
            else:
                ret = False

        return ret

    # @override(IPower)
    def turn_on(self):
        return self.set_mode('AUTO')

    # @override(IPower)
    def turn_off(self):
        return self.set_mode("OFF")

    # @override(IPower)
    @property
    def power(self):
        return self.get_last_attribute('power')

    # @override(IMode)
    def available_modes(self):
        if self.operation_modes:
            return list(self.operation_modes.keys())
        return None

    # @override(IMode)
    def set_mode(self, mode):
        # 0=OFF, 1=AUTO, 2=MANUAL, 3=AIR PURIFY
        if self.channels['default'] == 0:
            return False

        target_id = util.make_target_id(self.MAC, self.channels['default'])
        command = util.make_cmd("altrason-cmd", target_id=target_id, action="set-mode", id=self._Humi_id, value=self.operation_modes.get(mode))
        print(command)
        ret, out = self._cyl_controller.send_cmd(command)
        print(ret, out)
        if ret:
            self._last_attributes['mode'] = mode
        return ret

    # @override(IMode)
    def update_mode(self):
        if self.channels['default'] == 0:
            return False
        
        ret, out = self.supply_raw_data(util.ascii_to_decimal(f'{self.Humi_id.upper()} MODE\n'))
        if ret:
            data = util.decimal_to_ascii(out['response-raw-data'])
            token = data.strip().split(' ')
            token.pop(0)
            token_str = ' '.join(token)
            if token_str in self.operation_modes:
                self._last_attributes['mode'] = token_str
            else:
                ret = False

        return ret

    # @override(IMode)
    @property
    def mode(self):
        return self.get_last_attribute('mode')

    # @override(IFanMode)
    def available_fan_modes(self):
        if self.fan_modes:
            return list(self.fan_modes.keys())
        return None

    # @override(IFanMode)
    def set_fan_mode(self, mode):
        # 0=SILENT, 1=NORMAL, 2=TURBO
        if self.channels['default'] == 0:
            return False

        target_id = util.make_target_id(self.MAC, self.channels['default'])
        command = util.make_cmd("altrason-cmd", target_id=target_id, action="set-blower-speed", id=self._Humi_id, value=self.fan_modes.get(mode))
        print(command)
        ret, out = self._cyl_controller.send_cmd(command)
        print(ret, out)
        if ret:
            self._last_attributes['fan_mode'] = mode
        return ret

    # @override(IFanMode)
    def update_fan_mode(self):
        if self.channels['default'] == 0:
            return False
        
        ret, out = self.supply_raw_data(util.ascii_to_decimal(f'{self.Humi_id.upper()} BLOWER\n'))

        if ret:
            data = util.decimal_to_ascii(out['response-raw-data'])
            token = data.strip().split(' ')
            token.pop(0)
            token_str = ' '.join(token)
            if token_str in self.fan_modes:
                self._last_attributes['fan_mode'] = token_str
            else:
                ret = False

        return ret

    # @override(IFanMode)
    @property
    def fan_mode(self):
        return self.get_last_attribute('fan_mode')

    # @override(ITargetHumidity)
    def update_target_humidity(self):
        if self.channels['default'] == 0:
            return False
        
        ret, out = self.supply_raw_data(util.ascii_to_decimal(f'{self.Humi_id.upper()} TARGET\n'))

        if ret:
            data = util.decimal_to_ascii(out['response-raw-data'])
            float_list = util.extract_Numerical_value(data)
            if len(float_list):
                self._last_attributes['target_humidity'] = int(float_list[0])

        return ret

    # @override(ITargetHumidity)
    def set_target_humidity(self, intensity: int):
        if self.channels['default'] == 0:
            return False

        target_id = util.make_target_id(self.MAC, self.channels['default'])
        command = util.make_cmd("altrason-cmd", target_id=target_id, action="set-target-humidity", id=self._Humi_id, value=intensity)
        ret, out = self._cyl_controller.send_cmd(command)
        print(ret, out)
        if ret:
            self._last_attributes['target_humidity'] = intensity
        return ret

    # @override(ITargetHumidity)
    @property
    def max_target_humidity(self):
        return self._Humi_range['max']

    # @override(ITargetHumidity)
    @property
    def min_target_humidity(self):
        return self._Humi_range['min']

    # @override(ITargetHumidity)
    @property
    def target_humidity(self):
        return self.get_last_attribute('target_humidity')

    # @override(IHumidity)
    def update_humidity(self):
        if self.channels['default'] == 0:
            return False
        
        ret, out = self.supply_raw_data(util.ascii_to_decimal(f'{self.Humi_id.upper()} HUMID\n'))

        if ret:
            data = util.decimal_to_ascii(out['response-raw-data'])
            float_list = util.extract_Numerical_value(data)
            if len(float_list):
                self._last_attributes['humidity'] = float_list[0]

        return ret

    # @override(IHumidity)
    @property
    def humidity(self):
        return self.get_last_attribute('humidity')

    # @override(ITemperature)
    def update_temperature(self):
        if self.channels['default'] == 0:
            return False
        
        ret, out = self.supply_raw_data(util.ascii_to_decimal(f'{self.Humi_id.upper()} TEMP{self._Temp_unit}\n'))

        if ret:
            data = util.decimal_to_ascii(out['response-raw-data'])
            float_list = util.extract_Numerical_value(data)
            if len(float_list):
                self._last_attributes[f'temperature_{self._Temp_unit}'] = float_list[0]

        return ret

    # @override(ITemperature)
    @property
    def temperature(self):
        return self.get_last_attribute(f'temperature_{self._Temp_unit}')


    def update_attributes(self):

        #:{"code":0,"cmd":"altrason-cmd","target-id":"0000d01411b01211:1","timeout-ms":1000,"id":"FFFFFFFF","action":"query-all","response":[{"USN":"0a68e064"},{"humidity":"44.41"},{"temperature-c":"25.82"},{"Blow-RPM":"0000"},{"OFF-Timer":"0000"},{"fan-mode":"OFF"},{"mode":"Manual"},{"target-humidity":66},{"power":"OFF"}]}:#

        if self.channels['default'] == 0:
            _LOGGER.warning(f'{self.alias}, {self.unique_id}: invalid update by invalid channels {self.channels}')
            return False

        target_id = util.make_target_id(self.MAC, self.channels['default'])
        command = util.make_cmd("altrason-cmd", target_id=target_id, action="query-all", id=self._Humi_id, timeout_ms=1000)
        ret, out = self._cyl_controller.send_cmd(command)


        update_ret = False
        if ret and out.get("response"):
            response_dict = {}
            for response in out.get("response"):
                response_dict.update(response)

            if response_dict:
                self._last_attributes['power'] = response_dict.get("power")
                self._last_attributes['temperature_C'] = float(response_dict.get("temperature-c"))
                self._last_attributes['target_humidity'] = float(response_dict.get("target-humidity"))
                self._last_attributes['humidity'] = float(response_dict.get("humidity"))
                self._last_attributes['mode'] = response_dict.get("mode")
                self._last_attributes['fan_mode'] = response_dict.get("fan-mode")
                self._last_attributes['off_timmer'] = float(response_dict.get("OFF-Timer"))
                update_ret = True

        if update_ret is False:
            _LOGGER.error(f'{self.alias}, {self.unique_id}: {ret}, {out}')

        _LOGGER.debug(f'{self.alias}, {self.unique_id}: {self.last_attributes}')
        return update_ret

    def set_off_timmer(self, time_hr: int):
        # 0 = Disable, 1~24 = OFF Timer in Hours
        if self.channels['default'] == 0:
            return

        target_id = util.make_target_id(self.MAC, self.channels['default'])
        command = util.make_cmd("altrason-cmd", target_id=target_id, action="set-offtimer", id=self._Humi_id, value=time_hr)
        ret, out = self._cyl_controller.send_cmd(command)
        print(ret, out)
        if ret:
            self._last_attributes['off_timmer'] = time_hr
        return ret

    def supply_raw_data(self, raw_data: list):
        if self.channels['default'] == 0:
            return False

        target_id = util.make_target_id(self.MAC, self.channels['default'])
        command = util.make_cmd("supply-raw-data", target_id=target_id, raw_data=raw_data)
        print(command)
        ret, out = self._cyl_controller.send_cmd(command, False, read_until=False)
        print(ret, out)
        print('\n')

        if ret and out.get('other'):
            out_data = list()
            for d in out.get('other'):
                out_data += d['raw-data']

            out['response-raw-data'] = out_data
        return (ret, out)

    def update_off_timer(self):
        if self.channels['default'] == 0:
            return False
        
        ret, out = self.supply_raw_data(util.ascii_to_decimal(f'{self.Humi_id.upper()} SETOFFTIMER\n'))

        if ret:
            data = util.decimal_to_ascii(out['response-raw-data'])
            float_list = util.extract_Numerical_value(data)
            if len(float_list):
                self._last_attributes['off_timmer'] = int(float_list[0])

        return ret
