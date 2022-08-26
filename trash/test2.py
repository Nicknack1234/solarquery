
import minimalmodbus
import RPi.GPIO as GPIO
#import ctypes

GPIO.setmode(GPIO.BCM)
GPIO.setup(18, GPIO.OUT)
#writec = ctypes.cdll.LoadLibrary('/home/pi/solar_code/writec.so')

def switch(instrument, is_write):
    instrument.serial.flush()
    #print("CallBack")
    if is_write:
        GPIO.output(18, GPIO.HIGH)
    if not is_write:
        GPIO.output(18, GPIO.LOW)

instrument = minimalmodbus.Instrument('/dev/serial0', 1, before_transfer=switch)  # port name, slave address (in decimal)
instrument.serial.baudrate = 9600         # Baud
instrument.serial.bytesize = 8
instrument.serial.stopbits = 1
instrument.serial.timeout  = 0.25          # seconds
instrument.mode = minimalmodbus.MODE_RTU
instrument.clear_buffers_before_each_transaction = False
#r = writec.init()

temperature = instrument.read_register(5008, 1)
print("Temp "+str(temperature))

TotalActivePower = instrument.read_register(5017, 1)
print("Total PV Power "+str(TotalActivePower))

Frequency = instrument.read_register(5036, 1)
print("Freq "+str(Frequency))

MeterLoadPower = instrument.read_register(5091, 1)
print("House Overall Consumption "+str(MeterLoadPower))

ReverseActiveEnergy = instrument.read_register(5083, 1)
print("House Grid Consumption "+str(ReverseActiveEnergy))

export_power_indicator = instrument.read_register(5084, 1)
print("Direction "+str(export_power_indicator))

TotalYield = instrument.read_register(5004, 1)
print("Total Yield"+str(TotalYield))

DailyYield = instrument.read_register(5003, 1)
print("Daily Yield"+str(DailyYield))


count = 0
while count < 1000:
    address = 4999+count
    try:
        temperature = instrument.read_register(address)
        print(address, end=' ')
        print(":", end=' ')
        print(temperature)
    except Exception as e:
        print(address, end=' ')
        print(":", end=' ')
        print("Error")
    count = count + 1