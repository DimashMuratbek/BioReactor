from machine import Pin, ADC, RTC, SoftI2C, I2C
from time import sleep, ticks_ms, ticks_diff
import random
import math
import time
from tsl2591 import Tsl2591
import BME280
import socket
import ujson
import _thread
import network

# Wi-Fi Configuration
SSID = "HANZE-ZP11"  # Replace with your Wi-Fi SSID
PASSWORD = "sqr274YzW6"  # Replace with your Wi-Fi password

# Initialize Fluoro Sensor
i2c = SoftI2C(scl=Pin(22), sda=Pin(21))  # Adjust pins as per your setup
tsl = Tsl2591()  # Initialize the TSL2591 sensor

# Initialzie BME Sensor
i2c = SoftI2C(scl=Pin(18), sda=Pin(19), freq=10000)

# Flow sensor setup
flow_frequency = 0  # Measures flow meter pulses
l_hour = 0          # Calculated liters/hour
flowmeter_pin = 39  # Flow Meter Pin number
cloopTime = 0

# Initialize RTC
rtc = RTC()
rtc.init((2024, 9, 23, 12, 51, 0, 0, 0))  # Set RTC time directly
start_time_ms = ticks_ms()

# Pins and Constants
led = Pin(5, Pin.OUT)
relayPump = Pin(2, Pin.OUT)
POMP_TIME_FOR_HOMOGENEUS_SOLUTION = 15
MEASURING_FREQUENCY_SEC = 10
ON = 1
OFF = 0

#Light sensor calibration
FULL_SPECTRUM_BLANK = 23259
IR_SPECTRUM_BLANK = 527

# ADC Setup
pH_pin = 36
adcPH = ADC(Pin(pH_pin))
adcPH.atten(ADC.ATTN_11DB)

# Calibration constants
pH_SLOPE = -0.0051
pH_INTERCEPT = 15.449

# Globals for sensor data
latest_sensor_data = {
    "Temperature": "N/A",
    "pH": "N/A",
    "Flow Rate": "N/A",
    "Luminosity": "N/A"
}

# Flow Interrupt handler
def flow(pin):
    global flow_frequency
    flow_frequency += 1

# Setup Flow Sensor
def setup_flow():
    global cloopTime
    flowmeter = Pin(flowmeter_pin, Pin.IN, Pin.PULL_DOWN)
    flowmeter.irq(trigger=Pin.IRQ_RISING, handler=flow)
    cloopTime = ticks_ms()

# Connect to Wi-Fi
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    print(f"Connecting to Wi-Fi: {SSID}")

    # Wait until connected
    while not wlan.isconnected():
        sleep(1)
        print("Connecting...")
    
    print("Connected to Wi-Fi!")
    print("IP Address:", wlan.ifconfig()[0])  # Print IP address

# Sensor Reading Functions
def read_sensor(adc, slope, intercept):
    adc_value = adc.read()
    result = adc_value * slope + intercept
    return result

def read_luminosity():
    full, ir = tsl.get_full_luminosity()
    lux = tsl.calculate_lux(full, ir)
    return lux

def get_elapsed_time():
    return ticks_diff(ticks_ms(), start_time_ms) // 1000

# Web Server Function
def start_web_server():
    global latest_sensor_data

    # Create and bind socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("0.0.0.0", 80))
    server_socket.listen(5)
    print("Web server started on port 80")

    while True:
        client_socket, client_addr = server_socket.accept()
        print("Client connected from:", client_addr)
        request = client_socket.recv(1024).decode("utf-8")

        if "/data" in request:
            # Serve JSON data for updates
            response = ujson.dumps(latest_sensor_data)
            client_socket.send("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + response)
        else:
            # Serve the main HTML page
            html = """
            <!DOCTYPE html>
            <html>
                <head>
                    <title>ESP32 Sensor Data</title>
                    <script>
                        function updateData() {
                            fetch('/data')
                                .then(response => response.json())
                                .then(data => {
                                    document.getElementById('Temperature').innerText = data.Temperature;
                                    document.getElementById('pH').innerText = data.pH;
                                    document.getElementById('FlowRate').innerText = data["Flow Rate"];
                                    document.getElementById('Luminosity').innerText = data.Luminosity;
                                });
                        }
                        setInterval(updateData, 2000);  // Refresh every 2 seconds
                    </script>
                </head>
                <body>
                    <h1>ESP32 Sensor Data</h1>
                    <p><b>Temperature:</b> <span id="Temperature">N/A</span></p>
                    <p><b>pH:</b> <span id="pH">N/A</span></p>
                    <p><b>Flow Rate:</b> <span id="FlowRate">N/A</span></p>
                    <p><b>Luminosity:</b> <span id="Luminosity">N/A</span></p>
                </body>
            </html>
            """
            client_socket.send("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + html)
        client_socket.close()

# Main Function
def main():
    connect_wifi()  # Connect to Wi-Fi
    setup_flow()  # Setup the flow sensor
    _thread.start_new_thread(start_web_server, ())  # Start web server in a new thread

    global latest_sensor_data

    while True:
        # Read sensors
        temp = bme.temperature
        pH = read_sensor(adcPH, pH_SLOPE, pH_INTERCEPT)
        lux_value = read_luminosity()

        # Calculate flow rate
        currentTime = time.ticks_ms()
        # Every second, calculate and print liters/hour
        if time.ticks_diff(currentTime, cloopTime) >= 10000:
            cloopTime = currentTime  # Update cloopTime
            # Pulse frequency (Hz) = 7.5Q, Q is flow rate in L/min. (Results in +/- 3% range)
            l_hour = int((flow_frequency * 60) / 7.5)  # Calculate liters/hour
            flow_frequency = 0  # Reset counter

        # Update global data
        latest_sensor_data.update({
            "Temperature": temp,
            "pH": round(pH, 2),
            "Flow Rate": l_hour,
            "Luminosity": lux_value
        })

        # Debug print
        print(f"pH: {pH:.2f}, Flow: {l_hour}")

        sleep(MEASURING_FREQUENCY_SEC)

# Run Program
main()


