#!/usr/bin/env python

from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
from pymodbus.client.sync import ModbusTcpClient
from influxdb import InfluxDBClient
import json
import time
import datetime
import requests
from threading import Thread
import os

MIN_SIGNED   = -2147483648
MAX_UNSIGNED =  4294967295

MODEL = os.getenv('model', 'sungrow-sg5d')
INVIP = os.getenv('inverter_ip', '')
INVPORT = int(os.getenv('inverter_port', 502))
INVTIMEOUT = int(os.getenv('timeout', 3))

INFIP = os.getenv('influxdb_ip', '')
INFPORT = int(os.getenv('influxdb_port', 8086))
INFUSER = os.getenv('influxdb_user', 'influxuser')
INFPASSWORD = os.getenv('influxdb_password', 'influxpassword')
INFDATABASE = os.getenv('influxdb_database', 'inverter')

MODID = int(os.getenv('modbus_slave', 0x01))
MODINTV = int(os.getenv('scan_interval', 10))


requests.packages.urllib3.disable_warnings() 

print ("Load modbus map %s" % MODEL)

modmap_file = "modbus-" + MODEL
modmap = __import__(modmap_file)

client = ModbusTcpClient(INVIP, 
                         timeout=INVTIMEOUT,
                         RetryOnEmpty=True,
                         retries=3,
                         port=INVPORT)
client.connect()

try:
  flux_client = InfluxDBClient(INFIP,
                               INFPORT,
                               INFUSER,
                               INFPASSWORD,
                               INFDATABASE,
                               ssl=False,
                               verify_ssl=False)
except:
  flux_client = None

inverter = {}

def publish_influx(metrics):
  target=flux_client.write_points([metrics])
  print ("Sent to InfluxDB")

#ping inverter to see if its on?
while True:
  time.sleep(MODINTV)
  try:
    inverter = {}
    print ("Getting Data")
    for addr in modmap.read_register:
      rr = client.read_input_registers(int(addr), count=1, unit=MODID)
      if ("Exception" not in str(rr)) and ("Error" not in str(rr) and ("ModbusIOException" not in str(rr))):
        inverter[str(addr)] = rr.registers[0]
      else:
        print(str(rr))

    print("Loaded Data from Inverter, Sending to Influx")

    if flux_client is not None:
      metrics = {}
      tags = {}
      fields = {}
      metrics['measurement'] = "Sungrow"
      tags['location'] = "Home"
      metrics['tags'] = tags
      metrics['fields'] = inverter
      t = Thread(target=publish_influx, args=(metrics,))
      t.start()

    print ("Sent to Influx")
  except Exception as e:
    for addr in modmap.read_register:
      inverter[str(addr)] = 0
    metrics = {}
    tags = {}
    fields = {}
    metrics['measurement'] = "Sungrow"
    tags['location'] = "Home"
    metrics['tags'] = tags
    metrics['fields'] = inverter
    t = Thread(target=publish_influx, args=(metrics,))
    t.start()
    try:
      print(str(rr))
    except NameError:
      print("Exception, Sent zeroed data to Influx assuming inverter offline")