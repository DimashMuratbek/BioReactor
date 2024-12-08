import machine
import time
import network
import ujson
from machine import Pin, ADC, PWM
from umqtt.simple import MQTTClient
from microdot import Microdot

# Constants
LED_PIN = 2
RELAY_PUMP_PIN = 15
PH_PIN = 36
FLOW_PIN = 39
BUTTON_PIN = 34
CALIBRATION_FACTOR = 4.5
PUMP_INTERVAL = 15 * 60  # 15 minutes in seconds
PUMP_DURATION = 20       # 20 seconds
DATA_FILE = "data.json"

# WiFi credentials
SSID = "HANZE-ZP11"
PASSWORD = "sqr274YzW6"

# Global Variables
pulse_count = 0
flow_rate = 0.0
total_milliliters = 0
last_pump_time = time.time()

# Initialize peripherals
led = Pin(LED_PIN, Pin.OUT)
relay = Pin(RELAY_PUMP_PIN, Pin.OUT)
button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
ph_sensor = ADC(Pin(PH_PIN))
flow_sensor = Pin(FLOW_PIN, Pin.IN)

# Microdot Web Server
app = Microdot()

# Flow sensor interrupt
def flow_interrupt(pin):
    global pulse_count
    pulse_count += 1

flow_sensor.irq(trigger=Pin.IRQ_FALLING, handler=flow_interrupt)

# WiFi connection
def connect_to_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    print("Connecting to WiFi...")
    while not wlan.isconnected():
        time.sleep(1)
        print(".", end="")
    print("\nConnected to WiFi!")
    print("IP Address:", wlan.ifconfig()[0])

# Read sensor values
def read_ph():
    raw = ph_sensor.read()
    return -0.0051 * raw + 15.449

def read_flow():
    global pulse_count, flow_rate, total_milliliters
    pulse_1s = pulse_count
    pulse_count = 0
    flow_rate = (pulse_1s / CALIBRATION_FACTOR) * 60
    milliliters = (flow_rate / 60) * 1000
    total_milliliters += milliliters
    return flow_rate, total_milliliters

# Save data to filesystem
def save_data(data):
    try:
        with open(DATA_FILE, "a") as f:
            f.write(ujson.dumps(data) + "\n")
    except Exception as e:
        print("Failed to save data:", e)

# Web server routes
@app.route("/")
def index(request):
    return "ESP32 Sensor Data - <a href='/data'>View Stored Data</a>"

@app.route("/data")
def view_data(request):
    try:
        with open(DATA_FILE, "r") as f:
            content = f.read()
        return content.replace("\n", "<br>")
    except Exception:
        return "No data available."

# Main loop
def main():
    global last_pump_time

    connect_to_wifi()
    app.run(debug=True, host="0.0.0.0", port=80)

    while True:
        elapsed_time = time.time() - last_pump_time
        flow_rate, total_milliliters = read_flow()
        ph_value = read_ph()

        # Log data
        data = {
            "time": time.time(),
            "ph": ph_value,
            "flow_rate": flow_rate,
            "total_milliliters": total_milliliters
        }
        save_data(data)

        # Control pump and LED
        if elapsed_time >= PUMP_INTERVAL:
            print("Turning ON pump and LED...")
            relay.value(1)
            led.value(1)
            time.sleep(PUMP_DURATION)
            relay.value(0)
            led.value(0)
            last_pump_time = time.time()
            print("Turning OFF pump and LED...")

        # Print values to console
        print("pH: {:.2f}, Flow Rate: {:.2f} L/min, Total Volume: {:.2f} mL".format(ph_value, flow_rate, total_milliliters))

        time.sleep(1)

# Run the program
try:
    main()
except KeyboardInterrupt:
    print("Program stopped.")
