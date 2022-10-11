#!/usr/bin/env python

from operator import invert
import RS485Ext
from pymodbus.client.sync import ModbusSerialClient
from pymodbus.client.sync import ModbusTcpClient
from influxdb import InfluxDBClient
from datetime import datetime, time
import time
from threading import Thread
from pymodbus.payload import BinaryPayloadBuilder, Endian, BinaryPayloadDecoder


print ("Load modbus map sungrow-sg5d")
modmap_file = "s100-map"
modmap = __import__(modmap_file)
flux_client = InfluxDBClient('nick.lan', 8086, 'grafana', 'grafana', 'metrics', ssl=False, verify_ssl=False)

def publish_influx(inverter):
  metrics = {}
  tags = {}
  metrics['measurement'] = "Power"
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


def validateInverter(client=None):
  if (client is None) or (client.is_socket_open() == False):
    print("Sungrow Client is not connected")
    client = connectInverter()
  return client

def connectInverter():
  print("Connecting Sungrow...")
  ser=RS485Ext.RS485Ext(port='/dev/serial0', baudrate=9600, timeout=5)
  client = ModbusSerialClient(method='rtu')
  client.socket = ser
  client.connect()
  return client


def validateVictron(client=None):
  if (client is None) or (client.is_socket_open() == False):
    print("Victron Client is not connected")
    client = connectVictron()
  return client

def connectVictron():
  print("Connecting Victron...")
  tcplient = ModbusTcpClient("192.168.1.85", timeout=3, RetryOnEmpty=True, retries=3, port=502)
  tcplient.connect()
  return tcplient


def validateS100(client=None):
  if (client is None) or (client.is_socket_open() == False):
    print("S100 Energy Monitor Client is not connected")
    client = connectS100()
  return client
  
def connectS100():
  print("Connecting S100...")
  client = ModbusSerialClient(method='rtu', port='/dev/ttyUSB0', stopbits = 1, bytesize = 8, parity = 'N' , baudrate= 9600)
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

def SetVictron(rate, disableCharge, disableFeed):
  builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
  builder.reset()
  builder.add_16bit_int(int(rate))
  payload = builder.to_registers()
  victronClient.write_register(37, payload[0], unit=228)
  victronClient.write_register(38, disableCharge, unit=228)
  victronClient.write_register(39, disableFeed, unit=228)
  print ("New Setpoint: " + str(rate))
  
  
  
while True:
  print ("Waiting")
  time.sleep(15)
  inverter = {}
  inverterClient = validateInverter()
  victronClient = validateVictron()
  s100Client = validateS100()
  solargen = 0
  houseuse = 0
  vicinverter = 0

  importDemand = 0
  exportDemand = 0

  #Get Inverter Data
  if (isConnected(inverterClient) == False):
    print ("Solar is Offline, setting data zero")
    inverter["inverter"] = 0
  else:
    print ("Online, Getting Data")
    rr = inverterClient.read_input_registers(5016, count=1, unit=1)
    if ("Exception" not in str(rr)) and ("Error" not in str(rr) and ("ModbusIOException" not in str(rr))):
      solargen = rr.registers[0]
      inverter["inverter"] = solargen
    else:
        print(str(rr))
  
  #Get S100 Data
  for addr in modmap.read_register:
    rr = s100Client.read_holding_registers(int(addr), unit=32)
    if ("Exception" not in str(rr)) and ("Error" not in str(rr) and ("ModbusIOException" not in str(rr))):
      inverter[str(addr)] = rr.registers[0]
      if (int(addr) == 10):
        decoder = BinaryPayloadDecoder.fromRegisters(rr.registers, byteorder=Endian.Big, wordorder=Endian.Big)
        houseuse = decoder.decode_16bit_int() / 10
        inverter["HouseUsagef"] = houseuse
    else:
      print(str(rr))

  print ("House Usage: " + str(houseuse))

  #Get Victron Watts
  rr = victronClient.read_input_registers(12, unit=228)
  decoder = BinaryPayloadDecoder.fromRegisters(rr.registers, byteorder=Endian.Big, wordorder=Endian.Big)
  vicinverter = decoder.decode_16bit_int() * 10
  inverter["Victron Watts"] = vicinverter
  print ("Victron Watts: " + str(vicinverter))

  if (vicinverter <= 0):
    #vic inverter exporting so its negative
    houseuseAdjusted = houseuse + vicinverter
  elif (vicinverter > 0):
    #vic inverter importing
    houseuseAdjusted = houseuse - vicinverter

  print ("House use Adjusted: " + str(houseuseAdjusted))
  inverter["HouseUsageAdjusted"] = float(houseuseAdjusted)

  #Super Off Peak - 0.2c per kWh - 9am to 3pm
  #Charge Cycle, from 9am to 2:59pm Charge battery
  #Always charge 500w if there is no surplus
  #If there is a surplus between 0w and 1200w, charge at a max of 1200w
  #If there is a surplus of over 1200w then import at max. 
  #Hard coded limits that dont follow solar surplus exactly incase of cloudy days.
  if (in_between(datetime.now().time().hour, 9, 14)):
    if (vicinverter in range(-10,10)):
      print ("Adding Base import")
      importDemand = 500
    else:
      if (houseuseAdjusted < 0 and houseuseAdjusted > -1200):
        print ("Adding 50% charge to import")
        importDemand = 1200
      if (houseuseAdjusted < -1200):
        print ("Adding 100% charge to import")
        importDemand = 2400
    SetVictron(importDemand, 0, 1)
    inverter["SetPoint"] = float(importDemand)

  #Peak - 0.5c per Kwh - 3pm to 9pm
  #Discharge Cycle, from 3pm to 9:59pm track house usage and match export.
  if (in_between(datetime.now().time().hour, 15, 22)):
    if (houseuse < -100 and vicinverter in range(-10,10)):
      print ("Solar surplus, doing nothing.")
      exportDemand = 0
    elif (houseuse > -100 and vicinverter > 0):
      print ("Energy demand increasing, Adding a base export demand")
      exportDemand = -150
    else:
      if (int(houseuse) in range(-200,0)):
        exportDemand = vicinverter 
        print ("Current export demand is close to house usage, leaving")
      elif (houseuse >= 0):
        exportDemand = vicinverter - (houseuse + 150)
        print ("Current export demand is not meeting house load, increasing export")
      elif (houseuse < -200):
        exportDemand = vicinverter - (houseuse - -150)
        print ("Current export demand is exceeding house load by too much, decreasing export")
      else:
        print ("Couldn't figure out what to do!")
    SetVictron(exportDemand, 1, 0)
    inverter["SetPoint"] = float(exportDemand)

  #Off Peak - 0.22c per Kwh - 9pm to 9pm
  #Discharge Cycle, from 5am to 8:59pm track house usage and match export.
  #Only bother covering the early morning period when demand is high before solar covers usage
  #Leave overnight base load to be imported 
  if (in_between(datetime.now().time().hour, 5, 9)):
    if (houseuse < -100 and vicinverter in range(-10,10)):
      print ("Solar surplus, doing nothing.")
      exportDemand = 0
    elif (houseuse > -100 and vicinverter > 0):
      print ("Energy demand increasing, Adding a base export demand")
      exportDemand = -150
    else:
      if (houseuse in range(-200,0)):
        exportDemand = vicinverter 
        print ("Current export demand is close to house usage, leaving")
      elif (houseuse >= 0):
        exportDemand = vicinverter - (houseuse + 150)
        print ("Current export demand is not meeting house load, increasing export")
      elif (houseuse < -200):
        exportDemand = vicinverter - (houseuse - -150)
        print ("Current export demand is exceeding house load by too much, decreasing export")
    SetVictron(exportDemand, 1, 0)
    inverter["SetPoint"] = float(exportDemand)

  if (in_between(datetime.now().time().hour, 22, 4)):
    print ("Waiting until 5am to resume export")
    SetVictron(0, 1, 1)
    inverter["SetPoint"] = float(0)

#  if (houseuse in range(-200,200)):
#    print ("House use at acceptabe levels, leaving set point: " + str(vicinverter))










  #if (in_between(datetime.now().time().hour, 9, 14)):
  #  importDemand = solargen - (abs(houseuse) - vicinverter)   #eg 5000 - (3000 - 1000) = 3000W surplus
  #  if (importDemand < 1200):                                 #if surplus is less than 1000W override the system to pull 1000W so battery is always charging at atleast 50% rate. 
  #    importDemand = 1200  
  #  if (importDemand > 2400):                                 
  #    importDemand = 2400
  #  inverter["OPImportDemand"] = importDemand
  #  SetVictron(importDemand)
  
  #if (in_between(datetime.now().time().hour, 15, 21)):
  #  exportDemand = solargen - (abs(houseuse) - vicinverter)   #eg 1000 - (3000 - 1000) = -1000W Demand or # 0 - (0 - 1500)

  #House use adjusted should show the true house S100 value by remmoving the vitron value
  #houseuseAdjusted = 0
  #if (vicinverter <= 0):
    #vic inverter exporting so its negative
  #  houseuseAdjusted = houseuse + vicinverter
  #elif (vicinverter > 0):
    #vic inverter importing
  #  houseuseAdjusted = houseuse - vicinverter

  #energyState = houseuseAdjusted
  #Flip the house usage value so the inverter exports or imports correctly
  #if (houseuseAdjusted > 0):
  #  energyState = -abs(houseuseAdjusted)
  #elif (houseuseAdjusted < 0):
  #  energyState = abs(houseuseAdjusted)

  #Add smoothing to inverter set point, If its close to the desired point just leave it, should help with flapping on and off 
  #if (energyState in range(vicinverter-200,vicinverter+200)):
  #  print("Close enough, matching the existing value, Calculated: "+energyState)
  #  energyState = vicinverter
    
  

  #print ("House Use Adjusted: " + str(houseuseAdjusted))
  #print ("Energy command: " + str(energyState))

  #inverter["HouseUsageAdjusted"] = float(houseuseAdjusted)
  #inverter["HouseUsageTotal"] = float(houseuse) + float(solargen)
  #inverter["EnergyStatef"] = float(energyState)

  
  #inverter["setpoint"] = energyState

  #if (energyState > 250):
  #  if (energyState > 2400):
  #    victronClient.write_register(37, 2400, unit=228)
  #    victronClient.write_register(38, 0, unit=228)
  #    victronClient.write_register(39, 0, unit=228)
  #    inverter["setpoint"] = 2400
  #  else:
  #    victronClient.write_register(37, energyState, unit=228)
  #    inverter["setpoint"] = energyState


  rr = victronClient.read_input_registers(844, unit=100)
  inverter["Battery State"] = rr.registers[0] 

  rr = victronClient.read_input_registers(30, unit=228)
  inverter["Battery Level"] = rr.registers[0]

  rr = victronClient.read_input_registers(844, unit=100)
  inverter["Battery State"] = rr.registers[0]

  rr = victronClient.read_input_registers(26, unit=228)
  inverter["Battery Voltage"] = rr.registers[0]

  rr = victronClient.read_input_registers(27, unit=228)
  inverter["Battery Current"] = rr.registers[0]

  if flux_client is not None:
    t = Thread(target=publish_influx, args=(inverter,))
    t.start()
  print ("----------------------------------------------------------")