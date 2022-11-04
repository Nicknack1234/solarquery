#!/usr/bin/env python

import RS485Ext
from pymodbus.client.sync import ModbusSerialClient
from influxdb import InfluxDBClient
from datetime import datetime, time
import time
from threading import Thread


print ("Load modbus map sungrow-sg5d")
modmap_file = "modbus-sungrow-sg5d"
modmap = __import__(modmap_file)
flux_client = InfluxDBClient('nick.lan', 8086, 'grafana', 'grafana', 'metrics', ssl=False, verify_ssl=False)


def publish_influx(inverter):
  metrics = {}
  tags = {}
  metrics['measurement'] = "Sungrow"
  tags['location'] = "Home"
  metrics['tags'] = tags
  metrics['fields'] = inverter
  flux_client.write_points([metrics])
  print ("Sent to InfluxDB")

def in_between(now, start, end):
  if start <= end:
      return start <= now < end
  else:
      return start <= now or now < end

def validateModbus(client=None):
  if (client is None) or (client.is_socket_open() == False):
    print("Client is null or not connected")
    client = connectModBus()
  return client

def connectModBus():
  print("Connecting...")
  ser=RS485Ext.RS485Ext(port='/dev/serial0', baudrate=9600, timeout=5)
  client = ModbusSerialClient(method='rtu')
  client.socket = ser
  client.connect()
  return client

def isConnected(client):
  try:
    rr = client.read_input_registers(5007, count=1, unit=1)
    if ("Exception" not in str(rr)) and ("Error" not in str(rr) and ("ModbusIOException" not in str(rr))):
      return True
    else:
      return False
  except:
    return False


while True:
  print ("Waiting")
  time.sleep(60)
  inverter = {}
  client = validateModbus()
  if (isConnected(client) == False):
    print ("Offline, setting data zero")
    for addr in modmap.read_register:
      inverter[str(addr)] = 0
  else:
    print ("Online, Getting Data")
    for addr in modmap.read_register:
      rr = client.read_input_registers(int(addr), count=1, unit=1)
      if ("Exception" not in str(rr)) and ("Error" not in str(rr) and ("ModbusIOException" not in str(rr))):
        inverter[str(addr)] = rr.registers[0]
      else:
        print(str(rr))

  if flux_client is not None:
    t = Thread(target=publish_influx, args=(inverter,))
    t.start()
  print ("----------------------------------------------------------")