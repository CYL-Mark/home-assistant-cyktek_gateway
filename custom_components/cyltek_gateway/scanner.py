import asyncio
import logging
import re
from ipaddress import ip_network

import nmap
from homeassistant.components import network
from homeassistant.components.network.const import MDNS_TARGET_IP
from homeassistant.core import HomeAssistant

from .cyltek.cylcontroller_ex import CYLControllerEx

# from .const import CONF_INTERNET

_LOGGER = logging.getLogger(__name__)

def _scan_devices(ip):
    nm = nmap.PortScanner()
    nm.scan(hosts=str(ip), arguments='-sP -sn -T4')
    return [nm[host]['addresses'] for host in nm.all_hosts() if nm[host]['addresses'].get('mac')]


async def async_get_enable_network_adapters(hass: HomeAssistant) -> str:
    out = []
    for adapter in await network.async_get_adapters(hass):
        # _LOGGER.error(f"{adapter}")
        if adapter["enabled"] is False:
            continue
        out.append(adapter)
    return out

async def async_get_network(hass: HomeAssistant, adapter, ip_type: str='ipv4') -> str:
    """Search adapters for the network."""
    # We want the local ip that is most likely to be
    # on the LAN and not the WAN so we use MDNS_TARGET_IP
    local_ip = await network.async_get_source_ip(hass, MDNS_TARGET_IP)
    network_prefix = 24
    ip_type = ip_type.lower()
    # _LOGGER.error(f"{adapter}")
    for ip in adapter[ip_type]:
        if ip["address"] == local_ip:
            network_prefix = ip["network_prefix"]
            break
    return ip_network(f"{local_ip}/{network_prefix}", False)


async def async_create_controller(hass: HomeAssistant, device, interface):

    def _create_controller(device, interface):
        cyltek_device = CYLControllerEx(MAC=device['mac'], ip=device['ipv4'], internet=interface)
        init_ret = cyltek_device.init_ret
        return init_ret, cyltek_device

    return await hass.async_add_executor_job(
            _create_controller,
            device,
            interface
        )


async def async_discovery_MAC(hass: HomeAssistant, adapter, ip_type: str='ipv4'):
    try:
        ip_net = await async_get_network(hass, adapter=adapter, ip_type=ip_type)

        host_list = await hass.async_add_executor_job(
            _scan_devices,
            ip_net
        )

        mac_pattern = r'^D0:14:11:B'
        cyl_devices = [host for host in host_list if re.match(mac_pattern, host['mac'])]

        controller_list_ret = await asyncio.gather(
            *[async_create_controller(hass, d, adapter['name']) for d in cyl_devices]
        )
        
        controller_list = [ret[1] for ret in controller_list_ret if ret[0] is True]
        # _LOGGER.error(f"{cyl_devices}")

    except Exception as e:
        _LOGGER.exception(f"discovery_MAC Exception: {str(e)}")
        return []

    return controller_list