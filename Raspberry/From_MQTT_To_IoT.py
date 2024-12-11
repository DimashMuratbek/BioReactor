import paho.mqtt.client as mqtt
import json
import sqlite3
import argparse
import time
from azure.iot.device import IoTHubDeviceClient, Message
from azure.iot.device.exceptions import (
    ConnectionFailedError, ConnectionDroppedError, OperationTimeout, 
    OperationCancelled, NoConnectionError
)
from dotenv import load_dotenv
from log import console, log
import config

load_dotenv()

# MQTT Configuration
MQTT_BROKER = "10.149.34.38"  # Replace with your Raspberry Pi IP
MQTT_PORT = 1883
MQTT_USERNAME = "dimash"
MQTT_PASSWORD = "dimash"
SENSOR_TOPIC = "sensor"

# SQLite Database
DB_PATH = '/home/dimash/BioReactor/BioSensorData.db'

# Azure IoT Hub Configuration
parser = argparse.ArgumentParser()
parser.add_argument("connection", nargs='?', help="Device Connection String from Azure", 
                    default=config.IOTHUB_DEVICE_CONNECTION_STRING)
parser.add_argument("-t", "--time", type=int, default=config.MESSAGE_TIMESPAN,
                    help="Time in between messages sent to IoT Hub, in milliseconds (default: 2000ms)")
parser.add_argument("-n", "--no-send", action="store_true", 
                    help="Disable sending data to IoTHub, only print to console")
ARGS = parser.parse_args()


def log_data(temp, pH, flow, lumin):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Bio_data (timestamp, temp, pH, flow, luminosity) "
        "VALUES (datetime('now'), ?, ?, ?, ?)",
        (temp, pH, flow, lumin)
    )
    conn.commit()
    conn.close()

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

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
        client.subscribe(SENSOR_TOPIC)
    else:
        print(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    print(f"Received message: {msg.payload.decode()} on topic: {msg.topic}")
    try:
        sensor_data = json.loads(msg.payload.decode())
        temp = round(float(sensor_data.get("temperature")), 1)
        pH = round(float(sensor_data.get("pH")))
        flow = round(float(sensor_data.get("flow")))
        lumin = round(float(sensor_data.get("luminosity")), 3)

        log_data(temp, pH, flow, lumin)

        message = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            "temp": temp,
            "pH": pH,
            "flow": flow,
            "luminosity": lumin
        }

        if ARGS.no_send:
            log.warning("Not sending to IoTHub", message)
        else:
            send_message(device_client, message)

    except json.JSONDecodeError:
        print("Error: Could not decode JSON message")

if __name__ == "__main__":
    client = mqtt.Client()
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    # Connect to MQTT broker
    try:
        print("Connecting to MQTT broker...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        print(f"Error connecting to MQTT broker: {e}")
        exit(1)

    # Azure IoT Hub Client Setup
    device_client = None
    if not ARGS.no_send:
        try:
            device_client = IoTHubDeviceClient.create_from_connection_string(ARGS.connection)
            device_client.connect()
            log.success("Connected to Azure IoT Hub")
        except Exception as e:
            print(f"Error connecting to Azure IoT Hub: {e}")
            exit(1)

    # Start MQTT loop
    try:
        print("Listening for messages...")
        client.loop_forever()
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        if device_client:
            device_client.shutdown()
