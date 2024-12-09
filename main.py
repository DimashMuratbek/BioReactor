# Complete project details at https://RandomNerdTutorials.com/micropython-programming-with-esp32-and-esp8266/
from machine import Pin, ADC, RTC, SoftI2C, Timer
from time import sleep, ticks_ms, ticks_diff
import math
import time
import BME280
import json
from tsl2591 import Tsl2591

#Fluro initialization
i2c = SoftI2C(scl=Pin(22), sda=Pin(21))  # Adjust pins as per your setup
tsl = Tsl2591()  # Initialize the TSL2591 sensor

# Initialzie BE Sensor
i2c = SoftI2C(scl=Pin(18), sda=Pin(19), freq=10000)

#Flow sensor
flow_frequency = 0  # Measures flow meter pulses
l_hour = 0          # Calculated liters/hour
flowmeter_pin = 39   # Flow Meter Pin number
cloopTime = 0


rtc = RTC()
rtc.init((2024, 09, 23, 12, 51, 0, 0, 0))  # Set RTC time directly
start_time_ms = ticks_ms()  # Track elapsed time in milliseconds

led = Pin(5, Pin.OUT)
relayPump = Pin(2, Pin.OUT)
POMP_TIME_FOR_HOMOGENEUS_SOLUTION = 15
MEASURING_FREQUENCY_SEC = 10
ON = 1
OFF = 0

DEBUG = False  # print information to the serial port
STORE_VALUES = True  # store values on ESP32
SIMULATIONS = False
PRINT_ALL_DATA_VARIABLES = True

FULL_SPECTRUM_BLANK = 23259 # 3d printed cuvet 6335.80 # real cuvet with in and output 18600
IR_SPECTRUM_BLANK = 527 # 3d printed cuvet 144.2   

pH_SLOPE = -0.0051  # Adjust based on calibration
pH_INTERCEPT = 15.449

pH_pin = 36
adcPH = ADC(Pin(pH_pin))
for adc in [adcPH]:
    adc.atten(ADC.ATTN_11DB)


def read_luminosity():
    full, ir = tsl.get_full_luminosity()
    lux = tsl.calculate_lux(full, ir)
    return lux  # Return only the lux value


def read_sensor(adc, slope, intercept, sensor_name):
    adc_value = adc.read()
    result = adc_value * slope + intercept
    if DEBUG:
        print(f"{sensor_name}_ADC: {adc_value}, {sensor_name}: {result}")
    return result


def flow(pin):
    global flow_frequency
    flow_frequency += 1


def setup():
    global cloopTime
    # Configure the flowmeter pin as input with a pull-down resistor
    flowmeter = Pin(flowmeter_pin, Pin.IN, Pin.PULL_DOWN)
    flowmeter.irq(trigger=Pin.IRQ_RISING, handler=flow)  # Attach interrupt

    cloopTime = time.ticks_ms()  # Initialize cloopTime


def get_elapsed_time():
    return ticks_diff(ticks_ms(), start_time_ms) // 1000  # Convert to seconds




# MQTT
def sub_cb(topic, msg):
  print((topic, msg))
  if topic == b'notification' and msg == b'received':
    print('ESP received hello message')

def connect_and_subscribe():
  global client_id, mqtt_server, topic_sub
  client = MQTTClient(client_id, mqtt_server, user=mqtt_user, password=mqtt_pass)
  client.set_callback(sub_cb)
  client.connect()
  client.subscribe(topic_sub)
  print('Connected to %s MQTT broker, subscribed to %s topic' % (mqtt_server, topic_sub))
  return client

def restart_and_reconnect():
  print('Failed to connect to MQTT broker. Reconnecting...')
  time.sleep(10)
  machine.reset()

try:
  client = connect_and_subscribe()
except OSError as e:
  restart_and_reconnect()

# mosquitto_sub -d -t sensor -u dimash -P dimash





while True:
  lux_value = read_luminosity()
  #read data from bme280 and assign them to variables
  
  bme = BME280.BME280(i2c=i2c)
  temperature = bme.temperature
  
  temp =temperature.replace('C', '')  # Removes "C"
  
  currentTime = time.ticks_ms()
    # Every second, calculate and print liters/hour
  if time.ticks_diff(currentTime, cloopTime) >= 10000:
      cloopTime = currentTime  # Update cloopTime
      # Pulse frequency (Hz) = 7.5Q, Q is flow rate in L/min. (Results in +/- 3% range)
      l_hour = int((flow_frequency * 60) / 7.5)  # Calculate liters/hour
      flow_frequency = 0  # Reset counter
  
  elapsed_time = get_elapsed_time()  # Track the time in seconds
      # Read pH, Conductivity, and optical density
  pH = read_sensor(adcPH, pH_SLOPE, pH_INTERCEPT, "pH")
  
  try:
    client.check_msg()
    if (time.time() - last_message) > message_interval:
        
            
      # put values in message
      sensor_data = {
          "temperature": temp,
          "pH": pH,
          "flow": l_hour,
          "luminosity":lux_value 
          }
      # publish them to broker
      client.publish(sensor_topic, json.dumps(sensor_data))

      print(temp,' ',pH,' ', l_hour,' ',lux_value)
      last_message = time.time()
      counter += 1
  except OSError as e:
    restart_and_reconnect()



