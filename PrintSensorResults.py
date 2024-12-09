# Program to read the algae concentration inline.
# Version: v1 
# Written by: J. Hekman

#what is missing BME280 should be integrated.

from machine import Pin, ADC, RTC, SoftI2C, Timer
from time import sleep, ticks_ms, ticks_diff
import random
import math
import time
from tsl2591 import Tsl2591
import BME280

# Initialzie Fluro Sensor
i2c = SoftI2C(scl=Pin(22), sda=Pin(21))  # Adjust pins as per your setup
tsl = Tsl2591()  # Initialize the TSL2591 sensor

# Initialzie BME Sensor
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

# settings for flashing
DEBUG = False  # print information to the serial port
STORE_VALUES = True  # store values on ESP32
SIMULATIONS = False
PRINT_ALL_DATA_VARIABLES = True

# Light sensor settings
FULL_SPECTRUM_BLANK = 23259 # 3d printed cuvet 6335.80 # real cuvet with in and output 18600
IR_SPECTRUM_BLANK = 527 # 3d printed cuvet 144.2     # real cuvet with in and output  403

if not SIMULATIONS:
    tsl = Tsl2591('lux-1')  # Initialize the sensor

# pH and Conductivity sensor configuration
pH_pin = 36
# flow_pin = 39
adcPH = ADC(Pin(pH_pin))
# adcFlow = ADC(Pin(flow_pin))

for adc in [adcPH]:
    adc.atten(ADC.ATTN_11DB)  # Set ADC to 3.3V range

pH_SLOPE = -0.0051  # Adjust based on calibration
pH_INTERCEPT = 15.449



# Combined function for sensor reading (DRY principle)
def read_sensor(adc, slope, intercept, sensor_name):
    adc_value = adc.read()
    result = adc_value * slope + intercept
    if DEBUG:
        print(f"{sensor_name}_ADC: {adc_value}, {sensor_name}: {result}")
    return result

def read_sensor_F(adc, sensor_name):
    adc_value = adc.read()
    return adc_value

# Function to handle light sensor readings
def read_optical_density(samples):
    led.value(ON)
    sleep(1)
    average_ir, average_full = 0, 0
    for _ in range(samples):
        tempFull, tempIR = tsl.get_full_luminosity() if not SIMULATIONS else (random.random(), random.random())
        average_ir += tempIR
        average_full += tempFull
    
    average_ir /= samples
    average_full /= samples
    
    if DEBUG:
        print(f"average_ir: {average_ir}, average_full: {average_full}")
    led.value(OFF)
    return average_full, average_ir

# Combine the extinction calculation into a single function
def convert_to_extinction(spectrum, blank):
    transmission = spectrum / blank
    # convert to extinction and return extinction instead of transmission
    return transmission

# Density measurement using the pump
def measure_density():
    relayPump.value(ON)
    sleep(POMP_TIME_FOR_HOMOGENEUS_SOLUTION)
    
    full_spectr, ir_spectr = read_optical_density(5)
    E_full = convert_to_extinction(full_spectr, FULL_SPECTRUM_BLANK)
    E_ir = convert_to_extinction(ir_spectr, IR_SPECTRUM_BLANK)
    
    relayPump.value(OFF)
    return full_spectr, E_full, ir_spectr, E_ir

# Tracking elapsed time in seconds
def get_elapsed_time():
    return ticks_diff(ticks_ms(), start_time_ms) // 1000  # Convert to seconds

# Open the file once, append throughout the loop





# Get fluro value
def read_luminosity():
    full, ir = tsl.get_full_luminosity()
    lux = tsl.calculate_lux(full, ir)
    return lux  # Return only the lux value




# FLOW Interrupt handler function
def flow(pin):
    global flow_frequency
    flow_frequency += 1

# FLOW Setup function equivalent
def setup():
    global cloopTime
    # Configure the flowmeter pin as input with a pull-down resistor
    flowmeter = Pin(flowmeter_pin, Pin.IN, Pin.PULL_DOWN)
    flowmeter.irq(trigger=Pin.IRQ_RISING, handler=flow)  # Attach interrupt

    cloopTime = time.ticks_ms()  # Initialize cloopTime




while True:
#   Fluro value print  
    lux_value = read_luminosity()  # Get only the lux value
#     print(f"{lux_value:.6f}")
    
    bme = BME280.BME280(i2c=i2c)
    temp = bme.temperature
    
    currentTime = time.ticks_ms()
    # Every second, calculate and print liters/hour
    if time.ticks_diff(currentTime, cloopTime) >= 10000:
        cloopTime = currentTime  # Update cloopTime
        # Pulse frequency (Hz) = 7.5Q, Q is flow rate in L/min. (Results in +/- 3% range)
        l_hour = int((flow_frequency * 60) / 7.5)  # Calculate liters/hour
        flow_frequency = 0  # Reset counter

        # Print liters/hour to the console
#         print(f"{l_hour} L/hour")
        
    
    
    elapsed_time = get_elapsed_time()  # Track the time in seconds
      # Read pH, Conductivity, and optical density
    pH = read_sensor(adcPH, pH_SLOPE, pH_INTERCEPT, "pH")
#     cond = read_sensor_F(adcFlow, "Conductivity") # not present but example of additional ADC sensor
#     raw_full, extinction_full, raw_ir, extinction_ir = measure_density()
            
    if STORE_VALUES == True:
        f = open('datafile.csv', 'a')
        
        if (elapsed_time < 20):
            store_headers = f"elapsed_time, temp, pH, flow, luminosity\n"
            f.write(store_headers)
        # Format and store values in CSV
        data_string = f"{elapsed_time}, {temp}, {pH}, {l_hour}, {lux_value}\n"
        f.write(data_string)
                
        f.close()
            
    # Print variables with headers aligned
    if PRINT_ALL_DATA_VARIABLES:
        headers = (
                "Time (s)\t temp\t pH \t FLow \t Luminosity"
        )
        values = (
                f"Time: {elapsed_time}\t Temperature: {temp}\t PH: {pH:.2f}\t Flow {l_hour:.2f}\t Luminosity: {lux_value:.2f}"
        )
#         print(headers)
        print(values)
            
    sleep(MEASURING_FREQUENCY_SEC)        


