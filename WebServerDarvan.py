import network
import socket
from machine import Pin, ADC, SoftI2C
from time import sleep, ticks_ms, ticks_diff
from tsl2591 import Tsl2591

# Wi-Fi Connection Function
def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    while not wlan.isconnected():
        pass
    print('Connected to Wi-Fi')
    print('IP Address:', wlan.ifconfig()[0])
    return wlan.ifconfig()[0]

# Replace with your Wi-Fi credentials
ssid = "HANZE-ZP11"
password = "sqr274YzW6"

# Sensor Initialization
i2c = SoftI2C(scl=Pin(22), sda=Pin(21))  # Initialize SoftI2C
tsl = Tsl2591(i2c)  # Pass SoftI2C instance to TSL2591 library

# Flow Meter Variables
flow_frequency = 0  # Measures flow meter pulses
l_hour = 0          # Calculated liters/hour
flowmeter_pin = 2   # Flow meter pin number
cloopTime = 0       # For time tracking

# pH Sensor Configuration
pH_pin = 36
adcPH = ADC(Pin(pH_pin))
adcPH.atten(ADC.ATTN_11DB)  # Set ADC range to 3.3V

pH_SLOPE = -0.0051  # Adjust based on calibration
pH_INTERCEPT = 15.449

# Interrupt Handler for Flow Meter
def flow(pin):
    global flow_frequency
    flow_frequency += 1

# Configure Flow Meter Pin and Interrupt
flowmeter = Pin(flowmeter_pin, Pin.IN, Pin.PULL_DOWN)
flowmeter.irq(trigger=Pin.IRQ_RISING, handler=flow)  # Attach interrupt

# Read pH Sensor
def read_pH():
    adc_value = adcPH.read()
    return adc_value * pH_SLOPE + pH_INTERCEPT

# Read Light Sensor
def read_luminosity():
    full, ir = tsl.get_full_luminosity()
    lux = tsl.calculate_lux(full, ir)
    return lux

# Calculate Flow Rate
def calculate_flow_rate():
    global flow_frequency
    global cloopTime
    currentTime = ticks_ms()
    if ticks_diff(currentTime, cloopTime) >= 1000:  # Every 1 second
        cloopTime = currentTime  # Update cloopTime
        l_hour = (flow_frequency * 60) / 7.5  # Calculate liters/hour
        flow_frequency = 0  # Reset counter
        return l_hour
    return l_hour  # Return the last calculated value

# HTML Web Page
def web_page(pH, flow_rate, luminosity):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sensor Data</title>
        <meta http-equiv="refresh" content="10">
    </head>
    <body>
        <h1>Sensor Readings</h1>
        <p><strong>pH:</strong> {pH:.2f}</p>
        <p><strong>Flow Rate:</strong> {flow_rate:.2f} L/hour</p>
        <p><strong>Luminosity:</strong> {luminosity:.2f} lux</p>
    </body>
    </html>
    """
    return html

# Web Server Function
def serve_web_page(ip):
    addr = socket.getaddrinfo(ip, 80)[0][-1]
    s = socket.socket()
    s.bind(addr)
    s.listen(1)
    print('Listening on', addr)

    while True:
        cl, addr = s.accept()
        print('Client connected from', addr)
        request = cl.recv(1024)
        request = str(request)
        if 'GET / ' in request:
            pH = read_pH()
            flow_rate = calculate_flow_rate()
            luminosity = read_luminosity()
            response = web_page(pH, flow_rate, luminosity)
            cl.send('HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n')
            cl.send(response)
        cl.close()

# Main Program
def main():
    ip = connect_wifi(ssid, password)
    print(f"ESP32 is running on IP: {ip}")
    serve_web_page(ip)

# Run Main Program
if __name__ == "_main_":
    main()

