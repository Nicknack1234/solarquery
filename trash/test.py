import RS485Ext
from pymodbus.client.sync import ModbusSerialClient


ser=RS485Ext.RS485Ext(port='/dev/serial0', baudrate=9600, timeout=5)
client = ModbusSerialClient(method='rtu')
client.socket = ser
client.connect()
result = client.read_input_registers(address=5007, count=1, unit=1)



import minimalmodbus
#import RPi.GPIO as GPIO
#import ctypes

#GPIO.setmode(GPIO.BCM)
#GPIO.setup(18, GPIO.OUT)
#writec = ctypes.cdll.LoadLibrary('/home/pi/solar_code/writec.so')

#def switch(instrument, is_write):
#    instrument.serial.flush()
#    print("CallBack")
#    if is_write:
#        GPIO.output(18, GPIO.HIGH)
#    if not is_write:
#        GPIO.output(18, GPIO.LOW)

instrument = minimalmodbus.Instrument('/dev/serial0', 1, minimalmodbus.MODE_RTU)  # port name, slave address (in decimal)
instrument.serial.baudrate = 9600         # Baud
instrument.serial.bytesize = 8
instrument.serial.stopbits = 1
instrument.serial.timeout  = 2          # seconds
#instrument.mode = minimalmodbus.MODE_RTU
instrument.clear_buffers_before_each_transaction = False
#r = writec.init()

temperature = instrument.read_register(5007)





from pymodbus.client import ModbusSerialClient
client = ModbusSerialClient(method='rtu', port='/dev/serial0', baudrate=9600, timeout=3)
client.connect()
result = client.read_input_registers(address=5000, count=10, unit=1)
print(result)