"""Config flow for CYLTek lights."""
import logging
from copy import deepcopy
from typing import Any, Dict, Optional

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries, core
from homeassistant.const import (CONF_DEVICES, CONF_MAC, CONF_NAME,
                                 CONF_UNIQUE_ID, Platform)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from . import scanner
from .const import (CONF_CHANNELS, CONF_CONFIG_JSON, CONF_ENTITY_TYPE,
                    CONF_INTERNET, CONF_MODEL, CONF_TYPE, DEFAULT_NAMES,
                    DOMAIN, PLATFORMS)
from .cover import CoverType
from .cyltek import globalvar as gl
from .cyltek import util
from .cyltek.cylcontroller_ex import CYLController
from .humidifier import HumidifierType

_LOGGER = logging.getLogger(__name__)

# This is the schema that used to display the UI to the user.
# Note the input displayed to the user will be translated.
# See the translations/<lang>.json file and strings.json.
# See here for further information:
# https://developers.home-assistant.io/docs/config_entries_config_flow_handler/#translations

ACTIONS = {
    Platform.SWITCH     : "Add Switch",
    Platform.LIGHT      : "Add Light",
    Platform.COVER      : "Add Cover",
    Platform.CLIMATE    : "Add Climate",
    Platform.HUMIDIFIER : "Add Humidifier"
}


def _fill_the_form_by_value_dict(target_entity_type: str,
                                  default_value: Optional[Dict[str, Any]] = None):
    df = default_value
    if target_entity_type == Platform.SWITCH:
        return vol.Schema(
            {
                vol.Optional(CONF_NAME,         default=df['name'])                 : cv.string,
                vol.Required('on-off channel',  default=df['on-off channel'])       : vol.All(cv.positive_int, vol.Range(min=1)),
                vol.Optional("add another",     default=df['add another'])          : cv.boolean,
            }
        )

    elif target_entity_type == Platform.LIGHT:
        return vol.Schema(
            {
                vol.Optional(CONF_NAME,             default=df['name'])                 : cv.string,
                vol.Required('on-off channel',      default=df['on-off channel'])       : vol.All(cv.positive_int, vol.Range(min=1)),
                vol.Optional('level channel',       default=df['level channel'])        : cv.positive_int,
                vol.Optional('color-temp channel',  default=df['color-temp channel'])   : cv.positive_int,
                vol.Optional('color channel',       default=df['color channel'])        : cv.positive_int,
                vol.Optional("add another",         default=df['add another'])          : cv.boolean,
            }
        )
    elif target_entity_type == Platform.COVER:
        return vol.Schema(
            {
                vol.Optional(CONF_NAME,       default=df['name'])           : cv.string,
                vol.Required('open channel',  default=df['open channel'])   : vol.All(cv.positive_int, vol.Range(min=1)),
                vol.Required('close channel', default=df['close channel'])  : vol.All(cv.positive_int, vol.Range(min=1)),
                vol.Optional('stop channel',  default=df['stop channel'])   : cv.positive_int,
                vol.Optional('level channel', default=df['level channel'])  : cv.positive_int,
                vol.Optional(CONF_TYPE,       default=df[CONF_TYPE])        : vol.In([e.value for e in CoverType]),
                vol.Required('config json',   default=df['config json'])    : cv.string,
                vol.Optional("add another",   default=df['add another'])    : cv.boolean,
            }
        )

    elif target_entity_type == Platform.CLIMATE:
        return vol.Schema(
            {
                vol.Optional(CONF_NAME,          default=df['name'])            : cv.string,
                vol.Required('default channel',  default=df['default channel']) : vol.All(cv.positive_int, vol.Range(min=1)),
                vol.Required('AC id',            default=df['AC id'])           : vol.All(cv.positive_int, vol.Range(min=1)),
                vol.Optional(CONF_MODEL,         default=df[CONF_MODEL])        : cv.string,
                vol.Required('config json',      default=df['config json'])     : cv.string,
                vol.Optional("add another",      default=df['add another'])     : cv.boolean,
            }
        )
    elif target_entity_type == Platform.HUMIDIFIER:
        return vol.Schema(
            {
                vol.Optional(CONF_NAME,          default=df['name'])            : cv.string,
                vol.Required('default channel',  default=df['default channel']) : vol.All(cv.positive_int, vol.Range(min=1)),
                vol.Required('humi id',          default=df['humi id'])         : cv.string,
                vol.Optional(CONF_TYPE,          default=df[CONF_TYPE])         : vol.In([e.value for e in HumidifierType]),
                vol.Optional(CONF_MODEL,         default=df[CONF_MODEL])        : cv.string,
                vol.Required('config json',      default=df['config json'])     : cv.string,
                vol.Optional("add another",      default=df['add another'])     : cv.boolean,
            }
        )
    
    return None


## default value
switch_schema_default_values = {
    'name'              : DEFAULT_NAMES[Platform.SWITCH],
    'on-off channel'    : 1,
    'add another'       : False
}

light_schema_default_values = {
    'name'                  : DEFAULT_NAMES[Platform.LIGHT],
    'on-off channel'        : 1,
    'level channel'         : 0,
    'color-temp channel'    : 0,
    'color channel'         : 0,
    "add another"           : False
}

cover_schema_default_values = {
    'name'              : DEFAULT_NAMES[Platform.COVER],
    'open channel'      : 1,
    'close channel'     : 2,
    'stop channel'      : 0,
    'level channel'     : 0,
    'type'              : CoverType.Curtain,
    'config json'       : "cover",
    "add another"       : False
}

climate_schema_default_values = {
    'name'              : DEFAULT_NAMES[Platform.CLIMATE],
    'default channel'   : 1,
    'AC id'             : 1,
    'model'             : "standard",
    'config json'       : "daikin",
    "add another"       : False
}

humidifier_schema_default_values = {
    'name'              : DEFAULT_NAMES[Platform.HUMIDIFIER],
    'default channel'   : 1,
    'humi id'           : None,
    'type'              : HumidifierType.Dehumidifier,
    'model'             : "standard",
    'config json'       : "proCozy",
    "add another"       : False
}

DEVICE_SCHEMA_DICT = {
    Platform.SWITCH     : _fill_the_form_by_value_dict(Platform.SWITCH,     switch_schema_default_values),
    Platform.LIGHT      : _fill_the_form_by_value_dict(Platform.LIGHT,      light_schema_default_values),
    Platform.COVER      : _fill_the_form_by_value_dict(Platform.COVER,      cover_schema_default_values),
    Platform.CLIMATE    : _fill_the_form_by_value_dict(Platform.CLIMATE,    climate_schema_default_values),
    Platform.HUMIDIFIER : _fill_the_form_by_value_dict(Platform.HUMIDIFIER, humidifier_schema_default_values)
}

## generate device info dict from user input
def _get_device_info_from_user_input(target_entity_type: str,
                                     CYL_IOT_MAC: str,
                                     user_input: Optional[Dict[str, Any]] = None):
    device_info = {}

    if target_entity_type == Platform.SWITCH:
        device_info = { CONF_NAME: user_input[CONF_NAME],
                        CONF_CHANNELS:
                        {
                            'on-off': user_input['on-off channel'],
                        },
                        CONF_ENTITY_TYPE: target_entity_type,
                      }
        device_info[CONF_UNIQUE_ID] = util.make_unique_id(device_info[CONF_ENTITY_TYPE],
                                                          CYL_IOT_MAC,
                                                          device_info[CONF_CHANNELS].values())
    elif target_entity_type == Platform.LIGHT:
        device_info = { CONF_NAME: user_input[CONF_NAME],
                        CONF_CHANNELS:
                        {
                            'on-off': user_input['on-off channel'],
                            'level': user_input['level channel'],
                            'color-temp': user_input['color-temp channel'],
                            'color': user_input['color channel'],
                        },
                        CONF_ENTITY_TYPE: target_entity_type,
                      }
        device_info[CONF_UNIQUE_ID] = util.make_unique_id(device_info[CONF_ENTITY_TYPE],
                                                          CYL_IOT_MAC,
                                                          device_info[CONF_CHANNELS].values())
    elif target_entity_type == Platform.COVER:
        device_info = { CONF_NAME: user_input[CONF_NAME],
                        CONF_CHANNELS:
                        {
                            'open': user_input['open channel'],
                            'close': user_input['close channel'],
                            'stop': user_input['stop channel'],
                            'level': user_input['level channel'],
                        },
                        CONF_ENTITY_TYPE: target_entity_type,
                        CONF_TYPE: user_input[CONF_TYPE],
                        CONF_CONFIG_JSON: user_input['config json'],
                      }
        device_info[CONF_UNIQUE_ID] = util.make_unique_id(device_info[CONF_ENTITY_TYPE],
                                                          CYL_IOT_MAC,
                                                          device_info[CONF_CHANNELS].values())
    elif target_entity_type == Platform.CLIMATE:
        device_info = { CONF_NAME: user_input[CONF_NAME],
                        CONF_CHANNELS:
                        {
                            'default': user_input['default channel'],
                        },
                        CONF_ENTITY_TYPE: target_entity_type,
                        "ac_id": user_input['AC id'],
                        CONF_MODEL: user_input[CONF_MODEL],
                        CONF_CONFIG_JSON: user_input['config json'],
                      }
        device_info[CONF_UNIQUE_ID] = util.make_unique_id(device_info[CONF_ENTITY_TYPE],
                                                          CYL_IOT_MAC,
                                                          device_info[CONF_CHANNELS].values(),
                                                          ac_id=device_info["ac_id"])
    elif target_entity_type == Platform.HUMIDIFIER:
        device_info = { CONF_NAME: user_input[CONF_NAME],
                        CONF_CHANNELS:
                        {
                            'default': user_input['default channel'],
                        },
                        CONF_ENTITY_TYPE: target_entity_type,
                        "humi_id": user_input['humi id'],
                        CONF_CONFIG_JSON: user_input['config json'],
                        CONF_MODEL: user_input[CONF_MODEL],
                        CONF_TYPE: user_input[CONF_TYPE]
                      }
        device_info[CONF_UNIQUE_ID] = util.make_unique_id(device_info[CONF_ENTITY_TYPE],
                                                          CYL_IOT_MAC,
                                                          device_info[CONF_CHANNELS].values(),
                                                          humi_id=device_info["humi_id"])
    
    return device_info


def _validate_device(mac: str, interface: str) -> None:
    if util.is_valid_MAC(mac) is False:
        raise ValueError

    cyltek_device = CYLController(mac, internet=interface)
    if (False is cyltek_device.try_connect()):
        raise OSError


async def _async_validate_device(
    hass: core.HomeAssistant, mac: str, interface: str
) -> tuple[dict[str, str], str]:

    errors = {}
    try:
        await hass.async_add_executor_job(
            _validate_device,
            mac,
            interface
        )
    except ValueError:
        errors[CONF_MAC] = "invalid_MAC"
    except OSError:
        _LOGGER.exception("Cannot connect to %s", mac)
        errors[CONF_MAC] = "cannot_connect"

    return (errors, mac.upper())

## ConfigFlow
class CYLTekGatewayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CYLTek Lights"""

    data: Optional[Dict[str, Any]] = {}
    target_entity_type = Platform.SWITCH

    DEVICE_LIST = []
    SCAN_INTERFACE = None

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        adapters = []
        adapters = await scanner.async_get_enable_network_adapters(self.hass)
        if not adapters:
            return self.async_abort(reason="network_error")

        adapter_dict = {i['name']: i for i in adapters}
        CYLTekGatewayConfigFlow.SCAN_INTERFACE = adapters[0]['name']
        default = CYLTekGatewayConfigFlow.SCAN_INTERFACE
        scan_schema = vol.Schema(
            {
                vol.Required(CONF_INTERNET, default=default): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=list(adapter_dict.keys()),
                                                  mode=selector.SelectSelectorMode.DROPDOWN),
                    ),
                vol.Optional("rescan",      default=False): cv.boolean,
            }
        )

        errors = {}
        if user_input is not None:
            adapter = adapter_dict[user_input.get(CONF_INTERNET)]
            self.data[CONF_INTERNET] = user_input.get(CONF_INTERNET)
            # _LOGGER.error(user_input)
            if not CYLTekGatewayConfigFlow.DEVICE_LIST \
               or CYLTekGatewayConfigFlow.SCAN_INTERFACE != user_input.get(CONF_INTERNET) \
               or user_input.get("rescan", False):
                if device_list := await scanner.async_discovery_MAC(self.hass, adapter):
                    CYLTekGatewayConfigFlow.DEVICE_LIST = device_list
                    CYLTekGatewayConfigFlow.SCAN_INTERFACE = user_input.get(CONF_INTERNET)
                else:
                    errors["base"] = "no_devices_found"
            
            if not errors:
                return await self.async_step_pick()

        # elif len(adapters) == 1:
        #     adapter = adapter_dict[default]
        #     self.data[CONF_INTERNET] = default
        #     if not CYLTekGatewayConfigFlow.DEVICE_LIST:
        #         if device_list := await scanner.async_discovery_MAC(self.hass, adapter):
        #             CYLTekGatewayConfigFlow.DEVICE_LIST = device_list
        #             return await self.async_step_pick()
        #         else:
        #             return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=scan_schema,
            errors=errors,
        )

    async def async_step_pick(self, user_input: Optional[Dict[str, Any]] = None):
        errors: Dict[str, str] = {}

        device_list = CYLTekGatewayConfigFlow.DEVICE_LIST

        ## filter not added devices
        entry_dict = {e.data[CONF_MAC]: e for e in self._async_current_entries()}
        device_list = [d for d in device_list if not entry_dict.get(dr.format_mac(d.MAC).upper())]

        if not device_list:
            return self.async_abort(reason="all_devices_added")

        all_devices = {f"{d.MAC} ({d.ip}) {d.model_id}": d for d in device_list}
        default = list(all_devices)[0]

        pick_schema = vol.Schema(
            {
                vol.Required("device", default=default): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=list(all_devices),
                                                  mode=selector.SelectSelectorMode.DROPDOWN),
                    )
            }
        )
        already_built_entry_title = ''
        input_MAC_upper = ''
        if user_input is not None:
            controller = all_devices[user_input.get("device")]
            mac = dr.format_mac(controller.MAC).upper()
            errors, input_MAC_upper = await _async_validate_device(self.hass, mac, self.data[CONF_INTERNET])
            if not errors:
                # entity_registry = er.async_get(self.hass)
                is_already_built_entry = False
                if entry := entry_dict.get(mac):
                    is_already_built_entry = True
                    already_built_entry_title = entry.title

                # for entry in self._async_current_entries():
                #     # entries = async_entries_for_config_entry(
                #     #     entity_registry, entry.entry_id
                #     # )

                #     if entry.data[CONF_MAC] == input_MAC_upper:
                #         is_already_built_entry = True
                #         already_built_entry_title = entry.title
                #         break

                # self._async_abort_entries_match(
                #     {CONF_MAC: user_input[CONF_MAC]}
                # )
                if is_already_built_entry is False:
                    # Input is valid, set data.
                    self.data[CONF_MAC] = input_MAC_upper
                    self.data[CONF_DEVICES] = []
                    controllers_map = gl.get_controllers_map()
                    if not controllers_map.get(input_MAC_upper):
                        controllers_map[input_MAC_upper] = controller
                    ## Return the form of the next step.
                    return await self.async_step_select()
                else:
                    errors["base"] = "already_built_entry"

        return self.async_show_form(
            step_id="pick",
            data_schema=pick_schema,
            errors=errors,
            description_placeholders={
                "title": already_built_entry_title,
                "mac": input_MAC_upper
            }
        )

    async def async_step_select(self, user_input: Optional[Dict[str, Any]] = None):
        errors: Dict[str, str] = {}

        select_schema = vol.Schema(
            {
                vol.Required("action", default=self.target_entity_type): vol.In(ACTIONS),
            }
        )

        if user_input is not None:
            # handle error here
            # ...

            if not errors:
                # Input is valid, set data.
                self.target_entity_type = user_input.get("action")
                # Return the form of the next step.
                return await self.async_step_device()
        
        return self.async_show_form(
            step_id="select",
            data_schema=select_schema,
            errors=errors
        )

    async def async_step_device(self, user_input: Optional[Dict[str, Any]] = None):

        errors: Dict[str, str] = {}
        already_configured_entity_unique_id = ''
        already_configured_entity_name = ''
        device_schema = DEVICE_SCHEMA_DICT[self.target_entity_type]

        if user_input is not None:
            # Validate the path.
            # try:
            #     validate_channels(user_input)
            # except ValueError:
            #     errors["base"] = "invalid_channel"

            if not errors:
                device_info = _get_device_info_from_user_input(self.target_entity_type, self.data[CONF_MAC], user_input)

                is_already_configured_entity = False
                for curr_device in self.data[CONF_DEVICES]:
                    print(curr_device)
                    if device_info[CONF_UNIQUE_ID] == curr_device[CONF_UNIQUE_ID]:
                        is_already_configured_entity = True
                        already_configured_entity_name = curr_device[CONF_NAME]
                        already_configured_entity_unique_id = curr_device[CONF_UNIQUE_ID]
                        break

                if is_already_configured_entity is False:
                    ## Input is valid, set data.
                    self.data[CONF_DEVICES].append(device_info)
                    ## If user ticked the box show this form again so they can add an additional device.
                    if user_input.get("add another", False):
                        return await self.async_step_select()

                    ## User is done adding devices, create the config entry.
                    return self.async_create_entry(title=self.data[CONF_MAC], data=deepcopy(self.data))
                else:
                    errors["base"] = "already_configured_entity"
            
            if errors:
                device_schema = _fill_the_form_by_value_dict(self.target_entity_type, user_input)

        return self.async_show_form(
            step_id="device",
            data_schema=device_schema,
            errors=errors,
            description_placeholders={
                "uid": already_configured_entity_unique_id,
                "name": already_configured_entity_name,
                "device": DEFAULT_NAMES[self.target_entity_type],
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""
    target_entity_type = Platform.SWITCH

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:

        self.target_entity_type = Platform.SWITCH
        return self.async_show_menu(
            step_id="init",
            menu_options=["select", "remove"]
        )

    async def async_step_select(self, user_input: Optional[Dict[str, Any]] = None):
        errors: Dict[str, str] = {}

        select_schema = vol.Schema(
            {
                vol.Required("action", default=self.target_entity_type): vol.In(ACTIONS),
            }
        )

        if user_input is not None:
            ## handle error here
            ## ...

            if not errors:
                ## Input is valid, set data.
                self.target_entity_type = user_input.get("action")
                ## Return the form of the next step.
                return await self.async_step_device()
        
        return self.async_show_form(
            step_id="select",
            data_schema=select_schema,
            errors=errors
        )

    async def async_step_device(self, user_input: Optional[Dict[str, Any]] = None):

        errors: Dict[str, str] = {}
        already_configured_entity_unique_id = ''
        already_configured_entity_name = ''

        device_schema = DEVICE_SCHEMA_DICT[self.target_entity_type]
        if user_input is not None:
            entry_devices = deepcopy(self.config_entry.data[CONF_DEVICES])
            # Validate.
            # Validate the path.
            # try:
            #     validate_channels(user_input)
            # except ValueError:
            #     errors["base"] = "invalid_channel"
            if not errors:
                device_info = _get_device_info_from_user_input(self.target_entity_type,
                                                              self.config_entry.data[CONF_MAC],
                                                              user_input)

                is_already_configured_entity = False
                for curr_device in entry_devices:
                    # print(curr_device)
                    if device_info[CONF_UNIQUE_ID] == curr_device[CONF_UNIQUE_ID]:
                        is_already_configured_entity = True
                        already_configured_entity_name = curr_device[CONF_NAME]
                        already_configured_entity_unique_id = curr_device[CONF_UNIQUE_ID]
                        break

                if is_already_configured_entity is False:
                    # Input is valid, set data.
                    entry_devices.append(device_info)
                    ## Value of data will be set on the options property of our config_entry instance.
                    # print(self.config_entry.data)
                    reload = self.config_entry.state == config_entries.ConfigEntryState.SETUP_RETRY
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data={CONF_MAC       : self.config_entry.data[CONF_MAC],
                                                 CONF_INTERNET  : self.config_entry.data[CONF_INTERNET],
                                                 CONF_DEVICES   : entry_devices}
                    )
                    reload = self.config_entry.state in (
                        config_entries.ConfigEntryState.SETUP_RETRY,
                        config_entries.ConfigEntryState.LOADED,
                    )
                    if reload:
                        self.hass.async_create_task(
                            self.hass.config_entries.async_reload(self.config_entry.entry_id)
                        )
                        
                    ## If user ticked the box show this form again so they can add an additional device.
                    if user_input.get("add another", False):
                        return await self.async_step_select()
                    
                    # return self._set_confirm_only()
                    return self.async_abort(reason="setup_complete")
                    # return self.async_create_entry(
                    #     title=self.config_entry.title,
                    #     data=self.config_entry.data,
                    # )
                else:
                    errors["base"] = "already_configured_entity"
            
            if errors:
                device_schema = _fill_the_form_by_value_dict(self.target_entity_type, user_input)

        return self.async_show_form(
            step_id="device",
            data_schema=device_schema,
            errors=errors,
            description_placeholders={
                "uid"   : already_configured_entity_unique_id,
                "name"  : already_configured_entity_name,
                "device": DEFAULT_NAMES[self.target_entity_type],
            }
        )

    async def async_step_remove(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        print("async_step_remove")
        errors: Dict[str, str] = {}
        # Grab all configured devices from the entity registry so we can populate the
        # multi-select dropdown that will allow a user to remove a device.
        entity_registry = er.async_get(self.hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        )

        # for entry in self._async_current_entries(include_ignore=False):

        ## Default value for our multi-select.
        all_devices = {e.entity_id: f'{e.original_name} ({e.unique_id})' for e in entries}
        device_map = {e.entity_id: e for e in entries}

        if user_input is not None:
            updated_devices = deepcopy(self.config_entry.data[CONF_DEVICES])
            ## Remove any unchecked devices.
            removed_entities = [
                entity_id
                for entity_id in device_map.keys()
                    if entity_id not in user_input[CONF_DEVICES]
            ]
            for entity_id in removed_entities:
                ## Unregister from HA
                entity_registry.async_remove(entity_id)
                ## Remove from our configured devices.
                entity = device_map[entity_id]
                updated_devices = [ud for ud in updated_devices 
                                        if ud[CONF_UNIQUE_ID] != entity.unique_id]

            if not errors:
                ## Value of data will be set on the options property of our config_entry instance.
                # print({CONF_MAC: self.config_entry.data[CONF_MAC], CONF_DEVICES: updated_devices})
                # print(self.config_entry.data)
                
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data={CONF_MAC       : self.config_entry.data[CONF_MAC],
                                             CONF_INTERNET  : self.config_entry.data[CONF_INTERNET],
                                             CONF_DEVICES   : updated_devices}
                )
                reload = self.config_entry.state in (
                    config_entries.ConfigEntryState.SETUP_RETRY,
                    config_entries.ConfigEntryState.LOADED,
                )
                if reload:
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(self.config_entry.entry_id)
                    )
                
                # return self._set_confirm_only()
                return self.async_abort(reason="setup_complete")
                # print(self.config_entry.data)
                # return self.async_create_entry(
                #     title=self.config_entry.title,
                #     data=self.config_entry.data,
                # )

        options_schema = vol.Schema(
            {
                vol.Optional(CONF_DEVICES, default=list(all_devices.keys())): cv.multi_select(
                    all_devices
                ),
            }
        )
        return self.async_show_form(
            step_id="remove", data_schema=options_schema, errors=errors
        )
