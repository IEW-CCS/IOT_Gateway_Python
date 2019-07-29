import time
import sys
import json
import yaml
import binascii
import datetime
import os
import logging

from HslCommunication import MelsecMcNet
from HslCommunication import SoftBasic
from mqtt import MqttMessage
from config import settings

from apscheduler.schedulers.background import BackgroundScheduler
from pytz import utc

from multiprocessing import Queue as queue
from workers.base import BaseWorker

import logger

_LOGGER = logger.get(__name__)


KILL_ME = "kill"
STOP_COLLECT = "stop"

PLC_DTYPE_INT = "INT"
PLC_DTYPE_UINT = "UINT"
PLC_DTYPE_FLOAT = "FLOAT"
PLC_DTYPE_DOUBLE = "DOUBLE"
PLC_DTYPE_STRING = "STR"
PLC_DTYPE_BLOCK = "BLOCK"

PLC_DTYPE_ENUM = (PLC_DTYPE_INT, 
                  PLC_DTYPE_UINT, 
                  PLC_DTYPE_FLOAT, 
                  PLC_DTYPE_DOUBLE, 
                  PLC_DTYPE_STRING,
                  PLC_DTYPE_BLOCK)
PLC_ADDR_ENUM = ('M', 'B', 'D', 'W')

class PLCDevice:
  def __init__(self, worker, ip_addr: str, port_id, device_name: str, available: bool = False, last_status_time: float = None,
               message_sent: bool = True):
    if last_status_time is None:
      last_status_time = time.time()

    self.worker = worker
    self.available = available
    self.last_status_time = last_status_time
    self.message_sent = message_sent
    self.ip_addr = ip_addr
    self.port_id = port_id
    self.device_name = device_name

    self.p_device = self.get_peripheral(self.ip_addr, self.port_id)

  def set_status(self, available):
    print("PLCDevice: set_status() --> available", available)
    print("PLCDevice: set_status() --> self.available", self.available)
    if available != self.available:
      self.available = available
      self.last_status_time = time.time()
      self.message_sent = False
    print("PLCDevice: set_status() --> message_sent", self.message_sent)


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

  def get_peripheral(self, ip_addr, port_id):
    port = int(port_id)
    melsecNet = MelsecMcNet(ip_addr, port)
    if melsecNet.ConnectServer().IsSuccess == False:
      print("PLCDevice: get_peripheral --> connect falied")
      _LOGGER.info("PLCDevice: get_peripheral --> connect falied")
      return None
    else:
      print("PLCDevice: get_peripheral --> connect successed")
      _LOGGER.info("PLCDevice: get_peripheral --> connect successed")
      return melsecNet


  def read_data(self, addr):
    print("PLCDevice --> read_data: config is ", addr)
    now = datetime.datetime.now()
    
    ret_json = {}

    ret_json.update({'Device_ID':self.device_name})
    ret_json.update({'IP_Address':self.ip_addr})
    ret_json.update({'Time_Stamp':now.strftime("%Y%m%d%H%M%S")})
    edc_array = []
    
    for ad in addr:
      print("PLCDevice --> read_data: DATA_NAME is ", ad['DATA_NAME'])
      print("PLCDevice --> read_data: DATA_ADDR is ", ad['DATA_ADDR'])
      print("PLCDevice --> read_data: DATA_TYPE is ", ad['DATA_TYPE'])
      print("PLCDevice --> read_data: DATA_LENGTH is ", ad['DATA_LENGTH'])

      if ad['DATA_ADDR'][0] not in PLC_ADDR_ENUM:
        print("Address check error: ", ad['DATA_ADDR'])
        _LOGGER.error ("Address check error: "+ str(ad['DATA_ADDR']))
        return None
    
      if ad['DATA_TYPE'] in PLC_DTYPE_ENUM:
        print("Type check OK: ", ad['DATA_TYPE'])
        
        if ad['DATA_TYPE'] == PLC_DTYPE_INT or ad['DATA_TYPE'] == PLC_DTYPE_UINT:
          strFuncName = "self.p_device.Read"+ad['DATA_TYPE'].title() + str(ad['DATA_LENGTH'])
          print("PLCDevice --> read_data: strFuncName is ", strFuncName)
#          result = locals()[strFuncName](ad['DATA_ADDR'])
#          print("Result = ", result)
        elif ad['DATA_TYPE'] == PLC_DTYPE_STRING:
          strFuncName = "self.p_device.ReadString"
          print("PLCDevice --> read_data: strFuncName is ", strFuncName)
        elif ad['DATA_TYPE'] == PLC_DTYPE_BLOCK:
          strFuncName = "self.p_device.Read"
          print("PLCDevice --> read_data: strFuncName is ", strFuncName)
          result = self.p_device.Read(ad['DATA_ADDR'], int(ad['DATA_LENGTH']))
          print("PLCDevice --> read_data: result.content is ", str(result.Content))
#          result = locals()[strFuncName](ad['DATA_ADDR'], ad['DATA_LENGTH'])
#          print("Result = ", result)
        else: # For PLC_DTYPE_FLOAT and PLC_DTYPE_DOUBLE
          strFuncName = "self.p_device.Read" + ad['DATA_TYPE'].title()
          print("PLCDevice --> read_data: strFuncName is ", strFuncName)
        
        tmp = binascii.hexlify(result.Content)
        print("result.Content = ", tmp)
      
        edc_array.append({'DATA_NAME':ad['DATA_NAME'], 'DATA_VALUE':tmp.decode('utf-8')})
        
#          result = locals()[strFuncName](ad['DATA_ADDR'])
#          print("Result = ", result)

#        result = locals()[strFuncName](ad['DATA_ADDR'], ad['DATA_LENGTH'])
      else:
        print("Type check NG")
        _LOGGER.error("Type check NG")
        return None

    ret_json.update({'EDC_Data':edc_array})
    print("PLCDevice --> read_data:   ret_json : ", ret_json)
    
    return json.dumps(ret_json)

  def generate_messages(self, send_topic, json_msg):
    messages = []
    #if not self.message_sent and self.has_time_elapsed():
    #if not self.has_time_elapsed():
      #self.message_sent = True
    
    #json_msg = self.read_data()
    print("PLCDevice --> generate_messages: json_msg = ", json_msg)
    
    messages.append(
#      MqttMessage(topic=self.worker.format_topic('presence/{}'.format(self.name)), payload=(json_msg))
      MqttMessage(topic=(send_topic), payload=(json_msg))
    )
    #if self.available:
    #  messages.append(
    # MqttMessage(topic=self.worker.format_topic('presence/{}/rssi'.format(self.name)), payload=("rssi"))
    #)

    return messages

class MelsecplcWorker(BaseWorker):

  melsecPlc_Setting =  settings['manager']['workers']['melsecplc']
  gateway_id = None
  device_name = None
  if 'topic_subscription' in melsecPlc_Setting:
      _,_, gateway_id, device_name, cmd_type, cmd = melsecPlc_Setting['topic_subscription'].split('/')

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
  count = 0
  

  # Defined Puhlish MQTT Topic 
  ReadData_Topic  =  "/IEW/{gateway}/{device}/ReplyData"
  HeartBeat_Topic = "/IEW/{gateway}/{device}/Status/HeartBeat"
  Alarm_Topic = "/IEW/{gateway}/{device}/Status/Alarm"

  ReadData_job_id = '{}_interval_job'.format("ReadData")
  Version = "1.0"
  Status = "Init"
  
  Job_queue = queue(maxsize = 10)

  _LOGGER.info("Version = "+ Version ) 
  _LOGGER.info("MelsecPLC Class Initial Funished")
  _LOGGER.info("Setting Gateway_ID  = "+ gateway_id + ", Device_ID = " + device_name )
  _LOGGER.info("ReadData_Topic = "+ ReadData_Topic)
  _LOGGER.info("HeartBeat_Topic = "+ HeartBeat_Topic)
 

    
  def __init__(self, command_timeout, **kwargs):
  
    super(MelsecplcWorker, self).__init__(command_timeout, **kwargs)
    self._scheduler = BackgroundScheduler(timezone=utc)
    self._scheduler.add_job(self.Read_PLC_Data, 'interval', seconds=10, id=self.ReadData_job_id)
    self._scheduler.start()

    # Apschedule 不要紀錄 Logger 
    logging.getLogger('apscheduler.executors.default').propagate = False
   
    self.Status = "Init"
    _LOGGER.info("MelsecplcWorker --> starts = " +  self.Status)  

    self.report_alarm( '0000', 'Info', 'MelsecplcWorker is Initial')
    
   
  def run(self, mqtt):
    
     while True:
       time.sleep(1)
       if self.Job_queue.empty() == True:
           continue
       else:
          try :
             SendOutMQTT = self.Job_queue.get()
             mqtt.publish(SendOutMQTT) 
          except Exception as ee:
             logger.log_exception(_LOGGER, 'MelsecplcWorker --> Publish Error Msg : %s', str(ee))
             
             
  def create_devices(self):
    if not self.start_to_collect:
      self.last_status = []

      for device_name, dev_info in self.devices.items():
        _LOGGER.info("MelsecplcWorker --> create_devices : device_name = " + device_name)
        for d in dev_info:
          _LOGGER.info("MelsecplcWorker --> create_devices : ip_addr = " + d['IP_ADDR'])
          _LOGGER.info("MelsecplcWorker --> create_devices : port_id = " + d['PORT_ID'])
          self.last_status = [
            PLCDevice(self, d['IP_ADDR'], d['PORT_ID'], device_name)
          ]
          
      self.start_to_collect = True

  def set_stop_flag(self):
    self.start_to_collect = False
    self.flag_started = False


  def Read_PLC_Data(self):
      
    if self.start_to_collect and self.flag_started:
       self.count += 1
       if self.count > 65535:
          self.count =1
        
       _LOGGER.debug("MelsecplcWorker --> ReadPLC Data enters count = "+ str( self.count))
       sendout_topic =  self.ReadData_Topic.replace("{gateway}", self.gateway_id ).replace("{device}", self.device_name)

       # 成功讀取狀態改為Run
       try:
          for status in self.last_status:
             json_msg = status.read_data(self.addr_array)
             status.set_status(status is not None)
             self.Job_queue.put([MqttMessage(topic=sendout_topic, payload=json_msg)])
             _LOGGER.info("MelsecplcWorker --> Report Read PLC Data: " + json_msg )
             self.Status = "Run"
       except Exception as ee:
             logger.log_exception(_LOGGER, 'MelsecplcWorker --> Read Data Excepting. Msg : %s', str(ee))
             self.Status = "Down"
             # Read Data Error Send Error to MQTT
        
    else:
      _LOGGER.info("MelsecplcWorker --> status_update: Waiting for Collect Command!")


  def read_payload_cmd_start(self, device_name, payload, topic):
     
    try:
      cmd_start = {}
      cmd_start = json.loads(payload)
        
      _LOGGER.info("MelsecplcWorker --> read_payload_cmd_start: payload = "+ payload)
      _LOGGER.info("MelsecplcWorker --> read_payload_cmd_start: cmd_start = "+ str(cmd_start))
      _LOGGER.info("MelsecplcWorker --> read_payload_cmd_start: cmd_start['Device_Info] = "+ str(cmd_start['Device_Info']))
      sendout_topic =  topic + "/Ack"
      
      if cmd_start['Cmd_Type'] =="Start" :
          connect_status = 'OK'

          self.devices.update({device_name:cmd_start['Device_Info']})

          # 連線設定完成
          if not self.start_to_collect:
            self.create_devices()

          for status in self.last_status:
             if status.p_device == None:
                 connect_status = 'NG'

          ret_json = {}
          ret_json.update({'Cmd_Result': connect_status})
          ret_json.update({'Trace_ID':cmd_start['Trace_ID']})
          json_msg = json.dumps(ret_json)
          self.Job_queue.put([MqttMessage(topic=sendout_topic, payload=json_msg)])

          if connect_status == 'NG':
             self.Status = "Down"
             self.report_alarm( '1001', 'ERROR', 'Connected PLC Faild')
          else:
             self.Status = "Ready"
             self.report_alarm( '0001', 'INFO', 'Connected PLC successed')
          
      else:
          ret_json = {}
          ret_json.update({'Cmd_Result':"NG"})
          ret_json.update({'Trace_ID':cmd_start['Trace_ID']})
          json_msg = json.dumps(ret_json)
          self.Job_queue.put([MqttMessage(topic=sendout_topic, payload=json_msg)])
          # 補送Alarm to MQTT
          self.report_alarm( '1002', 'ERROR', 'Cmd_Type not Start')
        
    except Exception as ee:
      logger.log_exception(_LOGGER, 'Cmd Start Exception Error Msg : %s', str(ee))
      self.Status = "Down"
      ret_json = {}
      ret_json.update({'Cmd_Result':"NG"})
      ret_json.update({'Trace_ID':cmd_start['Trace_ID']})
      json_msg = json.dumps(ret_json)
      self.Job_queue.put([MqttMessage(topic=sendout_topic, payload=json_msg)])
       # 補送Alarm to MQTT
      self.report_alarm( '1003', 'ERROR', 'Cmd_Type Start happened exception error :' + str(ee))

     

  def read_payload_cmd_readdata(self, device_name,  payload, topic):
   
    try:
      cmd_read = {}
      cmd_read = json.loads(payload)
      
      _LOGGER.info("MelsecplcWorker --> read_payload_cmd_parameter: cmd_parameter = "+ str(cmd_read))
      sendout_topic =  topic + "/Ack"
      
      if cmd_read['Cmd_Type'] =="Collect" :
          self.addr_array = cmd_read['Address_Info']
          interval = int(cmd_read['Report_Interval'])
      
          self.flag_started = False
          self._scheduler.pause()
          self._scheduler.reschedule_job(job_id=self.ReadData_job_id,trigger='interval',seconds=interval)
          self._scheduler.resume()
          self.flag_started = True
      
          ret_json = {}
          ret_json.update({'Cmd_Result':"OK"})
          ret_json.update({'Trace_ID':cmd_read['Trace_ID']})
          json_msg = json.dumps(ret_json)
          self.Job_queue.put([MqttMessage(topic=sendout_topic, payload=json_msg)])

          
      else:
          ret_json = {}
          ret_json.update({'Cmd_Result':"NG"})
          ret_json.update({'Trace_ID':cmd_read['Trace_ID']})
          json_msg = json.dumps(ret_json)
          self.Job_queue.put([MqttMessage(topic=sendout_topic, payload=json_msg)])
          _LOGGER.error("MelsecplcWorker --> read_payload_cmd_NG tpye not Collect, cmd_read_type = "+ str(cmd_read['Cmd_Type']))
          # 補送Alarm to host
          self.report_alarm( '1004', 'ERROR', 'Type not Collect')
      
    except Exception as ee:
      logger.log_exception(_LOGGER, 'Cmd Start Exception Error Msg : %s', str(ee))
      ret_json = {}
      ret_json.update({'Cmd_Result':"NG"})
      ret_json.update({'Trace_ID':cmd_read['Trace_ID']})
      json_msg = json.dumps(ret_json)
      self.Job_queue.put([MqttMessage(topic=sendout_topic, payload=json_msg)])
      self.Status = "Down"
      self.report_alarm( '1005', 'ERROR', 'Cmd_Type Collect happened exception error :' + str(ee))

      
    
  def read_payload_parameter_request(self, device_name, payload):
    parameter_request = {}
    parameter_request = json.loads(payload)
    _LOGGER.info("MelsecplcWorker --> read_payload_parameter_request: parameter_request = "+ parameter_request)

  def cmd_stop(self, value):
    if value == KILL_ME:
      sys.exit("END")
    elif value == STOP_COLLECT:
      self._scheduler.pause()
      for status in self.last_status:
        self.set_stop_flag()
        self.last_status = None

  def status_update(self):
      
    _LOGGER.info("MelsecplcWorker --> Heartbit Report")
    now = datetime.datetime.now()
    sendout_topic =  self.HeartBeat_Topic.replace("{gateway}", self.gateway_id ).replace("{device}", self.device_name)

    HB_json = {}
    HB_json.update({'Version': self.Version})
    HB_json.update({'Status': self.Status})
    HB_json.update({'HBDatetime': now.strftime("%Y%m%d%H%M%S%f")[:-3]})
    json_msg = json.dumps(HB_json)
    _LOGGER.debug("Heartbit Report : " + json_msg)

    ret =[]
    messages = []
    messages.append(MqttMessage(topic = sendout_topic, payload = json_msg))

    ret += messages

    return ret

  def report_alarm(self, code, level, desc):
      
   
    now = datetime.datetime.now()
    report_alarm_Topic =  self.Alarm_Topic.replace("{gateway}", self.gateway_id ).replace("{device}", self.device_name)

    Alarm_json = {}
    Alarm_json.update({'AlarmCode': code})
    Alarm_json.update({'AlarmLevel': level})
    Alarm_json.update({'AlarmApp': 'WORKER'})
    Alarm_json.update({'DateTime': now.strftime("%Y%m%d%H%M%S%f")[:-3]})
    Alarm_json.update({'AlarmDesc': desc})
    json_msg = json.dumps(Alarm_json)

    self.Job_queue.put([MqttMessage(topic = report_alarm_Topic, payload = json_msg)])
    _LOGGER.error ("MelsecplcWorker --> Report Alarm to Host Msg : " + str(json_msg))
    

  def on_command(self, topic, value):
      
    value = value.decode('utf-8')\

    # 設定改在其他地方
    _,_, gateway_id, device_name, cmd_type, cmd = topic.split('/')

    if cmd_type == "Cmd":
        
      _LOGGER.info("MelsecplcWorker --> on_command: topic = "+ topic)
      _LOGGER.info("MelsecplcWorker --> on_command: gateway_id = "+ gateway_id)
      _LOGGER.info("MelsecplcWorker --> on_command: device_name = "+ device_name)
      _LOGGER.info("MelsecplcWorker --> on_command: cmd_type = "+ cmd_type)
      _LOGGER.info("MelsecplcWorker --> on_command: cmd = "+ cmd)

      if cmd == "Start":
        self.read_payload_cmd_start(device_name, value, topic)
      elif cmd == "ReadData":
        self.read_payload_cmd_readdata(device_name, value, topic)
      elif cmd == "Stop":
        self.cmd_stop(value)
        _LOGGER.error("MelsecplcWorker --> on_command = "+ cmd + "Stop Collect Data")
        self.Status = "Idle"

      elif cmd == "OTA":
        OTA_json = {}
        OTA_json.update({'Version': self.Version})
        OTA_json.update({'Status': self.Status})
        OTA_json.update({'HBDatetime': now.strftime("%Y%m%d%H%M%S%f")[:-3]})
        OTA_json.update({'ProcrssID': os.getpid()})
        json_msg = json.dumps(OTA_json)
        sendout_topic =  topic + "/Ack"
        self.Job_queue.put([MqttMessage(topic=sendout_topic, payload=json_msg)])
        time.sleep(5)
        self.cmd_stop("kill")

    elif cmd_type == "Parameter":
      if cmd == "Request":
        self.read_payload_parameter_request(device_name, value)
