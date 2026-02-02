import bpy
import math
import sys

sys.path.append(r'C:\Users\milan.s\AppData\Roaming\Python\Python311\site-packages')  # Ensures paho-mqtt is found
import paho.mqtt.client as mqtt
import json
import ssl
import time

# MQTT settings (same as your publisher)
BROKER = "chameleon.lmq.cloudamqp.com"
PORT = 8883
USERNAME = "gxmarmlp:gxmarmlp"
PASSWORD = "YfyyWeKMkTlMTLrqpcPfuGRyAMcYdqty"
TOPIC = "tank/rates"

# Global variables for rates (will be set by MQTT)
rate_in = 1.0  # Default fallback
rate_out = 1.0  # Default fallback


# MQTT callback to handle incoming message
def on_message(client, userdata, msg):
    global rate_in, rate_out
    try:
        data = json.loads(msg.payload.decode())
        rate_in = data.get('rate_in', 1.0)  # Fallback if key missing
        rate_out = data.get('rate_out', 1.0)
        print(f"Received rates from MQTT: rate_in={rate_in}, rate_out={rate_out}")
        client.disconnect()  # Stop after receiving one message
    except Exception as e:
        print(f"Error parsing MQTT message: {e}")
        client.disconnect()


# Function to subscribe and get rates from MQTT
def get_rates_from_mqtt():
    global rate_in, rate_out
    client = mqtt.Client()
    client.username_pw_set(USERNAME, PASSWORD)
    client.tls_set(cert_reqs=ssl.CERT_NONE)  # Disable cert verification (use CA certs in production)
    client.on_message = on_message

    try:
        client.connect(BROKER, PORT, 60)
        client.subscribe(TOPIC)
        print("Waiting for MQTT message on topic 'tank/rates'... (timeout in 10s)")

        # Start loop and wait for message or timeout
        start_time = time.time()
        while client.is_connected() and (time.time() - start_time) < 10:  # 10s timeout
            client.loop(timeout=0.1)  # Non-blocking loop

        if client.is_connected():
            print("MQTT timeout: Using default rates.")
            client.disconnect()
    except Exception as e:
        print(f"MQTT connection error: {e}. Using default rates.")


# Call MQTT function to get rates (this blocks until received or timeout)
get_rates_from_mqtt()

# Now proceed with the rest of the script using the fetched rates

# Clear the scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Parameters (adjust as needed)
tank_height = 5.0
tank_outer_radius = 2.0
tank_inner_radius = 1.8  # For hollow effect
inlet_radius = 0.2
outlet_radius = 0.2
water_radius = tank_inner_radius - 0.1  # Slightly smaller for water

# Volume = pi * r^2 * h = pi * (1.8)^2 * 5 ≈ 50.9 units^3
volume = math.pi * (tank_inner_radius ** 2) * tank_height
t_fill = volume / rate_in  # Time to fill
t_drain = volume / rate_out  # Time to drain
total_time = t_fill + t_drain

# Set frame rate and end frame
bpy.context.scene.render.fps = 24
bpy.context.scene.frame_end = int(total_time * 24) + 10  # Extra frames

# Create tank (hollow cylinder)
bpy.ops.mesh.primitive_cylinder_add(radius=tank_outer_radius, depth=tank_height, location=(0, 0, tank_height / 2))
tank_outer = bpy.context.active_object
tank_outer.name = "Tank_Outer"

bpy.ops.mesh.primitive_cylinder_add(radius=tank_inner_radius, depth=tank_height, location=(0, 0, tank_height / 2))
tank_inner = bpy.context.active_object
tank_inner.name = "Tank_Inner"

# Make hollow using boolean modifier
modifier = tank_outer.modifiers.new(name="Boolean", type='BOOLEAN')
modifier.object = tank_inner
modifier.operation = 'DIFFERENCE'
bpy.ops.object.modifier_apply(modifier="Boolean")

# Delete inner cylinder
bpy.data.objects.remove(tank_inner)

# Add material to tank (transparent for glass-like effect)
tank_mat = bpy.data.materials.new(name="Tank_Material")
tank_mat.diffuse_color = (0.8, 0.8, 0.8, 0.3)  # Semi-transparent gray
tank_mat.use_nodes = True  # Enable node-based materials for transparency
principled_bsdf = tank_mat.node_tree.nodes.get('Principled BSDF')
if principled_bsdf:
    principled_bsdf.inputs['Alpha'].default_value = 0.3  # Low alpha for transparency
    tank_mat.blend_method = 'BLEND'  # Enable alpha blending
tank_outer.data.materials.append(tank_mat)

# Create inlet pipe (small cylinder on top)
bpy.ops.mesh.primitive_cylinder_add(radius=inlet_radius, depth=1.0,
                                    location=(0, tank_outer_radius + inlet_radius, tank_height + 0.5))
inlet = bpy.context.active_object
inlet.name = "Inlet_Pipe"
inlet.data.materials.append(tank_mat)

# Create outlet pipe (small cylinder at bottom)
bpy.ops.mesh.primitive_cylinder_add(radius=outlet_radius, depth=1.0,
                                    location=(0, -tank_outer_radius - outlet_radius, 0.5))
outlet = bpy.context.active_object
outlet.name = "Outlet_Pipe"
outlet.data.materials.append(tank_mat)

# Create water (cylinder inside tank, starting at bottom)
bpy.ops.mesh.primitive_cylinder_add(radius=water_radius, depth=0.01, location=(0, 0, 0.005))  # Small depth at bottom
water = bpy.context.active_object
water.name = "Water"

# Set origin to bottom for proper scaling upwards
bpy.context.scene.cursor.location = (0, 0, 0)  # Set cursor to tank bottom
bpy.ops.object.origin_set(type='ORIGIN_CURSOR')  # Move origin to cursor (bottom)

# Add water material (blue)
water_mat = bpy.data.materials.new(name="Water_Material")
water_mat.diffuse_color = (0.0, 0.5, 1.0, 0.8)  # Semi-transparent blue
water.data.materials.append(water_mat)

# Animate water level (scale Z to rise from bottom)
# Filling phase: scale Z from 0 to full height over t_fill seconds
fill_frames = int(t_fill * 24)
water.scale[2] = 0.0  # Start flat at bottom
water.keyframe_insert(data_path="scale", frame=1, index=2)

water.scale[2] = tank_height / 0.01  # Scale factor to reach tank_height
water.keyframe_insert(data_path="scale", frame=fill_frames, index=2)

# Draining phase: after full, scale back to 0 over t_drain seconds
drain_start_frame = fill_frames
drain_end_frame = fill_frames + int(t_drain * 24)
water.keyframe_insert(data_path="scale", frame=drain_start_frame, index=2)  # Still full
water.scale[2] = 0.0
water.keyframe_insert(data_path="scale", frame=drain_end_frame, index=2)

# Create a text object to display rates
bpy.ops.object.text_add(location=(5, 0, tank_height + 1))  # Position near the tank
text_obj = bpy.context.active_object
text_obj.name = "Rates_Display"
text_obj.data.body = f"Rate In: {rate_in}, Rate Out: {rate_out}"  # Display the rates
text_obj.data.size = 0.5  # Adjust text size
text_obj.data.align_x = 'LEFT'  # Left-align text

# Optional: Add a camera and light for rendering
bpy.ops.object.camera_add(location=(10, -10, 10), rotation=(math.radians(60), 0, math.radians(45)))
bpy.context.scene.camera = bpy.context.active_object

bpy.ops.object.light_add(type='SUN', location=(5, 5, 10))

print(f"Blender script executed. Tank model created with water animation using rate_in={rate_in}, rate_out={rate_out}.")