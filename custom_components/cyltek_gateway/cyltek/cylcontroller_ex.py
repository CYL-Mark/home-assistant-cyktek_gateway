import logging

from . import util
from .cylcontroller import CYLController

_LOGGER = logging.getLogger(__name__)

class CYLControllerEx(CYLController):
    """Represents CYL Controller Ex."""

    def __init__(self,
                 MAC: str,
                 ip: str="",
                 internet: str='eth0') -> None:
        """Initialize device."""
        super().__init__(MAC, ip=ip, internet=internet)

        self._config = {}
        self._capabilities = {}
        self._model_id = "UNKNOWN"

        self.init_ret = False

        if (self.try_connect()):
            self.init_ret = self.update_config() and self.update_capabilities() and self.update_model_id()
        pass

    @property
    def model(self):
        return f"{self._model_id}, {self.config.get('product-id')}"

    @property
    def model_id(self):
        return self._model_id

    @property
    def config(self):
        return self._config

    @property
    def capabilities(self):
        return self._capabilities


    def update_config(self):
        res, out = self.send_cmd(util.make_cmd(cmd="configure", pretty_print=False), timeout=3, just_send=False)
        if res:
            self._config = out
        
        return res

    def update_capabilities(self):
        res, out = self.send_cmd(util.make_cmd(cmd="enumerate", refresh=False), timeout=10, read_until=True, just_send=False)
        if res:
            self._capabilities = out
        
        return res

    def update_model_id(self):
        target_id = util.make_target_id(self.MAC, channel=1)
        res, out = self.send_cmd(util.make_cmd(cmd='read-attr', target_id=target_id, attr='model-id'), just_send=False)
        if res and out.get('code') == 0:
            self._model_id = out.get('value')
        
        return res
