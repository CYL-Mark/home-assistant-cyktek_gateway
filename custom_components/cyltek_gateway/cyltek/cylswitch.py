import logging

from . import globalvar as gl
from . import util
from .cylcontroller_ex import CYLControllerEx
from .cyldevice import CYLOnOffDevice

_LOGGER = logging.getLogger(__name__)

def create_cylswitch(MAC, channels, internet="eth0", auto_on=False, model=None):
    controllers_map = gl.get_controllers_map()
    if controllers_map.get(MAC) is None:
        controllers_map[MAC] = CYLControllerEx(MAC, internet=internet)

    return CYLSwitch(controllers_map[MAC], channels, auto_on, model)


class CYLSwitch(CYLOnOffDevice):

    def __init__(
        self,
        cyl_controller: CYLControllerEx,
        channels: dict,
        auto_on=False,
        model=None
    ) -> None:

        super().__init__(cyl_controller, channels, auto_on, model)
        self._unique_id = util.make_unique_id("switch", cyl_controller.MAC, channels.values())
