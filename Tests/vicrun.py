#!/usr/bin/env python

from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
from pymodbus.client.sync import ModbusTcpClient
from influxdb import InfluxDBClient
from pymodbus.payload import BinaryPayloadBuilder, Endian, BinaryPayloadDecoder
import json
import time
import datetime
import requests
from threading import Thread
import os


#print ("Load modbus map sungrow-sg5d")
#modmap_file = "victron"
#modmap = __import__(modmap_file)
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
    client = connectVictronModBus()
  return client

def connectVictronModBus():
  print("Connecting...")
  tcplient = ModbusTcpClient("192.168.1.85", timeout=3, RetryOnEmpty=True, retries=3, port=502)
  tcplient.connect()
  return tcplient


while True:
  print("Running...")
  time.sleep(5)
  tcplient = ModbusTcpClient("192.168.1.85", timeout=3, RetryOnEmpty=True, retries=3, port=502)
  tcplient.connect()

  builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
  builder.reset()
  builder.add_16bit_int(500)
  payload = builder.to_registers()

  tcplient.write_register(37, payload[0], unit=228)
  tcplient.write_register(38, 0, unit=228)
  tcplient.write_register(39, 0, unit=228)
  
  rr = tcplient.read_input_registers(37, unit=228)
  print(str(rr.registers[0]))

  rr = tcplient.read_input_registers(38, unit=228)
  print(str(rr.registers[0]))

  rr = tcplient.read_input_registers(39, unit=228)
  print(str(rr.registers[0]))