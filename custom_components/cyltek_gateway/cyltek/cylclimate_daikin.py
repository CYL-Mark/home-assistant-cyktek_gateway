import logging
import os

from . import COMPONENT_ABS_DIR
from . import globalvar as gl
from . import util
from .cylcontroller_ex import CYLControllerEx
from .daikin_contorller import Daikin_cyl485
from .Interface import (IFanMode, IHumidity, IMode, IPower, ISwingMode,
                        ITargetTemperature, ITemperature)
from .IOThings import IOThings

_LOGGER = logging.getLogger(__name__)
# _LOGGER = util.get_logger(__name__, logging.DEBUG)
# _LOGGER = logging.getLogger(__name__)
# _LOGGER.setLevel(logging.INFO)
def create_cylclimate(MAC,
                      AC_id,
                      config_name,
                      channels,
                      internet="eth0",
                      auto_on=False,
                      model=None):

    """generate the CYLClimate instance"""

    controllers_map = gl.get_controllers_map()
    if controllers_map.get(MAC) is None:
        controllers_map[MAC] = CYLControllerEx(MAC, internet=internet)

    json_subdir = os.path.join('config', 'climates')
    json_absdir = os.path.join(COMPONENT_ABS_DIR, json_subdir)

    if not os.path.isdir(json_absdir):
        os.makedirs(json_absdir)

    json_filename = f'{config_name}.json'
    json_path = os.path.join(json_absdir, json_filename)

    if (config := util.load_config_json(json_path)):
        return CYLClimate(controllers_map[MAC], AC_id, config, channels, auto_on, model)
    
    return None


class CYLClimate(IOThings,
                 IPower,
                 IMode,
                 IFanMode,
                 ISwingMode,
                 IHumidity,
                 ITemperature,
                 ITargetTemperature):

    Data_Mask = {
        "on_off":       {"num": 0, "mask": 0x1},
        "fan_dir":      {"num": 0, "mask": 0x0700},
        "fan_vol":      {"num": 0, "mask": 0x7000},
        "op_mode":      {"num": 1, "mask": 0xF},
        "op_status":    {"num": 1, "mask": 0xF00},
        "heat_master":  {"num": 1, "mask": 0xC000},
        "target_temp":  {"num": 2, "mask": 0xFFFF},
        "temp":         {"num": 4, "mask": 0xFFFF},
    }

    def __init__(self,
                 cyl_controller: CYLControllerEx,
                 AC_id: int,
                 config: dict,
                 channels: dict = {'default': 1},
                 auto_on=False,
                 model="STANDARD", # INDUSTRIAL 
                ) -> None:

        self._slave_address = config.get('slave_address')
        if self._slave_address != None:
            channels['default'] = self._slave_address

        super().__init__(cyl_controller, channels)
        self._unique_id = util.make_unique_id("climate", cyl_controller.MAC, channels.values(), AC_id=AC_id)

        self._AC_id = AC_id
        self._offline_retry = 0

        self.auto_on = auto_on
        self._model = model.upper()

        self._groups = config.get('groups')

        self.power_status = config.get('power_status')
        self.heat_master = config.get('heat_master')
        self.operation_modes = config.get('operation_modes')
        self.fan_modes = config.get('fan_modes')
        self.swing_modes = config.get('swing_modes')

        self.inv_power_status = dict()
        self.inv_heat_master = dict()
        self.inv_operation_modes = dict()
        self.inv_fan_modes = dict()
        self.inv_swing_modes = dict()

        if self.power_status:
            self.inv_power_status = {v: k for k, v in self.power_status.items()}
        if self.heat_master:
            self.inv_heat_master = {v: k for k, v in self.heat_master.items()}
        if self.operation_modes:
            self.inv_operation_modes = {v: k for k, v in self.operation_modes.items()}
        if self.fan_modes:
            self.inv_fan_modes = {v: k for k, v in self.fan_modes.items()}
        if self.swing_modes:
            self.inv_swing_modes = {v: k for k, v in self.swing_modes.items()}

        self._type = config.get('type')
        self._Temp_range_config = config.get('temperature_range')
        self._Temp_range = self._Temp_range_config.get(self._model)
        self._manufacturer = config.get('manufacturer')
        unit = str(config.get('temperature_unit')).upper()
        self._Temp_unit = unit if unit in ("C", "F") else "C"


    def find_ac_group(self):
        for v in self._groups.values():
            if self.AC_id in v:
                return v
        
        return None

    @property
    def AC_id(self):
        return self._AC_id

    @property
    def type(self):
        return self._type

    @property
    def model(self):
        return self._model

    @property
    def temperature_unit(self):
        return self._Temp_unit

    # @override(IPower)
    def update_power(self):
        pass

    # @override(IPower)
    def turn_on(self):
        """Turn the climate on."""
        if self.channels['default'] == 0:
            return False


        daikin485 = Daikin_cyl485(self.host, self.MAC, self._slave_address)
        ret = daikin485.controller.set_power(self.AC_id, self.power_status.get('ON'))

        if ret:
            self._last_attributes['power'] = 'ON'
        return ret

    # @override(IPower)
    def turn_off(self):
        """Turn the climate off."""
        if self.channels['default'] == 0:
            return False

        daikin485 = Daikin_cyl485(self.host, self.MAC, self._slave_address)
        ret = daikin485.controller.set_power(self.AC_id, self.power_status.get('OFF'))
        daikin485.close()
        if ret:
            self._last_attributes['power'] = 'OFF'
        return ret

    # @override(IPower)
    @property
    def power(self):
        return self.get_last_attribute('power')

    # @override(IMode)
    def available_modes(self):
        """get all the operation modes."""
        if self.operation_modes:
            return list(self.operation_modes.keys())
        return None

    # @override(IMode)
    def set_mode(self, mode):

        if self.channels['default'] == 0:
            return False
        # if self.get_last_attribute('heat_master') != 'master' and mode == 'heat':
        #     return False

        daikin485 = Daikin_cyl485(self.host, self.MAC, self._slave_address)
        ret = daikin485.controller.set_mode(self.AC_id, self.operation_modes.get(mode), self.find_ac_group())
        daikin485.close()
        if ret:
            self._last_attributes['mode'] = mode
        return ret

    # @override(IMode)
    def update_mode(self):
        pass

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
        if self.channels['default'] == 0:
            return False

        daikin485 = Daikin_cyl485(self.host, self.MAC, self._slave_address)
        ret = daikin485.controller.set_fan_volume(self.AC_id, self.fan_modes.get(mode))
        daikin485.close()
        if ret:
            self._last_attributes['fan_mode'] = mode
        return ret

    # @override(IFanMode)
    def update_fan_mode(self):
        pass

    # @override(IFanMode)
    @property
    def fan_mode(self):
        return self.get_last_attribute('fan_mode')

    # @override(ISwingMode)
    def available_swing_modes(self):
        """get all the swing modes."""
        if self.swing_modes:
            return list(self.swing_modes.keys())
        return None

    # @override(ISwingMode)
    def set_swing_mode(self, mode):

        if self.channels['default'] == 0:
            return False

        target_id = util.make_target_id(self.MAC, self.channels['default'])
        command = util.make_cmd("daikin-cmd", target_id=target_id, action="", id=self._AC_id, value=self.swing_modes.get(mode))
        print(command)
        ret, out = self._cyl_controller.send_cmd(command)
        print(ret, out)
        if ret:
            self._last_attributes['swing_mode'] = mode
        return ret

    # @override(ISwingMode)
    def update_swing_mode(self):
        pass

    # @override(ISwingMode)
    @property
    def swing_mode(self):
        return self.get_last_attribute('swing_mode')

    # @override(IHumidity)
    def update_humidity(self):
        pass

    # @override(IHumidity)
    @property
    def humidity(self):
        return self.get_last_attribute('humidity')

    # @override(ITargetTemperature)
    def update_target_temperature(self):
        pass

    # @override(ITargetTemperature)
    def set_target_temperature(self, intensity: int):
        if self.channels['default'] == 0:
            return False

        daikin485 = Daikin_cyl485(self.host, self.MAC, self._slave_address)
        ret = daikin485.controller.set_temp(self.AC_id, intensity)
        daikin485.close()

        if ret:
            self._last_attributes['target_temperature'] = intensity
        return ret

    # @override(ITargetTemperature)
    @property
    def max_target_temperature(self):
        return self._Temp_range['max']

    # @override(ITargetTemperature)
    @property
    def min_target_temperature(self):
        return self._Temp_range['min']

    @property
    def target_temperature_step(self):
        return self._Temp_range['precision']

    # @override(ITargetTemperature)
    @property
    def target_temperature(self):
        return self.get_last_attribute('target_temperature')


    # @override(ITemperature)
    def update_temperature(self):
        pass

    # @override(ITemperature)
    @property
    def temperature(self, unit: str='C'):
        return self.get_last_attribute(f'temperature_{self._Temp_unit}')


    def update_attributes(self):

        channel = self.channels['default']
        if channel == 0:
            _LOGGER.warning(f'{self.alias}, {self.unique_id}: invalid update by invalid channels {self.channels}')
            return False
            
        #:{"cmd":"modbus-cmd", "target-id":"0000d01411b011E3:1","mode":"rtu","function":3,"slave-addr":1,"start-addr":2000,"number":6,"write-data":[],"timeout-ms": 1000}:#
        target_id = util.make_target_id(self.MAC, self.channels['default'])
        command = util.make_cmd("modbus-cmd", target_id=target_id, mode="rtu", function=3, slave_addr=1, start_addr=int(2000+6*self.AC_id), number=6, write_data=[])
        ret, out = self._cyl_controller.send_cmd(command, just_send=False, timeout=3)
        
        if ret and out.get("response-register-data"):
            d = out["response-register-data"]
            data = [(d[i+1] << 8) + d[i] for i in range(0, len(d), 2)]
            self._last_attributes[f'temperature_{self._Temp_unit}'] = float(util.decode16bit(data[self.Data_Mask["temp"]["num"]], self.Data_Mask["temp"]["mask"]))/10
            self._last_attributes['power'] = self.inv_power_status.get(int(util.decode16bit(data[self.Data_Mask["on_off"]["num"]], self.Data_Mask["on_off"]["mask"])))
            self._last_attributes['mode'] = self.inv_operation_modes.get(int(util.decode16bit(data[self.Data_Mask["op_mode"]["num"]], self.Data_Mask["op_mode"]["mask"])))
            self._last_attributes['fan_mode'] = self.inv_fan_modes.get(int(util.decode16bit(data[self.Data_Mask["fan_vol"]["num"]], self.Data_Mask["fan_vol"]["mask"])))
            self._last_attributes['swing_mode'] = self.inv_swing_modes.get(int(util.decode16bit(data[self.Data_Mask["fan_dir"]["num"]], self.Data_Mask["fan_dir"]["mask"])))
            self._last_attributes['target_temperature'] = float(util.decode16bit(data[self.Data_Mask["target_temp"]["num"]], self.Data_Mask["target_temp"]["mask"]))/10
            self._last_attributes['heat_master'] = self.inv_heat_master.get(int(util.decode16bit(data[self.Data_Mask["heat_master"]["num"]], self.Data_Mask["heat_master"]["mask"])))
            if self._last_attributes['mode'] not in self._Temp_range_config:
                self._Temp_range = self._Temp_range_config.get(self._model)
            else:
                self._Temp_range = self._Temp_range_config.get(self._last_attributes['mode'])
        else:
            _LOGGER.error(f'{self.alias}, {self.unique_id}: {command}')
            _LOGGER.error(f'{self.alias}, {self.unique_id}: {ret}, {out}')

        _LOGGER.debug(f'{self.alias}, {self.unique_id}: {self.last_attributes}')
        return ret


    def supply_raw_data(self, raw_data: list):
        """send the raw data"""

        if self.channels['default'] == 0:
            return False

        target_id = util.make_target_id(self.MAC, self.channels['default'])
        command = util.make_cmd("supply-raw-data", target_id=target_id, raw_data=raw_data)

        ret, out = self._cyl_controller.send_cmd(command, False, read_until=False)

        if ret and out.get('other'):
            out_data = list()
            for d in out.get('other'):
                out_data += d['raw-data']

            out['response-raw-data'] = out_data
        return (ret, out)
