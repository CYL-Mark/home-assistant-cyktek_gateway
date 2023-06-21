import json
import logging
import os
import sys

from cyltek import util

mylogger = logging.getLogger(__name__)
mylogger.setLevel(logging.DEBUG)


if __name__ == '__main__':
    print(os.path.abspath(__file__))
    dir = os.path.abspath(__file__).split("custom_components")[0]
    dir = os.path.join(dir, ".storage")
    print(os.path.isdir(dir))
    files = [os.path.join(dir, f) for f in ["core.config_entries", "core.device_registry", "core.entity_registry"]]

    config_entries = util.load_config_json(os.path.join(dir, "core.config_entries"))
    device_registry = util.load_config_json(os.path.join(dir, "core.device_registry"))
    entity_registry = util.load_config_json(os.path.join(dir, "core.entity_registry"))
    print(entity_registry)
    if (data := config_entries.get("data")) and (entries := data.get("entries")):
        for e in entries:
            if e.get("domain") != "cyltek_gateway":
                continue

            CYL_IOT_MAC = e.get("data").get("mac")
            for d in e.get("data").get("devices"):
                if d.get("entity_type").lower() == "climate":
                    id = d.get("ac_id")
                    d["unique_id"] = util.make_unique_id(d["entity_type"],
                                                            CYL_IOT_MAC,
                                                            d["channels"].values(),
                                                            id=id)
                elif d.get("entity_type").lower() == "humidifier":
                    id = d.get("humi_id")
                    d["unique_id"] = util.make_unique_id(d["entity_type"],
                                                            CYL_IOT_MAC,
                                                            d["channels"].values(),
                                                            id=id)
                else:
                    d["unique_id"] = util.make_unique_id(d["entity_type"],
                                                        CYL_IOT_MAC,
                                                        d["channels"].values())
                

    json_object = json.dumps(config_entries, indent=2)
    report_path = os.path.join(dir, "core.config_entries.json")
    with open(report_path, "w", encoding="utf8") as outfile:
        outfile.write(json_object)
    mylogger.info("write config_entries end")

    if (data := device_registry.get("data")) and (devices := data.get("devices")):
        for d in devices:
            if d.get("manufacturer") != "CYLTek":
                continue
            
            d.get("connections")[0][0] = "IPv6"

    json_object = json.dumps(device_registry, indent=2)
    report_path = os.path.join(dir, "core.device_registry.json")
    with open(report_path, "w", encoding="utf8") as outfile:
        outfile.write(json_object)
    mylogger.info("write device_registry end")


    if (data := entity_registry.get("data")) and (entities := data.get("entities")):
        for e in entities:
            if e.get("platform") != "cyltek_gateway":
                continue

            for ey in config_entries.get("data").get("entries"):
                if ey.get("domain") != "cyltek_gateway":
                    continue

                if ey.get("entry_id") != e.get("config_entry_id"):
                    continue

                for d in ey.get("data").get("devices"):
                    if d.get("entity_type").lower() == e.get("entity_id").split(".")[0]:
                        if ch := [str(n) for n in d.get("channels").values()] == e.get("unique_id").split("::")[0].split(":")[1:]:
                            if e.get("entity_id").split(".")[0] == "climate":
                                if e.get("unique_id").split("::")[1] != str(d.get("ac_id")):
                                    continue
                            elif e.get("entity_id").split(".")[0] == "humidifier":
                                if e.get("unique_id").split("::")[1] != str(d.get("humi_id")):
                                    continue
                            e["unique_id"] = d["unique_id"]

    json_object = json.dumps(entity_registry, indent=2, ensure_ascii=False)
    report_path = os.path.join(dir, "core.entity_registry.json")

    with open(report_path, "w", encoding="utf8") as outfile:
        outfile.write(json_object)
    mylogger.info("write entity_registry end")