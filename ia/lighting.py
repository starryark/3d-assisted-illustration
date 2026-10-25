"""lighting.py — one clear lighting idea: a dominant sun, a sky/HDRI for ambient, and a
few local lights where they serve the composition."""
import math
import os
import bpy
from mathutils import Vector, Euler
from .scene import col


def sun(direction=None, azimuth=None, elevation=None, energy=4.0, color=(1.0, 0.86, 0.7), angle_deg=1.0,
        name="Sun"):
    """direction: vector the light TRAVELS along. Or azimuth (deg, 0 = light coming from
    +Y toward -Y, positive toward +X) and elevation (deg above the horizon)."""
    if direction is None:
        az, el = math.radians(azimuth or 0.0), math.radians(elevation if elevation is not None else 30.0)
        src = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
        direction = -src
    ld = bpy.data.lights.new(name, 'SUN')
    ld.energy = energy; ld.color = color; ld.angle = math.radians(angle_deg)
    o = bpy.data.objects.new(name, ld)
    o.rotation_euler = Vector(direction).normalized().to_track_quat('-Z', 'Y').to_euler()
    col("Lighting").objects.link(o)
    return o


def sky_gradient(horizon=(0.95, 0.72, 0.52), zenith=(0.22, 0.32, 0.5), ground=(0.06, 0.055, 0.05),
                 strength=0.8, name="Sky"):
    """Procedural sky: ground -> horizon -> zenith ramp on the view direction."""
    w = bpy.data.worlds.new(name)
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree; L = nt.links
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Generated"], sep.inputs[0])
    r = nt.nodes.new("ShaderNodeValToRGB")
    cr = r.color_ramp
    cr.elements[0].position = 0.0; cr.elements[0].color = (*ground, 1)
    cr.elements[1].position = 0.5; cr.elements[1].color = (*horizon, 1)
    e = cr.elements.new(0.75); e.color = (*zenith, 1)
    L.new(sep.outputs["Z"], r.inputs["Fac"])
    L.new(r.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    return w


def hdri(path, strength=1.0, rotation_deg=0.0, name="HDRI"):
    """Image-based world light. If you also use a sun, align it with the HDRI's sun (or
    pick a diffuse HDRI) — two competing shadow directions read as wrong."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    w = bpy.data.worlds.new(name)
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree; L = nt.links
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(rotation_deg))
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(path, check_existing=True)
    L.new(tc.outputs["Generated"], mp.inputs["Vector"]); L.new(mp.outputs["Vector"], env.inputs["Vector"])
    L.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    return w


def area(name, loc, target, energy=100.0, size=2.0, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy; ld.size = size; ld.color = color
    o = bpy.data.objects.new(name, ld)
    o.location = Vector(loc)
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    col("Lighting").objects.link(o)
    return o


def spot(name, loc, target, energy=1000.0, size_deg=20.0, blend=0.4, color=(1, 1, 1), radius=0.1):
    ld = bpy.data.lights.new(name, 'SPOT')
    ld.energy = energy; ld.color = color; ld.spot_size = math.radians(size_deg); ld.spot_blend = blend
    ld.shadow_soft_size = radius
    o = bpy.data.objects.new(name, ld)
    o.location = Vector(loc)
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    col("Lighting").objects.link(o)
    return o


def point(name, loc, energy=10.0, color=(1, 1, 1), radius=0.05):
    ld = bpy.data.lights.new(name, 'POINT')
    ld.energy = energy; ld.color = color; ld.shadow_soft_size = radius
    o = bpy.data.objects.new(name, ld)
    o.location = Vector(loc)
    col("Lighting").objects.link(o)
    return o
