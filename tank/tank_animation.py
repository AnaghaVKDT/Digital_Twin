import bpy
import math
import bmesh

# =============================
# RESET SCENE (FIXED FOR CONTEXT ISSUES)
# =============================
# Instead of bpy.ops.object.select_all and delete, use direct removal to avoid context errors
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

# =============================
# CONSTANTS (EXTENDED DRAIN TIME)
# =============================
TANK_RADIUS = 1.0
TANK_HEIGHT = 3.0
TANK_WALL_THICKNESS = 0.05
PIPE_OUTER_RADIUS = 0.08
PIPE_INNER_RADIUS = 0.06
PIPE_LENGTH = 1.5

INLET_FLOW = 0.8       # m^3/s
OUTLET_FLOW = 0.5     # m^3/s

FPS = 24
DRAIN_TIME = 300       # 5 MINUTES to clearly see complete drain
TOTAL_TIME = 20 + DRAIN_TIME
TOTAL_FRAMES = FPS * TOTAL_TIME

TANK_AREA = math.pi * TANK_RADIUS ** 2
FULL_VOLUME = TANK_AREA * TANK_HEIGHT

# =============================
# TANK + WATER + PIPES
# =============================
# Tank (hollow)
bpy.ops.mesh.primitive_cylinder_add(radius=TANK_RADIUS, depth=TANK_HEIGHT, location=(0, 0, TANK_HEIGHT / 2))
tank_outer = bpy.context.active_object
bpy.ops.mesh.primitive_cylinder_add(radius=TANK_RADIUS - TANK_WALL_THICKNESS, depth=TANK_HEIGHT + 0.01, location=(0, 0, TANK_HEIGHT / 2))
tank_inner = bpy.context.active_object
bpy.context.view_layer.objects.active = tank_outer
bpy.ops.object.select_all(action='DESELECT')
tank_outer.select_set(True); tank_inner.select_set(True)
bpy.ops.object.modifier_add(type='BOOLEAN')
tank_outer.modifiers["Boolean"].object = tank_inner
tank_outer.modifiers["Boolean"].operation = 'DIFFERENCE'
bpy.ops.object.modifier_apply(modifier="Boolean")
bpy.data.objects.remove(tank_inner, do_unlink=True)
tank_outer.name = "Tank"
tank_outer.display_type = 'WIRE'

# Water
bpy.ops.mesh.primitive_cylinder_add(radius=(TANK_RADIUS - TANK_WALL_THICKNESS) * 0.97, depth=TANK_HEIGHT, location=(0, 0, TANK_HEIGHT / 2))
water = bpy.context.active_object
water.name = "Water"
water.scale[2] = 0.001
water.location[2] = 0.001
mat = bpy.data.materials.new("WaterMaterial")
mat.use_nodes = True
nodes = mat.node_tree.nodes
bsdf = nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.0, 0.4, 0.9, 1)
bsdf.inputs["Roughness"].default_value = 0.1
bsdf.inputs["Alpha"].default_value = 0.5
mat.blend_method = 'BLEND'
water.data.materials.append(mat)

# Hollow pipes - **OUTLET NOW AT BOTTOM** - ADJUSTED INLET POSITION FOR BETTER FLOW
pipes = {}
for pipe_name, loc_z in [("InletPipe", TANK_HEIGHT - 0.5), ("OutletPipe", 0.1)]:  # **CHANGED: 0.1 = bottom**
    x = -0.75 if "Inlet" in pipe_name else 1.2  # **ADJUSTED: Inlet center at -0.75 so end reaches x=0 (tank center)**
    bpy.ops.mesh.primitive_cylinder_add(radius=PIPE_OUTER_RADIUS, depth=PIPE_LENGTH, location=(x, 0, loc_z), rotation=(0, math.radians(90), 0))
    outer = bpy.context.active_object
    bpy.ops.mesh.primitive_cylinder_add(radius=PIPE_INNER_RADIUS, depth=PIPE_LENGTH + 0.01, location=(x, 0, loc_z), rotation=(0, math.radians(90), 0))
    inner = bpy.context.active_object
    bpy.context.view_layer.objects.active = outer
    bpy.ops.object.select_all(action='DESELECT')
    outer.select_set(True); inner.select_set(True)
    bpy.ops.object.modifier_add(type='BOOLEAN')
    outer.modifiers["Boolean"].object = inner
    outer.modifiers["Boolean"].operation = 'DIFFERENCE'
    bpy.ops.object.modifier_apply(modifier="Boolean")
    bpy.data.objects.remove(inner, do_unlink=True)
    outer.name = pipe_name
    pipes[pipe_name] = outer

# =============================
# ADD WATER FLOW FROM INLET PIPE (LIGHT PARTICLE SYSTEM)
# =============================
# Create a small plane emitter at the end of the inlet pipe (now at tank edge)
inlet_pipe = pipes["InletPipe"]
x_inlet = -0.75
emission_loc = (x_inlet + PIPE_LENGTH / 2, 0, TANK_HEIGHT - 0.5)  # End of inlet pipe, now at x=0
bpy.ops.mesh.primitive_plane_add(size=0.05, location=emission_loc, rotation=(0, math.radians(90), 0))  # Rotate to match pipe direction
emitter = bpy.context.active_object
emitter.name = "InletEmitter"
emitter.hide_render = True  # Hide the emitter plane in renders

bpy.context.view_layer.objects.active = emitter
bpy.ops.object.particle_system_add()
psys = emitter.particle_systems[0]
psys.settings.name = "WaterFlow"
settings = psys.settings
settings.emit_from = 'FACE'
settings.use_emit_random = False
settings.normal_factor = 1.0
settings.particle_size = 0.05  # Increased for better visibility
settings.render_type = 'OBJECT'
settings.lifetime = 200  # Long enough to reach tank bottom
settings.count = 2000  # Increased for denser flow
settings.frame_start = 1
settings.frame_end = TOTAL_FRAMES  # Will be adjusted later to stop at fill end
settings.effector_weights.gravity = 1.0  # Particles fall down

# Create small sphere for particle (water drop) - MADE LARGER FOR VISIBILITY
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.05, location=(0, 0, 0))  # Increased radius for easier selection/visibility
particle_obj = bpy.context.active_object
particle_obj.name = "WaterDrop"
drop_mat = bpy.data.materials.new("DropMaterial")
drop_mat.use_nodes = True
drop_nodes = drop_mat.node_tree.nodes
drop_bsdf = drop_nodes.get("Principled BSDF")
drop_bsdf.inputs["Base Color"].default_value = (0.0, 0.4, 0.9, 1)
drop_bsdf.inputs["Alpha"].default_value = 0.8
drop_mat.blend_method = 'BLEND'
particle_obj.data.materials.append(drop_mat)
settings.instance_object = particle_obj

# =============================
# ANIMATION: FILL → FULL → **COMPLETELY EMPTY** (UPDATED OUTLET LOGIC)
# =============================
current_volume = 0.0
tank_filled = False
tank_filled_frame = None  # Track when filling stops

for frame in range(1, TOTAL_FRAMES + 1):
    time_sec = frame / FPS
    prev_time = 0.0 if frame == 1 else (frame - 1) / FPS
    delta_time = time_sec - prev_time
    
    inlet_added = 0.0
    outlet_removed = 0.0
    
    # **STOP INLET WHEN 99% FULL**
    if current_volume >= FULL_VOLUME * 0.99:
        tank_filled = True
        if tank_filled_frame is None:
            tank_filled_frame = frame  # Record the frame when filling stops
    
    if not tank_filled:
        # FILLING PHASE
        inlet_added = INLET_FLOW * delta_time
        water_height = current_volume / TANK_AREA
        outlet_removed = OUTLET_FLOW * delta_time if water_height > 0.1 else 0.0  # **CHANGED: outlet at 0.1m**
    else:
        # **DRAINING PHASE** - Inlet OFF, Outlet ON (bottom drain)
        inlet_added = 0.0
        water_height = current_volume / TANK_AREA
        outlet_removed = OUTLET_FLOW * delta_time if water_height > 0.1 else 0.0  # **CHANGED: outlet at 0.1m**
    
    # Update volume
    current_volume += (inlet_added - outlet_removed)
    current_volume = min(current_volume, FULL_VOLUME)
    current_volume = max(current_volume, 0.0)
    
    # Animate
    water_height = current_volume / TANK_AREA
    scale_z = water_height / TANK_HEIGHT
    water.scale[2] = scale_z
    water.location[2] = water_height / 2
    water.keyframe_insert(data_path="scale", frame=frame)
    water.keyframe_insert(data_path="location", frame=frame)

# Adjust particle emission to stop when filling ends
if tank_filled_frame is not None:
    psys.settings.frame_end = tank_filled_frame

# Linear keyframes
if water.animation_data and water.animation_data.action:
    for fcurve in water.animation_data.action.fcurves:
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = 'LINEAR'

# =============================
# SCENE SETTINGS
# =============================
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = TOTAL_FRAMES
scene.render.fps = FPS
print(f"Outlet at bottom (0.1m) | Animation: {TOTAL_TIME}s | Fill:~15s | Drain:~300s | Particles flow from inlet during filling, stop when tank is full")