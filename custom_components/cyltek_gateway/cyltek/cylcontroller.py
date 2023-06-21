import logging
import time
from abc import ABC, abstractmethod

from . import util

_LOGGER = logging.getLogger(__name__)

class CYLController(ABC):
    """Represents CYL Controller."""
    MAC2ip_dict = {
        # 'D0:14:11:B0:01:F5':'192.168.50.12',
        # 'D0:14:11:B0:01:3E':'192.168.50.13',
        # 'D0:14:11:B0:03:1D':'192.168.50.53',
        # 'D0:14:11:B0:01:C0':'192.168.50.54',
        # 'D0:14:11:B0:12:79':'10.1.2.166',
        # 'D0:14:11:B0:12:E0':'10.1.2.20',
        # 'D0:14:11:B0:11:E3':'172.16.50.8',
        # 'D0:14:11:B0:12:84':'172.16.50.3',
        # 'D0:14:11:B0:01:BA':'192.168.50.11',
        # 'D0:14:11:B0:12:2F':'192.168.10.144',
        'D0:14:11:B0:03:5C':'192.168.53.164',
        'D0:14:11:B0:01:DD':'192.168.10.140',
        'D0:14:11:B0:10:3C':'172.16.50.4',
        'D0:14:11:B0:10:7B':'172.16.50.5'
        }

    PORT: int = 9528

    def __init__(self,
                 MAC: str="",
                 ip: str="",
                 internet: str='eth0') -> None:
        """Initialize device."""
        
        self._port = CYLController.PORT
        self._MAC = MAC.upper()
        self._ip = ip
        self._host = None
        if util.is_valid_MAC(self._MAC):
            self._host = CYLController.MAC2ip_dict.get(self._MAC)
            if self._host is None:
                ipv6 = util.MAC_to_ipv6(self._MAC)
                self._host = f'{ipv6}%{internet}'
            else:
                self._ip = self._host

        if self._host is None and ip:
            self._host = ip

        self._alias = self._MAC
        pass


    @property
    def MAC(self):
        return self._MAC

    @property
    def ip(self):
        return self._ip

    @property
    def host(self):
        return self._host

    @property
    def alias(self):
        return self._alias

    @property
    def port(self):
        return self._port


    def try_connect(self):
        dut = util.waitUntilConnect(self.host, self.port)
        if (dut is None):
            _LOGGER.warning(f'{self.host}:{self.port} dut is None')
            return False
        # command = util.make_cmd("bye")
        # ret, out = self.send_cmd(command)
        # dut.close()
        # if not ret:
        #     _LOGGER.warning(f'{self.host}:{self.port}, {command}: ret: {ret}, out: {out}')
        # return ret
        return True

    def send_cmd(self, cmd: str,
                       just_send: bool = False,
                       timeout: float = 3,
                       resend: bool = False,
                       expect_string: str = ':#',
                       read_until: bool = False,
                       encoding: str = 'utf-8'):

        start_time = time.time()
        msg = "timeout"
        out = dict()
        ret = True
        while (time.time() - start_time < timeout):
            dut = util.waitUntilConnect(self.host, self.port)
            if (dut is None):
                return (False, msg)
            
            ret, out = dut.sends(cmd, just_send, timeout=timeout, expect_string=expect_string, read_until=read_until, encoding=encoding)

            dut.close()
            if ret and just_send:
                return (True, out)

            is_sync = True
            input_cmd = util.content9528_to_dict(cmd)
            if ret:
                if out.get('target-id') != input_cmd.get('target-id')\
                   or out.get("cmd") != input_cmd.get("cmd")\
                   or out.get("attr") != input_cmd.get("attr"):
                    is_sync = False
            
            if ret and is_sync:
                if out.get('code') == 0:
                    return (True, out)
            else:
                _LOGGER.warning(f'ret: {ret}, is_sync: {is_sync}, in: {str(input_cmd)}, out: {out}')

            if resend is False:
                break

        return (False, out)