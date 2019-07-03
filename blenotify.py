#!/usr/bin/env python3
# coding=utf-8

import yaml
import struct
from bluepy.btle import Peripheral, DefaultDelegate


class MyDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)
        # ... initialise here

    def handleNotification(self, cHandle, data):
        print("MyDelegate --> handleNotification: notify from " + str(cHandle) + "  " + str(data)+"\n")


       
with open( os.path.join("config","test.yaml"), "r") as f:
  config = yaml.safe_load(f)

info = config['devices']
print("info mac address:", info['mac'])
print("info service uuid:", str(info['service_uuid']))
print("info notify uuid:", str(info['notify_uuid']))

p_device = Peripheral(info['mac'],"random")
p_device.setDelegate(MyDelegate());

svc = p_device.getServiceByUUID(info['service_uuid'])
for ch in svc.getCharacteristics():
  print(str(ch))
  print("Handle is  : " + str(ch.getHandle()))
  print("Property is: " + ch.propertiesToString())

char = svc.getCharacteristics(forUUID=info['notify_uuid'])[0]
for desc in char.getDescriptors():
  print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
  print("descriptors: ", desc)
  print("common name: ", desc.uuid.getCommonName())

#setup_data = b"\x01\x00"
notify_handle = char.getHandle() + 2
print("notify_handle is  : " + str(notify_handle))
p_device.writeCharacteristic(notify_handle, struct.pack('<bb', 0x01, 0x00), withResponse = True)

i = 0
while True:
  if p_device.waitForNotifications(1.0):
    i += 1
    if(i>1000):
      break
    continue
    
  print("Waiting...")
