import time
import sys
import json
import yaml
import binascii

from bluepy.btle import Peripheral, DefaultDelegate
from mqtt import MqttMessage

from workers.base import BaseWorker
import logger

KILL_ME = "kill"
STOP_COLLECT = "stop"

REQUIREMENTS = ['bluepy']
_LOGGER = logger.get(__name__)


class BleDeviceStatus:
  def __init__(self, worker, mac: str, name: str, uuid, available: bool = False, last_status_time: float = None,
               message_sent: bool = True):
    if last_status_time is None:
      last_status_time = time.time()

    self.worker = worker  # type: BlescanmultiWorker
    self.mac = mac.lower()
    self.uuid = uuid
    self.name = name
    self.available = available
    self.last_status_time = last_status_time
    self.message_sent = message_sent

    self.p_device = self.get_peripheral(self.mac)

  def set_status(self, available):
    print("BleDevicesStatus: set_status() --> available", available)
    print("BleDevicesStatus: set_status() --> self.available", self.available)
    if available != self.available:
      self.available = available
      self.last_status_time = time.time()
      self.message_sent = False
    print("BleDevicesStatus: set_status() --> message_sent", self.message_sent)

  def _timeout(self):
    if self.available:
      return self.worker.available_timeout
    else:
      return self.worker.unavailable_timeout

  def has_time_elapsed(self):
    elapsed = time.time() - self.last_status_time
    return elapsed > self._timeout()

  def payload(self):
    if self.available:
      return self.worker.available_payload
    else:
      return self.worker.unavailable_payload

  def get_peripheral(self, mac):
    try:
      p = Peripheral(mac, "random")
    except:
      print("BleDevicesStatus: get_peripheral(): Get Peripheral object exception!")
      return None
    else:
      print("BleDevicesStatus: get_peripheral(): Create Peripheral successful")
      return p

  def read_data(self):
    print("BleDevicesStatus --> read_data: self.uuid[2:] is ", self.uuid[2:])
    p_service = self.p_device.getServiceByUUID(int(self.uuid[2:],16))
    print("BleDevicesStatus --> read_data: p_service uuid is ", p_service.uuid)
    print("BleDevicesStatus --> read_data: p_service common name is ", p_service.uuid.getCommonName())

    print("BleDevicesStatus --> read_data: Characteristics information")
    chars = p_service.getCharacteristics()
    
    ret_json = {}
    tags = self.read_tags()
    print("BleDevicesStatus --> read_data:   tags = ", tags)
    
    i = 0
    for char in chars:
      print("BleDevicesStatus --> read_data:   -----------------------------------")
      print("BleDevicesStatus --> read_data:   uuid      : ", char.uuid, char.uuid.getCommonName())
      print("BleDevicesStatus --> read_data:   properties: ", char.propertiesToString())

      if char.supportsRead():
        val = char.read()  
        txt = ""
        for c in val:
          txt += chr(c)
        print("BleDevicesStatus --> read_data:   READ value     : ", txt)
        ret_json.update({tags[i]:txt})
        i += 1

    print("BleDevicesStatus --> read_data:   ret_json : ", ret_json)
    return json.dumps(ret_json)

  def read_tags(self):

      
    with open(os.path.join( "config","datatags.yaml"), "r") as f:
      config = yaml.safe_load(f)

    print("BleDevicesStatus --> read_tags: config", config)
    p = config['data_tags']
    
    param = p['parameter']

    return param.split(',')

  def generate_messages(self):
    messages = []
    #if not self.message_sent and self.has_time_elapsed():
    #if not self.has_time_elapsed():
      #self.message_sent = True
    
    json_msg = self.read_data()
    print("BleDevicesStatus --> generate_messages: json_msg = ", json_msg)
    
    messages.append(
      MqttMessage(topic=self.worker.format_topic('presence/{}'.format(self.name)), payload=(json_msg))
    )
    #if self.available:
    #  messages.append(
    # MqttMessage(topic=self.worker.format_topic('presence/{}/rssi'.format(self.name)), payload=("rssi"))
    #)

    return messages

class BlescanmultiWorker(BaseWorker):
  # Default values
  devices = {}
  # Payload that should be send when device is available
  available_payload = 'home'  # type: str
  # Payload that should be send when device is unavailable
  unavailable_payload = 'not_home'  # type: str
  # After what time (in seconds) we should inform that device is available (default: 0 seconds)
  available_timeout = 0  # type: float
  # After what time (in seconds) we should inform that device is unavailable (default: 60 seconds)
  unavailable_timeout = 60  # type: float
  scan_timeout = 10.  # type: float
  scan_passive = True  # type: str or bool
  start_to_collect = False #Global variable to control start to collect or not
  flag_started = False #Flag to control BleDeviceStatus object creation
  
  def __init__(self, command_timeout, **kwargs):
    print("BlescanmultiWorker --> __init__  starts")
    super(BlescanmultiWorker, self).__init__(command_timeout, **kwargs)

  def create_devices(self):
    if self.start_to_collect and not self.flag_started:
      self.last_status = []
 
      for device_name, dev_info in self.devices.items():
        print("BlescanmultiWorker --> __init__: device_name = ", device_name)
        print("BlescanmultiWorker --> __init__: mac = ", dev_info['MAC'])
        print("BlescanmultiWorker --> __init__: service_uuid = ", dev_info['Service_UUID'])
        self.last_status = [
          BleDeviceStatus(self, dev_info['MAC'], device_name, dev_info['Service_UUID'])
        ]

      self.flag_started = True

  def set_stop_flag(self):
    self.start_to_collect = False
    self.flag_started = False

  def read_payload_cmd_collect(self, device_name, payload):
    print("BlescanmultiWorker --> read_payload_cmd_collect: payload = ", payload)
    cmd_collect = {}
    cmd_collect = json.loads(payload)
    print("BlescanmultiWorker --> read_payload_cmd_collect: cmd_collect = ", cmd_collect)
    print("BlescanmultiWorker --> read_payload_cmd_collect: cmd_collect['Device_Info] = ", cmd_collect['Device_Info'])
    self.devices.update({device_name:cmd_collect['Device_Info']})
    self.start_to_collect = True

  def read_payload_cmd_parameter(self, device_name,  payload):
    cmd_parameter = {}
    cmd_parameter = json.loads(payload)
    print("BlescanmultiWorker --> read_payload_cmd_parameter: cmd_parameter = ", cmd_parameter)
    
  def read_payload_parameter_request(self, device_name, payload):
    parameter_request = {}
    parameter_request = json.loads(payload)
    print("BlescanmultiWorker --> read_payload_parameter_request: parameter_request = ", parameter_request)

  def cmd_stop(self, value):
    if value == KILL_ME:
      sys.exit("END")
    elif value == STOP_COLLECT:
      for status in self.last_status:
        self.set_stop_flag()
        self.last_status = None

  def status_update(self):
    print("BlescanmultiWorker --> status_update enters")

    ret = []

    if self.start_to_collect:
      self.create_devices()

      for status in self.last_status:
        status.read_data()
        status.set_status(status is not None)
        ret += status.generate_messages()
    else:
      print("BlescanmultiWorker --> status_update: Waiting for Collect Command!")

    return ret

  def on_command(self, topic, value):
    value = value.decode('utf-8')
    _, _, _, device_name, cmd_type, cmd = topic.split('/')

    print("BlescanmultiWorker --> on_command: topic = ", topic)
    print("BlescanmultiWorker --> on_command: device_name = ", device_name)
    print("BlescanmultiWorker --> on_command: cmd_type = ", cmd_type)
    print("BlescanmultiWorker --> on_command: cmd = ", cmd)

    if cmd_type == "Cmd":
      if cmd == "Collect":
        self.read_payload_cmd_collect(device_name, value)
      elif cmd == "Parameter":
        self.read_payload_cmd_parameter(device_name, value)
      elif cmd == "Stop":
        self.cmd_stop(value)
        
    elif cmd_type == "Parameter":
      if cmd == "Request":
        self.read_payload_parameter_request(device_name, value)
