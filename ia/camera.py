"""camera.py — cameras and framing.

Rules of thumb (see docs/WORKFLOW.md, "Camera"):
  * position decides perspective, focal length only crops — place the camera first;
  * tilting up converges verticals; keep the camera level and use shift_y to reframe
    when verticals should stay parallel.
"""
import math
import bpy
from mathutils import Vector
from .scene import col


def look_at(obj, target):
    """Aim -Z at target. Uses obj.location for unparented objects: a freshly created
    object's matrix_world is still identity until the depsgraph updates, which would
    silently aim from the world origin."""
    origin = obj.location if obj.parent is None else obj.matrix_world.translation
    d = Vector(target) - Vector(origin)
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def add_cam(name, loc, target, lens=35, sensor=36.0, shift=(0.0, 0.0), level=False, c=None,
            clip=(0.05, 3000)):
    """Camera at loc aimed at target. level=True keeps the camera horizontal (no tilt,
    parallel verticals) and frames the target with lens shift instead."""
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = sensor
    cd.clip_start, cd.clip_end = clip
    o = bpy.data.objects.new(name, cd)
    o.location = Vector(loc)
    (c or col("Cameras")).objects.link(o)
    cd.shift_x, cd.shift_y = shift
    if level:
        d = Vector(target) - Vector(loc)
        o.rotation_euler = (math.radians(90), 0, -math.atan2(d.x, d.y))
        # lens shift is measured in units of the sensor's larger dimension: put the
        # target where a tilted camera would have centred it, verticals stay parallel
        cd.shift_y += (d.z / max(math.hypot(d.x, d.y), 1e-6)) * lens / sensor
    else:
        look_at(o, target)
    return o


def set_dof(cam, focus_obj=None, fstop=4.0, distance=None):
    cam.data.dof.use_dof = True
    if focus_obj is not None:
        cam.data.dof.focus_object = focus_obj
    if distance is not None:
        cam.data.dof.focus_distance = distance
    cam.data.dof.aperture_fstop = fstop


def set_resolution(width, height, scale=1.0):
    r = bpy.context.scene.render
    r.resolution_x, r.resolution_y = int(width * scale), int(height * scale)
    r.resolution_percentage = 100


ASPECTS = {"16:9": (1920, 1080), "2.39:1": (2048, 858), "4:5": (1600, 2000), "2:3": (1600, 2400),
           "1:1": (1600, 1600), "3:2": (2100, 1400)}
