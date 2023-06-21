"""Constants for CYLTek Lights integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

# This is the internal name of the integration, it should also match the directory
# name for the integration.
DOMAIN: Final = "cyltek_gateway"
MANUFACTURER_NAME: Final = "CYLTek"
VERSION: Final = "2.0.3"
DEFAULT_NAMES: Final = { Platform.SWITCH : "CYLTek-Switch",
                         Platform.LIGHT : "CYLTek-Light",
                         Platform.COVER : "CYLTek-Cover",
                         Platform.CLIMATE : "CYLTek-Climate",
                         Platform.HUMIDIFIER : "CYLTek-Humidifier"
}

CONF_INTERNET: Final = "internet"
CONF_CHANNELS: Final = "channels"
CONF_CONFIG_JSON: Final = 'config_json'

CONF_ENTITY_TYPE: Final = "entity_type"
CONF_TYPE: Final = 'type'

# humidifier
CONF_HUMI_ID: Final = "humi_id"
CONF_MODEL: Final = "model"

# AC
CONF_AC_ID: Final = "ac_id"

PLATFORMS: Final = [Platform.SWITCH, Platform.LIGHT, Platform.COVER, Platform.CLIMATE, Platform.HUMIDIFIER]
