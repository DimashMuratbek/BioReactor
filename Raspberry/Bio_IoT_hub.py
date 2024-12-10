import config
import argparse
import sqlite3
from azure.iot.device import IoTHubDeviceClient
from azure.iot.device import Message
from azure.iot.device.exceptions import ConnectionFailedError, ConnectionDroppedError, OperationTimeout, OperationCancelled, NoConnectionError
from log import console, log
from dotenv import load_dotenv
import time
import json
load_dotenv()

# SECTION 1: Argument Parsing
# Parse arguments before anything for faster feedback
parser = argparse.ArgumentParser()
parser.add_argument("connection", nargs='?', help="Device Connection String from Azure", 
                    default=config.IOTHUB_DEVICE_CONNECTION_STRING)
parser.add_argument("-t", "--time", type=int, default=config.MESSAGE_TIMESPAN,
                    help="Time in between messages sent to IoT Hub, in milliseconds (default: 2000ms)")
parser.add_argument("-n", "--no-send", action="store_true", 
                    help="Disable sending data to IoTHub, only print to console")
ARGS = parser.parse_args()

# SECTION 2: Function to Send Message to IoTHub
# Function to send a message to Azure IoTHub
def send_message(device_client: IoTHubDeviceClient, message):
    telemetry = Message(json.dumps(message))
    telemetry.content_encoding = "utf-8"
    telemetry.content_type = "application/json"
    
    try:
        device_client.send_message(telemetry)
    except (ConnectionFailedError, ConnectionDroppedError, OperationTimeout, OperationCancelled, NoConnectionError):
        log.warning("Message failed to send, skipping")
    else:
        log.success("Message successfully sent!", message)

# SECTION 3: Main Function
# Main function to handle connection to IoTHub and send data from SQLite
def main():
    if not ARGS.connection and not ARGS.no_send:  # If no argument
        log.error("IOTHUB_DEVICE_CONNECTION_STRING in config.py variable or argument not found, try supplying one as an argument or setting it in config.py")
    
    device_client = None
    if not ARGS.no_send:
        with console.status("Connecting to IoT Hub with Connection String", spinner="arc", spinner_style="blue"):
            # Create instance of the device client using the connection string
            device_client = IoTHubDeviceClient.create_from_connection_string(ARGS.connection, connection_retry=False)

            # Connect the device client.
            device_client.connect()
        log.success("Connected to IoT Hub")

    # Connect to SQLite database
    conn = sqlite3.connect('/home/dimash/Sensors_Database/bmeWebServer/sensorsData.db')
    cursor = conn.cursor()

    try:
        while True:
            # Retrieve the latest data from the SQLite table
            cursor.execute("SELECT * FROM BME_data ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()

            if row:
                # Create message object with sensor data
                message = {
#                     "deviceId": "ESP32 - Python",
                    "timestamp": row[0],
                    "temp": row[1],
                    "pH": row[2],
                    "flow": row[3],
                    "luminosity": row[4]
                }

                # Send SQLite sensor data to Azure IoTHub
                if ARGS.no_send:
                    log.warning("Not sending to IoTHub", message)
                else:
                    with console.status("Sending message to IoTHub...", spinner="bouncingBar"):
                        send_message(device_client, message)

            # Wait for interval
            time.sleep(ARGS.time / 1000)
    except KeyboardInterrupt:
        # Shut down the device client when Ctrl+C is pressed
        log.error("Shutting down", exit_after=False)
        if device_client:
            device_client.shutdown()
    finally:
        # Close the SQLite connection
        conn.close()

# SECTION 4: Entry Point
# Entry point for the script
if __name__ == "__main__":
    main()
