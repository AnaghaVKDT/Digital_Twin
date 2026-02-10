import bpy
import math
import sys
import time
import json
import threading
import paho.mqtt.client as mqtt

print("Blender script started.")

# Add paho-mqtt path (adjust if needed)
sys.path.append(r'C:\\Users\\milan.s\\AppData\\Roaming\\Python\\Python311\\site-packages')

# Updated MQTT settings for LOCAL MOSQUITTO (matches your publisher)
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "tank/rates"
USERNAME = None  # No auth for local Mosquitto
PASSWORD = None

# Global variables - ALL declared at top
rate_in = None
rate_out = None
mqtt_connected = False
received_data = {"rate_in": None, "rate_out": None}
message_received = threading.Event()
fill_frames_global = 0
drain_start_frame_global = 0
drain_end_frame_global = 0
t_drain_global = 0.0
phase_text_obj_global = None


# Enhanced MQTT callbacks (paho-mqtt v2 compatible)
def on_message(client, userdata, msg):
    global received_data, message_received, mqtt_connected
    try:
        raw_payload = msg.payload.decode()
        print(f"🔍 RAW MQTT MESSAGE: '{raw_payload}'")
        data = json.loads(raw_payload)
        print(f"📊 PARSED JSON: {data}")

        if 'rate_in' in data and 'rate_out' in data:
            received_data["rate_in"] = float(data['rate_in'])
            received_data["rate_out"] = float(data['rate_out'])
            message_received.set()
            mqtt_connected = True
            print(f"✅ RATES RECEIVED: rate_in={received_data['rate_in']}, rate_out={received_data['rate_out']}")
        else:
            print(f"❌ Missing required keys: needs 'rate_in' and 'rate_out'")
    except Exception as e:
        print(f"❌ MQTT Error: {e}")


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("✅ Connected to MQTT broker")
        client.subscribe(TOPIC)
        print(f"📡 Subscribed to '{TOPIC}'")
    else:
        print(f"❌ Connection failed with code {rc}")


def get_rates_from_mqtt():
    global rate_in, rate_out, mqtt_connected
    client = None
    try:
        print("🌐 Connecting to local MQTT broker...")
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)

        if USERNAME and PASSWORD:
            client.username_pw_set(USERNAME, PASSWORD)

        client.on_message = on_message
        client.on_connect = on_connect

        client.connect(BROKER, PORT, 60)
        client.loop_start()

        print("⏳ Waiting for MQTT message (30s timeout)...")
        if message_received.wait(timeout=30):
            rate_in = received_data["rate_in"]
            rate_out = received_data["rate_out"]
            print(f"🎉 SUCCESS: rate_in={rate_in}, rate_out={rate_out}")
            return True
        else:
            print("⏰ Timeout: No message received in 30 seconds")
            return False

    except Exception as e:
        print(f"🔌 MQTT Connection Error: {e}")
        return False
    finally:
        if client:
            client.loop_stop()
            client.disconnect()


# Get rates from MQTT
print("🚀 Starting MQTT connection...")
mqtt_success = get_rates_from_mqtt()

print(f"📈 FINAL STATUS: rate_in={rate_in}, rate_out={rate_out}, connected={mqtt_connected}")

# CHECK: Stop simulation if no valid rates
if not mqtt_success or rate_in is None or rate_out is None:
    print("❌ No valid MQTT data received. Simulation not created.")
    print("💡 TIP: 1. Start Mosquitto broker 2. Run publisher script 3. Then run this Blender script!")
    print("Blender remains open - try again when publisher is running.")
else:
    print(f"🎉 MQTT Success: Using rate_in={rate_in}, rate_out={rate_out}")

    # Simulation parameters
    inlet_valve_percentage = 0.5  # 50% open
    outlet_valve_percentage = 1.0  # 100% open

    # Adjust rates based on valve percentages
    effective_rate_in = rate_in * inlet_valve_percentage if inlet_valve_percentage > 0 else 0.001
    effective_rate_out = rate_out * outlet_valve_percentage if outlet_valve_percentage > 0 else 0.001
    t_fill = 0.0

    print(f"🔧 Effective rates: in={effective_rate_in}, out={effective_rate_out}")

    # Clear scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    # Tank parameters
    tank_height = 5.0
    tank_outer_radius = 2.0
    tank_inner_radius = 1.8
    inlet_radius = 0.2
    outlet_radius = 0.2
    water_radius = tank_inner_radius - 0.1

    # Volume calculation
    volume = math.pi * (tank_inner_radius ** 2) * tank_height
    print(f"📦 Tank volume = {volume:.2f} units³")

    # Time calculations - NOW assign to globals
    fps = 24
    t_fill = volume / effective_rate_in
    t_drain_global = volume / effective_rate_out
    total_time = t_fill + t_drain_global
    fill_frames_global = int(t_fill * fps)
    drain_start_frame_global = fill_frames_global
    drain_end_frame_global = fill_frames_global + int(t_drain_global * fps)

    print(f"⏱️  Fill time: {t_fill:.2f}s, Drain time: {t_drain_global:.2f}s, Total: {total_time:.2f}s")

    # Set timeline
    bpy.context.scene.render.fps = fps
    bpy.context.scene.frame_end = int(total_time * fps) + 10

    # Create tank outer
    bpy.ops.mesh.primitive_cylinder_add(radius=tank_outer_radius, depth=tank_height, location=(0, 0, tank_height / 2))
    tank_outer = bpy.context.active_object
    tank_outer.name = "Tank_Outer"

    # Create tank inner for hollowing
    bpy.ops.mesh.primitive_cylinder_add(radius=tank_inner_radius, depth=tank_height, location=(0, 0, tank_height / 2))
    tank_inner = bpy.context.active_object
    tank_inner.name = "Tank_Inner"

    # Add boolean modifier to make hollow
    bool_mod = tank_outer.modifiers.new(name="Boolean", type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = tank_inner

    # Apply the modifier
    bpy.context.view_layer.objects.active = tank_outer
    bpy.ops.object.modifier_apply(modifier="Boolean")

    # Delete the inner cylinder
    bpy.ops.object.select_all(action='DESELECT')
    tank_inner.select_set(True)
    bpy.ops.object.delete(use_global=False)

    # Collision modifier
    collision_mod = tank_outer.modifiers.new(name="Collision", type='COLLISION')
    collision_mod.settings.thickness_outer = 0.2

    # Tank material (glass-like using Glass BSDF)
    tank_mat = bpy.data.materials.new(name="Tank_Material")
    tank_mat.diffuse_color = (0.8, 0.8, 0.8, 0.3)  # Semi-transparent gray
    tank_mat.use_nodes = True  # Enable node-based materials for transparency
    principled_bsdf = tank_mat.node_tree.nodes.get('Principled BSDF')
    if principled_bsdf:
        principled_bsdf.inputs['Alpha'].default_value = 0.3  # Low alpha for transparency
        tank_mat.blend_method = 'BLEND'  # Enable alpha blending
    tank_outer.data.materials.append(tank_mat)
    # Clear default nodes
    for node in tank_mat.node_tree.nodes:
        tank_mat.node_tree.nodes.remove(node)
    # Add Glass BSDF
    glass_node = tank_mat.node_tree.nodes.new('ShaderNodeBsdfGlass')
    glass_node.inputs['IOR'].default_value = 1.45
    glass_node.inputs['Roughness'].default_value = 0.0
    # Add Material Output
    output_node = tank_mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    # Link
    tank_mat.node_tree.links.new(glass_node.outputs['BSDF'], output_node.inputs['Surface'])
    tank_mat.blend_method = 'BLEND'
    tank_outer.data.materials.append(tank_mat)

    # Inlet pipe
    bpy.ops.mesh.primitive_cylinder_add(radius=inlet_radius, depth=2.0,
                                        location=(0, tank_outer_radius, tank_height - 0.5))
    inlet = bpy.context.active_object
    inlet.name = "Inlet_Pipe"
    inlet.rotation_euler[0] = math.radians(90)
    inlet.data.materials.append(tank_mat)

    # Inlet valve
    bpy.ops.mesh.primitive_cylinder_add(radius=0.1, depth=0.2, location=(0, tank_outer_radius + 0.5, tank_height - 0.5))
    valve_inlet = bpy.context.active_object
    valve_inlet.name = "Inlet_Valve"
    valve_inlet.rotation_euler[0] = math.radians(90)
    valve_inlet.rotation_euler[2] = math.radians(inlet_valve_percentage * 90)
    valve_mat = bpy.data.materials.new(name="Valve_Material")
    valve_mat.diffuse_color = (0.2, 0.2, 0.2, 1.0)
    valve_inlet.data.materials.append(valve_mat)

    # Inlet emitter plane
    bpy.ops.mesh.primitive_plane_add(size=0.4, location=(0, tank_outer_radius - 0.5, tank_height - 0.5))
    inlet_emitter = bpy.context.active_object
    inlet_emitter.name = "Inlet_Emitter"
    inlet_emitter.rotation_euler[0] = math.radians(-90)
    inlet_emitter.hide_render = True

    # Outlet pipe
    bpy.ops.mesh.primitive_cylinder_add(radius=outlet_radius, depth=2.0,
                                        location=(0, -tank_outer_radius - outlet_radius, 0.5))
    outlet = bpy.context.active_object
    outlet.name = "Outlet_Pipe"
    outlet.rotation_euler[0] = math.radians(90)
    outlet.data.materials.append(tank_mat)

    # Outlet valve
    bpy.ops.mesh.primitive_cylinder_add(radius=0.1, depth=0.2,
                                        location=(0, -tank_outer_radius - outlet_radius - 0.5, 0.5))
    valve_outlet = bpy.context.active_object
    valve_outlet.name = "Outlet_Valve"
    valve_outlet.rotation_euler[0] = math.radians(90)
    valve_outlet.rotation_euler[2] = math.radians(outlet_valve_percentage * 90)
    valve_outlet.data.materials.append(valve_mat)

    # Floor plane
    bpy.ops.mesh.primitive_plane_add(size=10.0, location=(0, 0, -0.1))
    plane = bpy.context.active_object
    plane.name = "Floor_Plane"
    plane_mat = bpy.data.materials.new(name="Floor_Material")
    plane_mat.diffuse_color = (0.5, 0.5, 0.5, 1.0)
    plane.data.materials.append(plane_mat)

    # Water level
    bpy.ops.mesh.primitive_cylinder_add(radius=water_radius, depth=0.01, location=(0, 0, 0.005))
    water = bpy.context.active_object
    water.name = "Water"

    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')

    water_mat = bpy.data.materials.new(name="Water_Material")
    water_mat.diffuse_color = (0.0, 0.5, 1.0, 0.8)
    water.data.materials.append(water_mat)

    # Animate water level
    water.scale[2] = 0.0
    water.keyframe_insert(data_path="scale", frame=1, index=2)
    water.scale[2] = tank_height / 0.01
    water.keyframe_insert(data_path="scale", frame=fill_frames_global, index=2)
    water.keyframe_insert(data_path="scale", frame=drain_start_frame_global, index=2)
    water.scale[2] = 0.0
    water.keyframe_insert(data_path="scale", frame=drain_end_frame_global, index=2)

    # Water drop instance
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.05)
    drop_obj = bpy.context.active_object
    drop_obj.name = "Water_Drop"
    drop_obj.data.materials.append(water_mat)

    # Inlet particles
    inlet_emitter.select_set(True)
    bpy.context.view_layer.objects.active = inlet_emitter
    bpy.ops.object.particle_system_add()
    ps_fill = inlet_emitter.particle_systems[0]
    ps_fill.name = "Water_Inflow"
    ps_settings = ps_fill.settings
    ps_settings.count = int(15000 * inlet_valve_percentage)
    ps_settings.frame_start = 1
    ps_settings.frame_end = fill_frames_global
    ps_settings.lifetime = 300
    ps_settings.emit_from = 'FACE'
    ps_settings.normal_factor = -1.0
    ps_settings.physics_type = 'NEWTON'
    ps_settings.effector_weights.gravity = 1.0
    ps_settings.particle_size = 0.2
    ps_settings.render_type = 'OBJECT'
    ps_settings.instance_object = drop_obj
    ps_settings.use_modifier_stack = True

    # Outlet particles
    outlet.select_set(True)
    bpy.context.view_layer.objects.active = outlet
    bpy.ops.object.particle_system_add()
    ps_drain = outlet.particle_systems[0]
    ps_drain.name = "Water_Outflow"
    ps_settings_drain = ps_drain.settings
    ps_settings_drain.count = int(15000 * outlet_valve_percentage)
    ps_settings_drain.frame_start = drain_start_frame_global
    ps_settings_drain.frame_end = drain_end_frame_global
    ps_settings_drain.lifetime = 300
    ps_settings_drain.emit_from = 'VERT'
    ps_settings_drain.normal_factor = 1.0
    ps_settings_drain.physics_type = 'NEWTON'
    ps_settings_drain.effector_weights.gravity = 1.0
    ps_settings_drain.particle_size = 0.08
    ps_settings_drain.render_type = 'OBJECT'
    ps_settings_drain.instance_object = drop_obj
    ps_settings_drain.use_modifier_stack = True

    # Info text
    bpy.ops.object.text_add(location=(5, 0, tank_height + 1))
    text_obj = bpy.context.active_object
    text_obj.name = "Rates_Display"
    text_obj.data.body = (f"RAW MQTT rate_in: {rate_in}\n"
                          f"RAW MQTT rate_out: {rate_out}\n"
                          f"Effective In: {effective_rate_in:.3f}\n"
                          f"Effective Out: {effective_rate_out:.3f}\n"
                          f"Fill: {t_fill:.1f}s | Drain: {t_drain_global:.1f}s")
    text_obj.data.size = 0.4

    # Create phase time text object FIRST
    bpy.ops.object.text_add(location=(5, 0, tank_height - 1))
    phase_text_obj_global = bpy.context.active_object
    phase_text_obj_global.name = "Phase_Time_Display"
    phase_text_obj_global.data.body = "Filling: 0.00s"
    phase_text_obj_global.data.size = 0.4


    # Frame change handler - uses suffixed global names
    def update_phase_time(scene):
        global fill_frames_global, drain_end_frame_global, t_drain_global, phase_text_obj_global
        current_frame = scene.frame_current
        fps = scene.render.fps

        if current_frame <= fill_frames_global:
            phase_time = (current_frame - 1) / fps
            phase_text_obj_global.data.body = f"Filling: {phase_time:.2f}s"
        elif current_frame <= drain_end_frame_global:
            phase_time = (current_frame - fill_frames_global) / fps
            phase_text_obj_global.data.body = f"Draining: {phase_time:.2f}s"
        else:
            phase_text_obj_global.data.body = f"Complete: {t_drain_global:.2f}s"


    bpy.app.handlers.frame_change_post.append(update_phase_time)

    # Camera and light
    bpy.ops.object.camera_add(location=(10, -10, 10), rotation=(math.radians(60), 0, math.radians(45)))
    bpy.context.scene.camera = bpy.context.active_object
    bpy.ops.object.light_add(type='SUN', location=(5, 5, 10))

    print("✅ Tank simulation created successfully!")

print("🏁 Script completed. Press SPACEBAR to play animation.")