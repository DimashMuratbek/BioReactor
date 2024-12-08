import network
import socket
from machine import Pin, ADC, RTC
from time import sleep, ticks_ms, ticks_diff
import ujson

# Wi-Fi credentials
# Replace with your network password

# Connect to the Wi-Fi network
station = network.WLAN(network.STA_IF)
station.active(True)
station.connect(ssid, password)

print("Connecting to Wi-Fi...")
while not station.isconnected():
    pass

print("Connected to Wi-Fi")
print("Network Config:", station.ifconfig())  # Print the IP address, subnet, gateway, and DNS

# Initialize variables
rtc = RTC()
rtc.init((2024, 9, 23, 12, 51, 0, 0, 0))
start_time_ms = ticks_ms()

led = Pin(5, Pin.OUT)
relayPump = Pin(2, Pin.OUT)
POMP_TIME_FOR_HOMOGENEUS_SOLUTION = 15
MEASURING_FREQUENCY_SEC = 5  # Reduce for frequent updates
ON = 1
OFF = 0

FULL_SPECTRUM_BLANK = 23259
IR_SPECTRUM_BLANK = 527

pH_pin = 36
adcPH = ADC(Pin(pH_pin))
adcPH.atten(ADC.ATTN_11DB)  # Set ADC range to 3.3V

pH_SLOPE = -0.0051
pH_INTERCEPT = 15.449

# Global variable for the latest sensor data
latest_sensor_data = {
    "pH": "N/A",
    "Raw Full Spectrum": "N/A",
    "Extinction Full": "N/A",
    "Raw IR Spectrum": "N/A",
    "Extinction IR": "N/A"
}

# Sensor reading functions
def read_sensor(adc, slope, intercept):
    adc_value = adc.read()
    result = adc_value * slope + intercept
    return round(result, 2)

def read_optical_density():
    led.value(ON)
    sleep(1)
    # Simulate data as a placeholder for the light sensor
    average_full = 1000  # Replace with actual light sensor reading logic
    average_ir = 500  # Replace with actual light sensor reading logic
    led.value(OFF)
    return average_full, average_ir

def convert_to_extinction(spectrum, blank):
    transmission = spectrum / blank
    return transmission

def measure_density():
    relayPump.value(ON)
    sleep(POMP_TIME_FOR_HOMOGENEUS_SOLUTION)
    full_spectrum, ir_spectrum = read_optical_density()
    relayPump.value(OFF)
    extinction_full = convert_to_extinction(full_spectrum, FULL_SPECTRUM_BLANK)
    extinction_ir = convert_to_extinction(ir_spectrum, IR_SPECTRUM_BLANK)
    return full_spectrum, extinction_full, ir_spectrum, extinction_ir

# Web server handler
def start_web_server():
    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    server_socket = socket.socket()
    server_socket.bind(addr)
    server_socket.listen(5)
    print("Web server started. Connect to:", station.ifconfig()[0])

    while True:
        client_socket, client_addr = server_socket.accept()
        print("Client connected from:", client_addr)
        request = client_socket.recv(1024).decode("utf-8")

        if "/data" in request:
            # Serve JSON data for dynamic updates
            response = ujson.dumps(latest_sensor_data)
            client_socket.send("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + response)
        else:
            # Serve the main HTML page
            html = """
            <!DOCTYPE html>
            <html>
                <head>
                    <title>Sensor Data</title>
                    <script>
                        function updateData() {
                            fetch('/data')
                                .then(response => response.json())
                                .then(data => {
                                    document.getElementById('pH').innerText = data.pH;
                                    document.getElementById('RawFull').innerText = data['Raw Full Spectrum'];
                                    document.getElementById('ExtinctionFull').innerText = data['Extinction Full'];
                                    document.getElementById('RawIR').innerText = data['Raw IR Spectrum'];
                                    document.getElementById('ExtinctionIR').innerText = data['Extinction IR'];
                                });
                        }
                        setInterval(updateData, 2000);  // Update every 2 seconds
                    </script>
                </head>
                <body>
                    <h1>Sensor Data</h1>
                    <p><b>pH:</b> <span id="pH">N/A</span></p>
                    <p><b>Raw Full Spectrum:</b> <span id="RawFull">N/A</span></p>
                    <p><b>Extinction Full:</b> <span id="ExtinctionFull">N/A</span></p>
                    <p><b>Raw IR Spectrum:</b> <span id="RawIR">N/A</span></p>
                    <p><b>Extinction IR:</b> <span id="ExtinctionIR">N/A</span></p>
                </body>
            </html>
            """
            client_socket.send("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + html)
        client_socket.close()

# Start the web server in a separate thread
import _thread
_thread.start_new_thread(start_web_server, ())

# Main loop for sensor measurements
while True:
    elapsed_time = ticks_diff(ticks_ms(), start_time_ms) // 1000
    pH = read_sensor(adcPH, pH_SLOPE, pH_INTERCEPT)
    raw_full, extinction_full, raw_ir, extinction_ir = measure_density()

    # Update latest sensor data
    latest_sensor_data.update({
        "pH": pH,
        "Raw Full Spectrum": round(raw_full, 2),
        "Extinction Full": round(extinction_full, 2),
        "Raw IR Spectrum": round(raw_ir, 2),
        "Extinction IR": round(extinction_ir, 2),
    })

    # Log data to console for debugging
    print("Sensor Data:", latest_sensor_data)

    # Wait for the next measurement
    sleep(MEASURING_FREQUENCY_SEC)

