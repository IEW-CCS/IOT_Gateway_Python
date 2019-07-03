from mqtt import MqttMessage
from bluepy.btle import Scanner, DefaultDelegate
from workers.base import BaseWorker
import logger

REQUIREMENTS = ['pyserial']
_LOGGER = logger.get(__name__)

class ScanDelegate(DefaultDelegate):
  def __init__(self):
    DefaultDelegate.__init__(self)

  def handleDiscovery(self, dev, isNewDev, isNewData):
    if isNewDev:
      _LOGGER.debug("Discovered new device: %s" % dev.addr)


class MybleWorker(BaseWorker):
  def run(self, mqtt):
      print("this is run status")
      
      
  def generate_messages(self, device):
    messages = []

    messages.append( MqttMessage(topic=self.worker.format_topic('presence/{}/mac'.format(self.name)), payload=device.addr))
    messages.append( MqttMessage(topic=self.worker.format_topic('presence/{}/rssi'.format(self.name)), payload=device.rssi))
     
    return messages

  def status_update(self):
      print("this is BLE Scan update")
      ret = []
      scanner = Scanner().withDelegate(ScanDelegate())
      devices = scanner.scan(10.0)

      for dev in devices:
         ret += self.generate_messages(dev)
      return ret
     