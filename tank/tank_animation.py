import bpy
import math
import sys

print("Blender script started.")  # Confirm script is running

# Use the correct path from site.getusersitepackages()
sys.path.append(r'C:\Users\milan.s\AppData\Roaming\Python\Python311\site-packages')

try:
    import paho.mqtt.client as mqtt
    import json
    import time

    print("paho-mqtt imported successfully.")
except ImportError as e:
    print(f"Failed to import paho-mqtt: {e}. Using default rates.")
    rate_in = 1.0
    rate_out = 1.0
    mqtt_connected = False
    pass

# MQTT settings
BROKER = "localhost"
PORT = 1883
USERNAME = ""
PASSWORD = ""
TOPIC = "tank/rates"

# Global variables for rates (EDIT THESE IF NOT USING MQTT)
rate_in = 1.0  # <-- Change this value here if needed (e.g., to 2.0)
rate_out = 1.0  # <-- Change this value here if needed (e.g., to 0.5)
mqtt_connected = False


# MQTT callback
def on_message(client, userdata, msg):
    global rate_in, rate_out, mqtt_connected
    try:
        print(f"Raw message received: {msg.payload.decode()}")
        data = json.loads(msg.payload.decode())
        print(f"Parsed data: {data}")
        rate_in = data.get('rate_in', 1.0)
        rate_out = data.get('rate_out', 1.0)
        mqtt_connected = True
        print(f"Rates updated: rate_in={rate_in}, rate_out={rate_out}")
        client.disconnect()
    except Exception as e:
        print(f"Error parsing MQTT message: {e}")
        client.disconnect()


# Function to get rates
def get_rates_from_mqtt():
    global rate_in, rate_out, mqtt_connected
    try:
        client = mqtt.Client()
        client.username_pw_set(USERNAME, PASSWORD)
        client.on_message = on_message

        print("Attempting to connect to MQTT broker...")
        client.connect(BROKER, PORT, 60)
        print("Connected to MQTT broker successfully!")
        client.subscribe(TOPIC)
        print("Subscribed to topic 'tank/rates'. Waiting for message... (timeout in 60s)")

        start_time = time.time()
        while client.is_connected() and (time.time() - start_time) < 60:
            client.loop(timeout=0.1)

        if client.is_connected():
            print("Timeout: No message received. Using default rates.")
            client.disconnect()
    except Exception as e:
        print(f"MQTT connection error: {e}. Using default rates.")


# Try to get rates from MQTT
try:
    get_rates_from_mqtt()
except Exception as e:
    print(f"MQTT setup error: {e}. Using default rates.")

# DEBUG: Print current rates before calculations
print(f"DEBUG: Final rate_in = {rate_in}, rate_out = {rate_out}")

# Now proceed with the rest of the script using the fetched rates

# Clear the scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Parameters
tank_height = 5.0
tank_outer_radius = 2.0
tank_inner_radius = 1.8
inlet_radius = 0.2
outlet_radius = 0.2
water_radius = tank_inner_radius - 0.1

# Volume calculation (using inner radius for water volume inside)
volume = math.pi * (tank_inner_radius ** 2) * tank_height
print(f"DEBUG: Tank volume = {volume:.2f} units^3")

# Time calculations (dynamic based on rates)
t_fill = volume / rate_in
t_drain = volume / rate_out
total_time = t_fill + t_drain

# Print the calculated times to console
print(f"Time to fill the tank: {t_fill:.2f} seconds (at rate_in = {rate_in})")
print(f"Time to drain the tank: {t_drain:.2f} seconds (at rate_out = {rate_out})")
print(f"Total simulation time: {total_time:.2f} seconds")

# Set frame rate and end frame
fps = 24
bpy.context.scene.render.fps = fps
bpy.context.scene.frame_end = int(total_time * fps) + 10

# Create tank (solid cylinder)
bpy.ops.mesh.primitive_cylinder_add(radius=tank_outer_radius, depth=tank_height, location=(0, 0, tank_height / 2))
tank_outer = bpy.context.active_object
tank_outer.name = "Tank_Outer"

# Add collision modifier to tank to contain particles
collision_mod = tank_outer.modifiers.new(name="Collision", type='COLLISION')
collision_mod.settings.thickness_outer = 0.2  # Increased thickness for better containment
print("DEBUG: Collision modifier added to tank.")

# Add material to tank (transparent for glass-like effect)
tank_mat = bpy.data.materials.new(name="Tank_Material")
tank_mat.diffuse_color = (0.8, 0.8, 0.8, 0.3)  # Semi-transparent gray
tank_mat.use_nodes = True  # Enable node-based materials for transparency
principled_bsdf = tank_mat.node_tree.nodes.get('Principled BSDF')
if principled_bsdf:
    principled_bsdf.inputs['Alpha'].default_value = 0.3  # Low alpha for transparency
    tank_mat.blend_method = 'BLEND'  # Enable alpha blending
tank_outer.data.materials.append(tank_mat)

# Create inlet pipe (horizontal, slightly down in tank)
bpy.ops.mesh.primitive_cylinder_add(radius=inlet_radius, depth=2.0,
                                    location=(0, tank_outer_radius, tank_height - 0.5))  # Slightly down in tank
inlet = bpy.context.active_object
inlet.name = "Inlet_Pipe"
inlet.rotation_euler[0] = math.radians(90)  # Rotate 90 degrees around X-axis to make horizontal
inlet.data.materials.append(tank_mat)

# Create a small plane for inlet particle emission (inner face)
bpy.ops.mesh.primitive_plane_add(size=0.4, location=(0, tank_outer_radius - 0.5, tank_height - 0.5))  # At inner end of pipe
inlet_emitter = bpy.context.active_object
inlet_emitter.name = "Inlet_Emitter"
inlet_emitter.rotation_euler[0] = math.radians(-90)  # Rotate to face downward into tank
# Temporarily visible for debugging
inlet_emitter.hide_viewport = False  # Make visible in viewport
inlet_emitter.hide_render = True  # Hide in render

# Create outlet pipe (horizontal, at bottom, extended for better emission)
bpy.ops.mesh.primitive_cylinder_add(radius=outlet_radius, depth=2.0,  # Increased depth for longer pipe
                                    location=(0, -tank_outer_radius - outlet_radius, 0.5))
outlet = bpy.context.active_object
outlet.name = "Outlet_Pipe"
outlet.rotation_euler[0] = math.radians(90)  # Rotate 90 degrees around X-axis to make horizontal
outlet.data.materials.append(tank_mat)

# Create solid plane under the tank
bpy.ops.mesh.primitive_plane_add(size=10.0, location=(0, 0, -0.1))  # Large plane below tank
plane = bpy.context.active_object
plane.name = "Floor_Plane"
plane_mat = bpy.data.materials.new(name="Floor_Material")
plane_mat.diffuse_color = (0.5, 0.5, 0.5, 1.0)  # Solid gray
plane.data.materials.append(plane_mat)

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
fill_frames = int(t_fill * fps)
water.scale[2] = 0.0  # Start flat at bottom
water.keyframe_insert(data_path="scale", frame=1, index=2)

water.scale[2] = tank_height / 0.01  # Scale factor to reach tank_height
water.keyframe_insert(data_path="scale", frame=fill_frames, index=2)

# Draining phase: after full, scale back to 0 over t_drain seconds
drain_start_frame = fill_frames
drain_end_frame = fill_frames + int(t_drain * fps)
water.keyframe_insert(data_path="scale", frame=drain_start_frame, index=2)  # Still full
water.scale[2] = 0.0
water.keyframe_insert(data_path="scale", frame=drain_end_frame, index=2)

# Create a small sphere for water drops
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.05)  # Increased radius for larger drops
drop_obj = bpy.context.active_object
drop_obj.name = "Water_Drop"
drop_obj.data.materials.append(water_mat)

# Add particle system for water flow from inlet (filling) - particles from inner face only
inlet_emitter.select_set(True)
bpy.context.view_layer.objects.active = inlet_emitter
bpy.ops.object.particle_system_add()
ps_fill = inlet_emitter.particle_systems[0]
ps_fill.name = "Water_Inflow"
ps_settings = ps_fill.settings
ps_settings.name = "Water_Inflow_Settings"
ps_settings.count = 15000  # Increased count for denser emission
ps_settings.frame_start = 1
ps_settings.frame_end = fill_frames
ps_settings.lifetime = 300  # Very long lifetime
ps_settings.emit_from = 'FACE'
ps_settings.normal_factor = -1.0  # Downward into tank
ps_settings.tangent_factor = 0.0
ps_settings.physics_type = 'NEWTON'
ps_settings.effector_weights.gravity = 1.0  # Full gravity
ps_settings.size_random = 0.0
ps_settings.particle_size = 0.2  # Increased size for larger drops
ps_settings.render_type = 'OBJECT'  # Render as objects for drop-like appearance
ps_settings.instance_object = drop_obj  # Use the sphere as water drop
ps_settings.use_modifier_stack = True  # Enable collision with modifiers
print("DEBUG: Inlet particle system created (particles from inner face only, into the tank).")

# Now hide the emitter plane in render only
inlet_emitter.hide_render = True

# Add particle system for water flow from outlet (draining) - like a flow of water from the end
outlet.select_set(True)
bpy.context.view_layer.objects.active = outlet
bpy.ops.object.particle_system_add()
ps_drain = outlet.particle_systems[0]
ps_drain.name = "Water_Outflow"
ps_settings_drain = ps_drain.settings
ps_settings_drain.name = "Water_Outflow_Settings"
ps_settings_drain.count = 15000  # Higher count for denser flow
ps_settings_drain.frame_start = drain_start_frame
ps_settings_drain.frame_end = drain_end_frame
ps_settings_drain.lifetime = 300  # Very long lifetime
ps_settings_drain.emit_from = 'VERT'  # Emit from vertices (ends of the pipe)
ps_settings_drain.normal_factor = 1.0  # Outward velocity from the pipe end
ps_settings_drain.tangent_factor = 0.0
ps_settings_drain.physics_type = 'NEWTON'
ps_settings_drain.effector_weights.gravity = 1.0  # Full gravity
ps_settings_drain.size_random = 0.0
ps_settings_drain.particle_size = 0.08  # Increased size for larger drops
ps_settings_drain.render_type = 'OBJECT'  # Render as objects for drop-like flow
ps_settings_drain.instance_object = drop_obj  # Use the sphere as water drop
ps_settings_drain.use_modifier_stack = True  # Enable collision with modifiers
print("DEBUG: Outlet particle system created (particles flowing from the end of the pipe).")

# Create a text object to display rates and times
bpy.ops.object.text_add(location=(5, 0, tank_height + 1))
text_obj = bpy.context.active_object
text_obj.name = "Rates_Display"
text_obj.data.body = f"Rate In: {rate_in}\nRate Out: {rate_out}\nFill Time: {t_fill:.2f}s\nDrain Time: {t_drain:.2f}s"
text_obj.data.size = 0.5
text_obj.data.align_x = 'LEFT'

# Create a text object for phase-specific time (filling or draining)
bpy.ops.object.text_add(location=(5, 0, tank_height - 1))  # Position below the first text
phase_text_obj = bpy.context.active_object
phase_text_obj.name = "Phase_Time_Display"
phase_text_obj.data.body = "Filling Time: 0.00s"  # Initial value (starts with filling)
phase_text_obj.data.size = 0.5
phase_text_obj.data.align_x = 'LEFT'

# Visual indicator for the first text
if mqtt_connected:
    text_obj.data.materials.new(name="Text_Material")
    text_mat = text_obj.data.materials[0]
    text_mat.diffuse_color = (0.0, 1.0, 0.0, 1.0)
    print("MQTT Status: Connected - Rates received from publisher!")
else:
    print("MQTT Status: Not connected - Using default rates.")


# Function to update phase time on frame change
def update_phase_time(scene):
    current_frame = scene.frame_current
    if current_frame <= fill_frames:
        # Filling phase
        phase_time = (current_frame - 1) / fps
        phase_text_obj.data.body = f"Filling Time: {phase_time:.2f}s"
    elif current_frame <= drain_end_frame:
        # Draining phase
        phase_time = (current_frame - fill_frames) / fps
        phase_text_obj.data.body = f"Draining Time: {phase_time:.2f}s"
    else:
        # After draining, keep at max
        phase_text_obj.data.body = f"Draining Time: {t_drain:.2f}s"


# Register the frame change handler
bpy.app.handlers.frame_change_post.append(update_phase_time)

# Optional: Add a camera and light
bpy.ops.object.camera_add(location=(10, -10, 10), rotation=(math.radians(60), 0, math.radians(45)))
bpy.context.scene.camera = bpy.context.active_object

bpy.ops.object.light_add(type='SUN', location=(5, 5, 10))

print(f"Blender script executed. Tank model created with water animation using rate_in={rate_in}, rate_out={rate_out}.")