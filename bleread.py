#!/usr/bin/env python3
# coding=utf-8

import yaml
import os
import sys
from bluepy.btle import Peripheral

with open(os.path.join(sys.path[0], "config","test.yaml"), "r") as f:
  config = yaml.safe_load(f)

info = config['devices']
#print("info =", info)
print("info mac address:", info['mac'])
print("info service uuid:", str(info['service_uuid']))
  
p_device = Peripheral(info['mac'],"random")
#p_device = Peripheral.connect(info['mac'],"random")

try:
  #for p_service in p_device.getServices():
  p_service = p_device.getServiceByUUID(info['service_uuid'])
  print("p_service uuid is ", p_service.uuid)
  print("p_service common name is ", p_service.uuid.getCommonName())

  print("Characteristics information")
  chars = p_service.getCharacteristics()
  for char in chars:
    #hnd = char.getHandle()
    print("   -----------------------------------")
    print("   common name: ", char.uuid.getCommonName())
    print("   uuid       : ", char.uuid)
    print("   properties : ", char.propertiesToString())
    if char.supportsRead():
      #print("   READ value : ", char.read())
      val = char.read()
      txt = ""
      for c in val:
        txt += chr(c)
      #txt = "(" + txt[:-1] + ")"
      print("   READ value  : ", txt)
      
    #for desc in char.getDescriptors():
    #  print("        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
    #  print("        descriptors: ", desc)
  
    #p_device.disconnect()

except:
  print("Exceptions!!")
  #p_device.disconnect()
  
else:
  print("Get characteristics information successful")