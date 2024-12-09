
# Complete project details at https://RandomNerdTutorials.com/micropython-programming-with-esp32-and-esp8266/


from machine import Pin, SoftI2C
import BME280

import time
from umqttsimple import MQTTClient
import ubinascii
import machine
import micropython
import network
import esp
esp.osdebug(None)
import gc
gc.collect()



ssid = 'HANZE-ZP11'
password = 'sqr274YzW6'
mqtt_server = '10.149.34.38'
mqtt_user = 'dimash'
mqtt_pass = 'dimash'

# ssid = 'NETGEAR15'
# password = 'Vanhamelstraat5b'
# mqtt_server = '192.168.178.164'
# mqtt_user = 'dimash'
# mqtt_pass = 'dimash'


#EXAMPLE IP ADDRESS
#mqtt_server = '192.168.1.144'
client_id = ubinascii.hexlify(machine.unique_id())
topic_sub = b'notification'

# publis values on raspi
# topic_pub = b'hello'
# temp_topic = "sensor/temperature";
# hum_topic = "sensor/humidity";
# pres_topic = "sensor/pressure";


sensor_topic = b"sensor"


last_message = 0
message_interval = 5
counter = 0

station = network.WLAN(network.STA_IF)

station.active(True)
station.connect(ssid, password)

while station.isconnected() == False:
  pass

print('Connection successful')
print(station.ifconfig())
