import paho.mqtt.client as mqtt
import json
import sqlite3
# MQTT broker details
# MQTT_BROKER = "192.168.178.164"
MQTT_BROKER = "10.149.34.38"# Replace with your Raspberry Pi IP
MQTT_PORT = 1883
MQTT_USERNAME = "dimash"  # Replace with your MQTT username
MQTT_PASSWORD = "dimash"  # Replace with your MQTT password
SENSOR_TOPIC = "sensor"
# Replace with your sensor topic name
dbname='/home/dimash/BioReactor/BioSensorData.db'

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

def logData (temp, hum, pres):	
	conn=sqlite3.connect(dbname)
	curs=conn.cursor()
	curs.execute("INSERT INTO Bio_data values(datetime('now'), (?), (?), (?), (?))", (temp, ph, flow, lumin))
	conn.commit()
	conn.close()
# display database data
def displayData():
	conn=sqlite3.connect(dbname)
	curs=conn.cursor()
	print ("\nEntire database contents:\n")
	for row in curs.execute("SELECT * FROM Bio_data"):
		print (row)
	conn.close()

# Callback when the client connects to the broker
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
        # Subscribe to the topic
        client.subscribe(SENSOR_TOPIC)
    else:
        print(f"Failed to connect, return code {rc}")

# Callback when a message is received
def on_message(client, userdata, msg):
    print(f"Raw received message: {msg.payload.decode()} on topic: {msg.topic}")
    message = msg.payload.decode()
    print(f"Received message: {message} on topic: {msg.topic}")
#     
#     try:
#         # Try parsing the message into float (if values are numerical)
#         value = float(message)
#         print(f"Parsed value: {value}")
#     except ValueError:
#         print("Received non-numeric value, cannot parse!")
    try:
        # Parse JSON message
        
        sensor_data = json.loads(message)
        temp = float(sensor_data.get("temperature"))
        pH = float(sensor_data.get("pH"))
        flow = float(sensor_data.get("flow"))
        lumin = float(sensor_data.get("luminosity"))
        
        temp = round(temp, 1)
        pH = round(pH)
        flow=round(flow)
        lumin=round(lumin,3)
        
#         print(f"Temperature: {temp} °C")
#         print(f"Humidity: {hum} %")
#         print(f"Pressure: {pres} hPa")
        
#         logData (temp, pH, flow,lumin)
#         displayData()
        print(temp,' ',pH,' ', flow, ' ', lumin)
    except json.JSONDecodeError:
        print("Error: Could not decode JSON message")



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
            
    # Create MQTT client
    client = mqtt.Client()

    # Set username and password for the MQTT broker
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    # Assign callback functions
    client.on_connect = on_connect
    client.on_message = on_message

    # Connect to the MQTT broker
    try:
        print("Connecting to MQTT broker...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        print(f"Error connecting to MQTT broker: {e}")
        exit(1)

    # Start the MQTT client loop to listen for messages
    print("Listening for messages...")
    client.loop_forever()
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

