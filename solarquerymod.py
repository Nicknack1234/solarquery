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
import logging
from logging.handlers import RotatingFileHandler

# create logger
logger = logging.getLogger('simple_example')
logger.setLevel(logging.INFO)

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# create formatter
formatter = logging.Formatter('%(asctime)s - %(message)s')
handler = RotatingFileHandler("/home/pi/SOLARRUN/sungrow-logfile.log", maxBytes=200000000, backupCount=5)

# add formatter to ch
ch.setFormatter(formatter)
handler.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)
logger.addHandler(handler)

logger.info("Load modbus map sungrow-sg5d")
modmap_file = "s100-map"
modmap = __import__(modmap_file)
flux_client = InfluxDBClient('pi1.lan', 8086, 'grafana', 'grafana', 'metrics', ssl=False, verify_ssl=False)

def publish_influx(inverter):
  metrics = {}
  tags = {}
  metrics['measurement'] = "Power"
  tags['location'] = "Home"
  metrics['tags'] = tags
  metrics['fields'] = inverter
  flux_client.write_points([metrics])
  logger.info("Sent to InfluxDB")

def in_between(now, start, end):
  if start <= end:
      return start <= now < end
  else:
      return start <= now or now < end


def validateInverter(client=None):
  if (client is None) or (client.is_socket_open() == False):
    #print("Sungrow Client is not connected")
    client = connectInverter()
  return client

def connectInverter():
  logger.info("Connecting Sungrow...")
  ser=RS485Ext.RS485Ext(port='/dev/serial0', baudrate=9600, timeout=5)
  client = ModbusSerialClient(method='rtu')
  client.socket = ser
  client.connect()
  return client


def validateVictron(client=None):
  if (client is None) or (client.is_socket_open() == False):
    #print("Victron Client is not connected")
    client = connectVictron()
  return client

def connectVictron():
  logger.info("Connecting Victron...")
  tcplient = ModbusTcpClient("192.168.1.85", timeout=3, RetryOnEmpty=True, retries=3, port=502)
  tcplient.connect()
  return tcplient


def validateS100(client=None):
  if (client is None) or (client.is_socket_open() == False):
    #print("S100 Energy Monitor Client is not connected")
    client = connectS100()
  return client
  
def connectS100():
  logger.info("Connecting S100...")
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
  logger.info("New Setpoint: " + str(rate))
  
#This function should return the import and export demand of the house
#Should import when there is excess solar and 
def FollowDemand(battery, victron, house):
  if (int(house) in range(-25,25) and battery > 5):
    logger.info("Current export demand is close to house usage, leaving")
    return victron
  elif (house > 25):
    logger.info("Current export demand is not meeting house load, increasing export")
    return victron - (house + 25)
  elif (house < -25):
    logger.info("Current export demand is exceeding house load by too much, decreasing export")
    return victron - (house - -25)
  else:
    logger.info("Battery too low or logic issue, battery: "+str(battery))
    return 0


  
while True:
  logger.info("Waiting")
  time.sleep(5)
  inverter = {}
  inverterClient = validateInverter()
  victronClient = validateVictron()
  s100Client = validateS100()
  logger.info("***********************")
  solargen = 0
  houseuse = 0
  vicinverter = 0

  importDemand = 0
  exportDemand = 0
  batterylevel = 0

  #Get Inverter Data
  if (in_between(datetime.now().time().hour, 5, 19)):
    if (isConnected(inverterClient) == False):
      logger.info("Solar is Offline, setting data zero")
      inverter["inverter"] = 0
    else:
      logger.info("Online, Getting Data")
      rr = inverterClient.read_input_registers(5016, count=1, unit=1)
      if ("Exception" not in str(rr)) and ("Error" not in str(rr) and ("ModbusIOException" not in str(rr))):
        solargen = rr.registers[0]
        inverter["inverter"] = solargen
      else:
          logger.info(str(rr))
  else:
      logger.info("Ignoring solar")
      inverter["inverter"] = 0
  
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
      logger.info(str(rr))

  logger.info("House Usage: " + str(houseuse))

  #Get Victron Watts
  rr = victronClient.read_input_registers(12, unit=228)
  decoder = BinaryPayloadDecoder.fromRegisters(rr.registers, byteorder=Endian.Big, wordorder=Endian.Big)
  vicinverter = decoder.decode_16bit_int() * 10
  inverter["Victron Watts"] = vicinverter
  logger.info("Victron Watts: " + str(vicinverter))

  if (vicinverter <= 0):
    #vic inverter exporting so its negative
    houseuseAdjusted = houseuse + vicinverter
  elif (vicinverter > 0):
    #vic inverter importing
    houseuseAdjusted = houseuse - vicinverter

  logger.info("House use Adjusted: " + str(houseuseAdjusted))
  inverter["HouseUsageAdjusted"] = float(houseuseAdjusted)

  rr = victronClient.read_input_registers(844, unit=100)
  inverter["Battery State"] = rr.registers[0] 

  rr = victronClient.read_input_registers(30, unit=228)
  inverter["Battery Level"] = rr.registers[0]
  batterylevel = rr.registers[0] / 10

  rr = victronClient.read_input_registers(844, unit=100)
  inverter["Battery State"] = rr.registers[0]

  rr = victronClient.read_input_registers(26, unit=228)
  inverter["Battery Voltage"] = rr.registers[0]

  rr = victronClient.read_input_registers(27, unit=228)
  inverter["Battery Current"] = rr.registers[0]

  logger.info("***********************")


  #Super Off Peak - 0.2c per kWh - 9am to 3pm
  #Charge Cycle, from 9am to 2:59pm Charge battery
  #Always charge 500w if there is no surplus
  #If there is a surplus between 0w and 1200w, charge at a max of 1200w
  #If there is a surplus of over 1200w then import at max. 
  #Hard coded limits that dont follow solar surplus exactly incase of cloudy days.
  if (in_between(datetime.now().time().hour, 9, 15)):
    logger.info("Super Off Peak - 0.2c per kWh - 9am to 3pm")
    logger.info("Adding 100% charge to import")
    SetVictron(32700, 0, 0)
    inverter["SetPoint"] = float(importDemand)

  #Peak - 0.5c per Kwh - 3pm to 9pm
  #Discharge Cycle, from 3pm to 9pm track house usage and match export.
  if (in_between(datetime.now().time().hour, 15, 21) and  batterylevel > 4 ):
    logger.info("Peak - 0.5c per Kwh - 3pm to 9pm")
    demandCalc = FollowDemand(batterylevel, vicinverter, houseuse)
    SetVictron(demandCalc, 0, 0)
    inverter["SetPoint"] = float(demandCalc)

  #Off Peak - 0.22c per Kwh - 9pm to 9am
  #Discharge Cycle, from 5am to 8:59pm track house usage and match export.
  #Only bother covering the early morning period when demand is high before solar covers usage
  #Leave overnight base load to be imported 
  if (in_between(datetime.now().time().hour, 21, 6)):
    logger.info("Off Peak - 0.22c per Kwh - 9pm to 9am")
    demandCalc = FollowDemand(batterylevel, vicinverter, houseuse)
    if (batterylevel <= 20 and demandCalc < -150):
      logger.info("Battery is low, stopping export.")
      demandCalc = 0
    SetVictron(demandCalc, 0, 0)
    inverter["SetPoint"] = float(demandCalc)
  if (in_between(datetime.now().time().hour, 6, 9)):
    logger.info("Off Peak - 0.22c per Kwh - 9pm to 9am")
    demandCalc = FollowDemand(batterylevel, vicinverter, houseuse)
    if (batterylevel <= 15 and demandCalc > 150):
      logger.info("Battery is low, stopping export.")
      demandCalc = 0
    SetVictron(demandCalc, 0, 0)
    inverter["SetPoint"] = float(demandCalc)

  if flux_client is not None:
    t = Thread(target=publish_influx, args=(inverter,))
    t.start()
  logger.info("----------------------------------------------------------")