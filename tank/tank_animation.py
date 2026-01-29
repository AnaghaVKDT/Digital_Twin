import bpy
import math
import bmesh

# =============================
# RESET SCENE
# =============================
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

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

# Hollow pipes - **OUTLET NOW AT BOTTOM**
for pipe_name, loc_z in [("InletPipe", TANK_HEIGHT - 0.5), ("OutletPipe", 0.1)]:  # **CHANGED: 0.1 = bottom**
    x = -1.2 if "Inlet" in pipe_name else 1.2
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

# =============================
# ANIMATION: FILL → FULL → **COMPLETELY EMPTY** (UPDATED OUTLET LOGIC)
# =============================
current_volume = 0.0
tank_filled = False

for frame in range(1, TOTAL_FRAMES + 1):
    time_sec = frame / FPS
    prev_time = 0.0 if frame == 1 else (frame - 1) / FPS
    delta_time = time_sec - prev_time
    
    inlet_added = 0.0
    outlet_removed = 0.0
    
    # **STOP INLET WHEN 99% FULL**
    if current_volume >= FULL_VOLUME * 0.99:
        tank_filled = True
    
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
print(f"Outlet at bottom (0.1m) | Animation: {TOTAL_TIME}s | Fill:~15s | Drain:~300s")



