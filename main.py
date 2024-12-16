from machine import Pin, ADC, RTC, SoftI2C, Timer
from time import sleep, ticks_ms, ticks_diff
import math
import time
import BME280
import json
from tsl2591 import Tsl2591

buffer = []  # Initialize an empty buffer
BUFFER_SIZE = 10  # Number of data entries to buffer before writing to flash

# Fluro initialization
i2c = SoftI2C(scl=Pin(18), sda=Pin(19))  # Adjust pins as per your setup
tsl = Tsl2591()  # Initialize the TSL2591 sensor

# Initialize BME Sensor
i2c = SoftI2C(scl=Pin(18), sda=Pin(19), freq=10000)

# Flow sensor
flow_frequency = 0  # Measures flow meter pulses
l_hour = 0          # Calculated liters/hour
flowmeter_pin = 39   # Flow Meter Pin number
cloopTime = 0

rtc = RTC()
rtc.init((2024, 9, 23, 12, 51, 0, 0, 0))  # Set RTC time directly
start_time_ms = ticks_ms()  # Track elapsed time in milliseconds

led = Pin(25, Pin.OUT)
relayPump = Pin(26, Pin.OUT)
button = Pin(34, Pin.IN, Pin.PULL_UP)  # Button to toggle relay activation
PUMP_PRE_ON_TIME_SECONDS = 5  # Time before data sending when relays are turned on
DATA_SEND_INTERVAL_SECONDS = 15 * 60  # Interval between data sends
MEASURING_FREQUENCY_SEC = 10
ON = 0
OFF = 1

DEBUG = False  # print information to the serial port
STORE_VALUES = True  # store values on ESP32
SIMULATIONS = False
PRINT_ALL_DATA_VARIABLES = True

FULL_SPECTRUM_BLANK = 23259  # 3d printed cuvet 6335.80 # real cuvet with in and output 18600
IR_SPECTRUM_BLANK = 527  # 3d printed cuvet 144.2   

pH_SLOPE = -0.0051  # Adjust based on calibration
pH_INTERCEPT = 15.449

pH_pin = 36
adcPH = ADC(Pin(pH_pin))
for adc in [adcPH]:
    adc.atten(ADC.ATTN_11DB)

manual_mode = False  # To track if button is pressed

def save_to_csv(filename, data_buffer):
    """Writes buffered data to a CSV file on internal storage."""
    try:
        with open(filename, "a") as file:  # Open file in append mode
            if file.tell() == 0:  # Write headers if the file is empty
                file.write("Elapsed_Time,Temperature,pH,Flow,Luminosity\n")
            for entry in data_buffer:
                file.write(entry + "\n")
            file.flush()  # Ensure data is flushed to storage
        print("Data saved to", filename)
    except Exception as e:
        print("Error writing to file:", e)


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

last_message_time = ticks_ms()
pump_state = OFF
led_state = OFF

# Initialize data buffer and buffer size
buffer = []  # List to temporarily hold sensor data
BUFFER_SIZE = 10  # Number of records before saving to local storage

while True:
    # Read sensor data
    lux_value = read_luminosity()
    bme = BME280.BME280(i2c=i2c)
    temperature = bme.temperature.replace('C', '')  # Removes "C"
    elapsed_time = get_elapsed_time()  # Time since start
    pH = read_sensor(adcPH, pH_SLOPE, pH_INTERCEPT, "pH")

    # Calculate flow rate every 10 seconds
    current_time = time.ticks_ms()
    if time.ticks_diff(current_time, cloopTime) >= 10000:
        cloopTime = current_time  # Update cloopTime
        l_hour = int((flow_frequency * 60) / 7.5)  # Calculate liters/hour
        flow_frequency = 0  # Reset counter

    # Format data for CSV
    data_row = f"{elapsed_time},{temperature},{pH},{l_hour},{lux_value}"
    print("Buffered Data:", data_row)
    buffer.append(data_row)

    # Save data to local storage if buffer is full
    if len(buffer) >= BUFFER_SIZE:
        save_to_csv("sensor_data.csv", buffer)  # Write to local storage
        buffer = []  # Clear the buffer

    # Manual mode (button pressed)
    if button.value() == 1:  # Button is pressed
        if not manual_mode:
            manual_mode = True
            print("Manual mode activated")
        relayPump.value(ON)
        led.value(ON)

        # Print sensor data in manual mode
        print(f"Temperature: {temperature}, pH: {pH}, Flow: {l_hour}, Luminosity: {lux_value}")
        sleep(0.5)  # Small delay to avoid spamming output

    else:  # Button is released
        if manual_mode:
            manual_mode = False
            print("Manual mode deactivated, resuming scheduled operations")

        relayPump.value(OFF)
        led.value(OFF)

        # Scheduled operations
        time_since_last_message = ticks_diff(ticks_ms(), last_message_time) / 1000
        if pump_state == OFF and time_since_last_message >= DATA_SEND_INTERVAL_SECONDS - PUMP_PRE_ON_TIME_SECONDS:
            pump_state = ON
            relayPump.value(ON)
            led.value(ON)
            if DEBUG:
                print("Pump and LED ON before data send")

        elif pump_state == ON and time_since_last_message >= DATA_SEND_INTERVAL_SECONDS:
            pump_state = OFF
            relayPump.value(OFF)
            led.value(OFF)
            last_message_time = ticks_ms()

            # Publish data to MQTT
            try:
                sensor_data = {
                    "temperature": temperature,
                    "pH": pH,
                    "flow": l_hour,
                    "luminosity": lux_value
                }
                client.publish(sensor_topic, json.dumps(sensor_data))
                print("Sent Data:", temperature, pH, l_hour, lux_value)
            except OSError as e:
                restart_and_reconnect()

    # Check for incoming MQTT messages
    try:
        client.check_msg()
    except OSError as e:
        restart_and_reconnect()
