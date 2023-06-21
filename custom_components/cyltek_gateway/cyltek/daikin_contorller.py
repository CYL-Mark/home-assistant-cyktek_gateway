import logging
import time

from . import util
from .cyltelnet import CYLTelnet

_LOGGER = logging.getLogger(__name__)
# _LOGGER = logging.getLogger(__name__)
# _LOGGER.setLevel(logging.INFO)

def retry_counter():
    success = True

class Daikin_modbus_handler(object):
    power    :int
    direction:int
    volume   :int
    mode     :int
    op_status:int
    setpoint :float
    roomtemp :float
    master   :int
    
    def __analyze_power(self, register):
        return int(register[0] % 2)
    def __analyze_direction(self, register):
        return int(register[1] % 8)
    def __analyze_volume(self, register):
        return int(register[1] / 16)    
    def __analyze_mode(self, register):
        return int(register[2] % 8)
    def __analyze_status(self, register):
        return int(register[3] % 4)
    def __analyze_daikin_temp(self, register_lower, register_upper):
        temp = ((register_upper % 128) << 8) + register_lower
        temp = temp / 10
        if(register_upper & (1 << 7)):
            temp = -1 * temp
        return float(temp)
    def __analyze_setpoint(self, register):
        return self.__analyze_daikin_temp(register[4], register[5])
    def __analyze_roomtemp(self, register):
        return self.__analyze_daikin_temp(register[8], register[9])
    def __analyze_master(self, register):
        return int(register[3] >> 7)

    def check_comm_error(id, register):
        error_state = (register[1] << 8) + register[0]
        error_state = error_state % (1 << (id + 2)) + error_state & (1 << id)
        if error_state == 0:
            return True
        else:
            return False

    def analyze_input(self, input_register):
        self.power     = self.__analyze_power(input_register)
        self.direction = self.__analyze_direction(input_register)
        self.volume    = self.__analyze_volume(input_register)
        self.mode      = self.__analyze_mode(input_register)
        self.op_status = self.__analyze_status(input_register)
        self.setpoint  = self.__analyze_setpoint(input_register)
        self.roomtemp  = self.__analyze_roomtemp(input_register)
        self.master    = self.__analyze_master(input_register)

    def return_holding(self, ctrl_flag, dmh):
        holding_reg = []
        
        # power : holding_reg[0]
        holding_reg.append(dmh.power)
        if (ctrl_flag == 1):
            holding_reg[0] = holding_reg[0] + (6 << 4)

        # fan direction, fan volume : holding_reg[1]
        holding_reg.append(dmh.direction + (dmh.volume << 4))

        # mode : holding_reg[2]
        holding_reg.append(dmh.mode)

        # operation status : holding_reg[3]
        holding_reg.append(dmh.op_status)

        # set point : holding_reg[4], holding_reg[5]
        setpoint = int(dmh.setpoint * 10)
        holding_reg.append(int(setpoint % 256))
        holding_reg.append(int(setpoint / 256))

        return holding_reg

class Daikin(object):
    target_id: str
    endpoint:  int

    def __init__(self, mac, endpoint, connection, slave_address):
        self.mac        = mac
        self.endpoint   = endpoint
        self.conn       = connection
        self.target_id  = util.make_target_id(self.mac, self.endpoint)
        self.slave_addr = slave_address
        self.master_id  = -1 # if Master for this VRV system is not decided id will still be -1

    def __show_id(self, id):
        num = id
        _LOGGER.info(f"ID : {num}")

    def __send_9528(self, command):
        out = ""
        while(1):
            ret, out = self.conn.sends(command, just_send=False, timeout=3)
            _LOGGER.debug(out)
            time.sleep(0.2)
            try:
                if out["code"] == 0:
                    break
            except:
                pass
            _LOGGER.error("9528 error, retry")

        return out

    def __get_status(self, id):
        if (self.endpoint) != 0:
            #:{"cmd":"modbus-cmd", "target-id":"0000d01411b011E3:1","mode":"rtu","function":3,"slave-addr":1,"start-addr":2000,"number":6,"write-data":[],"timeout-ms": 1000}:#
            command = util.make_cmd("modbus-cmd", target_id = self.target_id,
                                     mode="rtu", function = 3, slave_addr = self.slave_addr, 
                                     start_addr = int(2000 + 6 * id), number = 6, write_data = [])
            out = self.__send_9528(command)
            
            dmh = Daikin_modbus_handler()
            dmh.analyze_input(out["response-register-data"])
            return dmh

    def __update_status(self, id, ctrl_flag, dmh):
        if (self.endpoint) != 0:
            #:{"cmd":"modbus-cmd", "target-id":"0000d01411b0122f:1","mode":"rtu","function":4,"slave-addr":1, "start-addr":2002,"number":1,"write-data":[97,16] , "timeout-ms": 1000}:#
            modbus_reg = dmh.return_holding(ctrl_flag = ctrl_flag, dmh = dmh)
            command = util.make_cmd("modbus-cmd", target_id = self.target_id,
                                    mode="rtu", function = 4, slave_addr = self.slave_addr, 
                                    start_addr = int(2000 + 3 * id), number = 3,
                                    write_data = modbus_reg, timeou_ms = 1000)
            out = self.__send_9528(command)
            return out

    def __check_comm_status(self, id):
        if (self.endpoint) != 0:
            #:{"cmd":"modbus-cmd", "target-id":"0000d01411b011E3:1","mode":"rtu","function":3,"slave-addr":1,"start-addr":2000,"number":6,"write-data":[],"timeout-ms": 1000}:#
            command = util.make_cmd("modbus-cmd", target_id=self.target_id,
                                     mode="rtu", function=3, slave_addr=self.slave_addr, 
                                     start_addr=5, number=1, write_data=[])

            while(1):
                out = self.__send_9528(command)
                if Daikin_modbus_handler.check_comm_error(id, out["response-register-data"]):
                    break
                _LOGGER.error("comm status error")
                return out

    def __verify_setting(self, id, set_dmh):
        # wait for 
        time.sleep(3)
        # check input register make sure setting success
        _LOGGER.debug("check input register make sure setting success")
        now_dmh = self.__get_status(id)
        # print status
        _LOGGER.info("Verify set cmd result")
        _LOGGER.info(f"power    : now {now_dmh.power    }, set {set_dmh.power}")        
        _LOGGER.info(f"volume   : now {now_dmh.volume   }, set {set_dmh.volume}")
        _LOGGER.info(f"mode     : now {now_dmh.mode     }, set {set_dmh.mode}")
        _LOGGER.info(f"setpoint : now {now_dmh.setpoint }, set {set_dmh.setpoint}")

        _LOGGER.debug("Verify other result")
        _LOGGER.debug(f"direction: now {now_dmh.direction}, set {set_dmh.direction}")
        _LOGGER.debug(f"op_status: now {now_dmh.op_status}, set {set_dmh.op_status}")
        _LOGGER.debug(f"room remp: now {now_dmh.roomtemp }, set {set_dmh.roomtemp}")

        set_dmh.op_status = now_dmh.op_status
        set_dmh.roomtemp  = now_dmh.roomtemp
        now = now_dmh.__dict__
        set = set_dmh.__dict__

        if now == set:
            _LOGGER.info("Verify Success")

        else:
            _LOGGER.error("Verify error & retry")
            # resend setting
            self.__update_status(id, ctrl_flag = 1, dmh = set_dmh)
            # check again
            self.__verify_setting(id, set_dmh)
        
    def __set_preprocess(self, id):
        _LOGGER.debug("set preprocess")
        # check communication error info
        _LOGGER.debug("check communication error info")
        self.__check_comm_status(id)
        # Get indoor unit status of connected indoor units
        _LOGGER.debug("Get indoor unit status of connected indoor units")
        now_dmh = self.__get_status(id)
        # Set indoor unit status to Holding Register
        _LOGGER.debug("Sync indoor unit status to Holding Register")
        self.__update_status(id, ctrl_flag = 0, dmh = now_dmh) 

        return now_dmh

    def __opposite_mode(self, value):
        if value == 1:
            return 2
        else: 
            return 1

    def __direct_set_mode(self, id, value):
        set_dmh = self.__set_preprocess(id)
        # Set Value
        set_dmh.mode = value
        self.__update_status(id, ctrl_flag = 1, dmh = set_dmh) 
        # dobule check
        self.__verify_setting(id, set_dmh)

    def __cool_heat_handle(self, id, value, group):
        if (self.master_id >= 0):
            # this is Daikin default behavior
            _LOGGER.info(f"Master id is {self.master_id}")
            self.__direct_set_mode(self.master_id, value)

            # failed
            # _LOGGER.info(f"Master id is {self.master_id}")
            # self.__direct_set_mode(self.master_id, value)
            # group.remove(self.master_id)
            # # need to wait for vrv set master to opposite mode
            # # time.sleep(10)
            # self.__direct_set_mode(self.master_id, value)
            # group.remove(id)

            # for set_id in group:
            #     now_dmh = self.__get_status(set_id)
            #     if(now_dmh.mode == self.__opposite_mode(value)):
            #         _LOGGER.info(f"ID {set_id} is opposite mode, change to fan mode")
            #         self.__direct_set_mode(self.master_id, 0)

        else:
            _LOGGER.info("No master in this group")
            for set_id in group:
                self.__direct_set_mode(set_id, value)

    def __need_change_operation(self, id, value, group):
        change_flag = 0
        for id in group:
            id_dmh = self.__get_status(id)
            if (id_dmh.mode == self.__opposite_mode(value)):
                change_flag = 1
            if (id_dmh.master == 1):
                self.master_id = id

        return change_flag

    def set_power(self, id, value):
        # 8196 command
        # cmd = util.make_cmd("daikin-cmd", target_id = self.target_id, action="on", id = id)

        # Simulate lightgw
        self.__show_id(id)
        if(value == 0 or value == 1):
            set_dmh = self.__set_preprocess(id)
            # Set Value
            _LOGGER.debug("Set indoor unit status to Holding Register")
            set_dmh.power = value
            self.__update_status(id, ctrl_flag = 1, dmh = set_dmh) 
            # dobule check
            self.__verify_setting(id, set_dmh)

            return True
        else:
            _LOGGER.error("Set power value error")
            return False

    def set_fan_volume(self, id, value):
        # 8196 command
        #:{"cmd":"daikin-cmd", "target-id":"0000d01411b0122f:1","action":"set-fan-volume","id":7,"value":5}:#
        # cmd = util.make_cmd("daikin-cmd", target_id = self.target_id, action = "set-fan-volume", id = id, value = value)

        # simulate lightgw
        self.__show_id(id)
        if(value == 0 or value == 1 or value == 3 or value == 5):
            set_dmh = self.__set_preprocess(id)
            # Set Value
            set_dmh.volume = value

            self.__update_status(id, ctrl_flag = 1, dmh = set_dmh) 
            # dobule check
            self.__verify_setting(id, set_dmh)

            return True
        else:
            _LOGGER.error("Set fan volume value error")
            return False

    def set_mode(self, id, value, group):
        # 8196 command
        #:{"cmd":"daikin-cmd", "target-id":"0000d01411b0122f:1","action":"set-mode","id":7,"value":2}:#
        # cmd = util.make_cmd("daikin-cmd", target_id = self.target_id, action = "set-mode", id = id, value = value)

        # simulate lightgw
        self.__show_id(id)
        if(value == 1 or value == 2):
            if (self.__need_change_operation(id, value, group)):
                _LOGGER.info("Need to change cool/heat mode")
                self.__cool_heat_handle(id, value, group)
            else:
                _LOGGER.info("Don't need to change cool/heat mode")
                self.__direct_set_mode(id, value)

        elif(value == 0 or value == 3 or value == 7):
            self.__direct_set_mode(id, value)

            return True
        else:
            _LOGGER.error("Set mode value error")
            return False

    def set_temp(self, id, value):
        # 8196 command
        #:{"cmd":"daikin-cmd", "target-id":"0000d01411b0122f:1","action":"set-temperature","id":7,"value":250}:#
        # cmd = util.make_cmd("daikin-cmd", target_id = self.target_id, action = "set-temperature", id = id, value = value)

        # simulate lightgw
        self.__show_id(id)
        if (value >= -127.9 and value <= 127.9):
            set_dmh = self.__set_preprocess(id)
            # Set Value
            set_dmh.setpoint = value
            self.__update_status(id, ctrl_flag = 1, dmh = set_dmh) 
            # dobule check
            self.__verify_setting(id, set_dmh)
            
            return True
        else:
            _LOGGER.error("Set temp value error")
            return False

    def query(self, id):
        # simulate lightgw
        self.__show_id(id)
        # check communication error info
        self.__check_comm_status(id)
        # return indoor unit status of connected indoor units
        res = self.__get_status(id).__dict__
        _LOGGER.info(res)

        # will return result like this json {'power': 1, 'direction': 0, 'volume': 1, 'mode': 2, 'op_status': 2, 'setpoint': 24.0, 'roomtemp': 24.0}   
        return True, res

class Daikin_cyl485(object):
    def __init__(self, ip, mac, slave_address):
        self.device485 = CYLTelnet(host=ip, port=9528, timeout=2, verbose=False)
        self.device485.telnet_connect(host=ip, port=9528)
        self.controller = Daikin(mac = mac, endpoint = 1, connection = self.device485, slave_address = slave_address)

    def close(self):
        self.device485.close()


# # Michael Home
# ip = '192.168.10.60'
# mac = 'd01411b0122f'
# slave_address = 1
# group = [0, 1, 2, 3, 4, 5, 6, 7]

# # CYL Hsin-chu
# ip = '192.168.50.68'
# mac = 'd01411b00259'
# slave_address = 1
# group = [0]

# for i in range(0, 8):
#     daikin485 = Daikin_cyl485(ip, mac, slave_address)
#     # out = daikin485.controller.set_power(i, 1)
#     # out = daikin485.controller.set_temp(i, 25.0)
#     # out = daikin485.controller.set_fan_volume(i, 1)
#     # out = daikin485.controller.set_mode(i, 2, group)
#     res = daikin485.controller.query(i)
#     daikin485.close()
#     _LOGGER.info("--------------------------------------------------------------------")


# # test change cool heat mode
# daikin485 = Daikin_cyl485(ip, mac, slave_address)
# out = daikin485.controller.set_mode(0, 2, group)
# daikin485.close()
# time.sleep(1)

# see result
# _LOGGER.info("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
# for i in range(0, 8):
#     daikin485 = Daikin_cyl485(ip, mac, slave_address)
#     res = daikin485.controller.query(i)
#     daikin485.close()
#     _LOGGER.info("--------------------------------------------------------------------")