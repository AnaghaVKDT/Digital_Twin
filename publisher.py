import time
import json
import random
import paho.mqtt.client as mqtt

# === CONFIGURATION FOR NETWORK USE ===
BROKER = "broker.hivemq.com"  # Listen on ALL network interfaces (or use your laptop IP)
PORT = 1883
TOPIC = "tank/rates"

# Alternative: Use public broker (easiest)
# BROKER = "broker.hivemq.com"
# PORT = 1883

client = mqtt.Client()
print(f"🚀 Publisher connecting to {BROKER}:{PORT}...")

# Connect to broker
client.connect(BROKER, PORT, 60)
print("✅ Connected to broker!")

client.loop_start()

try:
    while True:
        # Fake changing rates (same as before)
        rate_in = round(random.uniform(0.5, 2.0), 2)
        rate_out = round(random.uniform(0.2, 1.5), 2)

        payload = {
            "rate_in": rate_in,
            "rate_out": rate_out
        }

        client.publish(TOPIC, json.dumps(payload), qos=1)
        print(f"📤 Published to '{TOPIC}': {payload}")

        time.sleep(5)  # Publish every 5 seconds

except KeyboardInterrupt:
    print("\n🛑 Stopping publisher...")
finally:
    client.loop_stop()
    client.disconnect()
    print("👋 Publisher disconnected.")
