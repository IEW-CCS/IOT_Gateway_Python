import yaml
import os
import sys

with open(os.path.join(sys.path[0], "config","manager.yaml"), "r") as f:
    settings = yaml.safe_load(f)

with open(os.path.join(sys.path[0], "config","mqtt.yaml"), "r") as q:
    mqtt_settings = yaml.safe_load(q)