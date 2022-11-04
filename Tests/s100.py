#!/usr/bin/env python

import RS485Ext
from pymodbus.client.sync import ModbusSerialClient
from influxdb import InfluxDBClient
from datetime import datetime, time
import time
from threading import Thread

client = ModbusSerialClient(method='rtu', port='/dev/ttyUSB0', stopbits = 1, bytesize = 8, parity = 'N' , baudrate= 9600)
client.connect()
rr = client.read_holding_registers(0, unit=32)
rr = client.read_holding_registers(10, unit=32)
print ("Reading 10 value " + str(rr.registers[0]))

print ("Load modbus map")
modmap_file = "s100-map"
modmap = __import__(modmap_file)
flux_client = InfluxDBClient('nick.lan', 8086, 'grafana', 'grafana', 'metrics', ssl=False, verify_ssl=False)


def publish_influx(inverter):
  metrics = {}
  tags = {}
  metrics['measurement'] = "S100"
  tags['location'] = "Home"
  metrics['tags'] = tags
  metrics['fields'] = inverter
  flux_client.write_points([metrics])
  print ("Sent to InfluxDB")


while True:
  print ("Waiting")
  time.sleep(15)
  inverter = {}
  client = ModbusSerialClient(method='rtu', port='/dev/ttyUSB0', stopbits = 1, bytesize = 8, parity = 'N' , baudrate= 9600)
  client.connect()
  for addr in modmap.read_register:
    rr = client.read_holding_registers(int(addr), unit=32)
    
    if ("Exception" not in str(rr)) and ("Error" not in str(rr) and ("ModbusIOException" not in str(rr))):
      inverter[str(addr)] = rr.registers[0]
    else:
      print(str(rr))
    print ("Reading "+ addr + " value " + str(rr.registers[0]))

  if flux_client is not None:
    t = Thread(target=publish_influx, args=(inverter,))
    t.start()
  print ("----------------------------------------------------------")