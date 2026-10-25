"""mannequin.py — articulated character placeholder.

The 3D figure only has to solve body scale against the architecture, pose and
foreshortening, contact, cast-shadow direction and which parts catch the light; face,
hair and clothing are drawn in 2D. This one is built from pivots (empties) and simple
capsules with human proportions, so poses are exact and contacts are measurable.

Local frame: faces -Y, origin on the ground between the feet, height = H.
"""
import math
import bmesh
import bpy
from mathutils import Vector, Matrix, Euler, Quaternion
from .scene import col, upd
from . import materials as M
from . import posing as PS
from . import verify as VF

# proportions as fractions of the height (adult, ~7.5 heads)
PROP = dict(ankle=0.045, shin=0.245, thigh=0.245, hip_x=0.055, spine=0.60, shoulder=0.815, sh_x=0.105,
            neck_top=0.87, head_c=0.935, head_r=0.066, upper=0.185, fore=0.16, hand=0.10,
            foot_len=0.15, foot_w=0.055, torso_r=0.074, pelvis=(0.095, 0.06, 0.065))


def _capsule(name, r0, r1, length, seg=16):
    """Capsule along -Z from 0 to -length (radii r0 at the top, r1 at the bottom)."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r1, radius2=r0, depth=length,
                          matrix=Matrix.Translation((0, 0, -length / 2)))
    for r, z in ((r0, 0.0), (r1, -length)):
        bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=8, radius=r, matrix=Matrix.Translation((0, 0, z)))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.shade_smooth()
    return me


def _ellipsoid(name, rx, ry, rz, seg=20):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=12, radius=1.0, matrix=Matrix.Diagonal((rx, ry, rz, 1)))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.shade_smooth()
    return me


def build(name="Figure", loc=(0, 0, 0), yaw_deg=0.0, height=1.7, color=(0.72, 0.68, 0.64), c=None):
    """Build the mannequin. Returns a dict of pivots and parts."""
    H = height; p = PROP
    c = c or col("Character")
    mat = M.flat(f"{name}_Skin", color, 0.55)
    root = bpy.data.objects.new(name, None); root.empty_display_type = 'ARROWS'
    root.location = Vector(loc); root.rotation_euler = (0, 0, math.radians(yaw_deg))
    c.objects.link(root)
    P = dict(root=root, name=name, height=H, parts=[])

    def piv(n, parent, l):
        e = bpy.data.objects.new(f"{name}_{n}", None); e.empty_display_size = 0.03
        e.parent = parent; e.location = Vector(l); c.objects.link(e)
        P[n] = e
        return e

    def part(n, me, parent, l=(0, 0, 0), rot=(0, 0, 0)):
        o = bpy.data.objects.new(f"{name}_{n}", me); o.parent = parent
        o.location = Vector(l); o.rotation_euler = Euler(rot)
        o.data.materials.append(mat); c.objects.link(o)
        P["parts"].append(o)
        return o
    hip_z = (p["ankle"] + p["shin"] + p["thigh"]) * H
    pelvis = piv("pelvis", root, (0, 0, hip_z))
    part("pelvis_m", _ellipsoid(f"{name}_pelvis", *(x * H for x in p["pelvis"])), pelvis, (0, 0, 0.025 * H))
    spine = piv("spine", pelvis, (0, 0, (p["spine"] * H) - hip_z))
    tl = (p["shoulder"] - p["spine"]) * H
    torso = part("torso", _capsule(f"{name}_torso", p["torso_r"] * H, p["torso_r"] * 0.85 * H, tl * 0.82), spine,
                 (0, 0, tl * 0.9), (0, 0, 0))
    torso.scale = (1.0, 0.68, 1.0)
    neck = piv("neck", spine, (0, 0, tl))
    nl = (p["neck_top"] - p["shoulder"]) * H
    part("neck_m", _capsule(f"{name}_neck", 0.026 * H, 0.03 * H, nl), neck, (0, 0, nl))
    head = piv("head", neck, (0, 0, nl))
    head.rotation_mode = 'QUATERNION'
    hc = (p["head_c"] - p["neck_top"]) * H
    part("head_m", _ellipsoid(f"{name}_head", p["head_r"] * H * 0.88, p["head_r"] * H * 0.95, p["head_r"] * H * 1.05),
         head, (0, -0.005 * H, hc))
    bm = bmesh.new()                                                      # nose: shows facing
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.012 * H, radius2=0.0, depth=0.03 * H,
                          matrix=Matrix.Translation((0, 0, 0.015 * H)))
    me = bpy.data.meshes.new(f"{name}_nose"); bm.to_mesh(me); bm.free()
    part("nose", me, head, (0, -p["head_r"] * H * 0.9, hc), (math.radians(90), 0, 0))
    P["head_center_local"] = Vector((0, 0, hc))
    for s, sx in (("L", 1), ("R", -1)):
        sh = piv(f"sh{s}", spine, (sx * p["sh_x"] * H, 0, tl - 0.01 * H))
        part(f"upper{s}", _capsule(f"{name}_upper", 0.04 * H * 0.75, 0.032 * H * 0.75, p["upper"] * H), sh)
        el = piv(f"elbow{s}", sh, (0, 0, -p["upper"] * H))
        part(f"fore{s}", _capsule(f"{name}_fore", 0.03 * H * 0.75, 0.024 * H * 0.75, p["fore"] * H), el)
        hd = piv(f"hand{s}", el, (0, 0, -p["fore"] * H))
        hand = part(f"hand_m{s}", _ellipsoid(f"{name}_hand", 0.022 * H, 0.012 * H, p["hand"] * H / 2), hd,
                    (0, 0, -p["hand"] * H / 2))
        hip = piv(f"hip{s}", pelvis, (sx * p["hip_x"] * H, 0, 0))
        part(f"thigh{s}", _capsule(f"{name}_thigh", 0.06 * H * 0.8, 0.042 * H * 0.8, p["thigh"] * H), hip)
        kn = piv(f"knee{s}", hip, (0, 0, -p["thigh"] * H))
        part(f"shin{s}", _capsule(f"{name}_shin", 0.042 * H * 0.8, 0.03 * H * 0.8, p["shin"] * H), kn)
        an = piv(f"ankle{s}", kn, (0, 0, -p["shin"] * H))
        fl, fw, fh = p["foot_len"] * H, p["foot_w"] * H, p["ankle"] * H
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, -fl * 0.33, -fh / 2)) @ Matrix.Diagonal((fw, fl, fh, 1)))
        me = bpy.data.meshes.new(f"{name}_foot"); bm.to_mesh(me); bm.free()
        part(f"foot{s}", me, an)
        sh.rotation_euler = (0, math.radians(-6 * sx), 0)
    upd()
    return P


def head_center(P):
    upd()
    return P["head"].matrix_world @ P["head_center_local"]


def look_at(P, target, max_deg=60.0, roll_deg=0.0):
    """Turn the head (about its neck pivot) toward a world target, clamped."""
    upd()
    hd = P["head"]
    d = (Vector(target) - head_center(P)).normalized()
    par = hd.parent.matrix_world.to_3x3().normalized()
    d_loc = (par.inverted() @ d).normalized()
    q = Vector((0, -1, 0)).rotation_difference(d_loc)
    if q.angle > 1e-6:
        q = Quaternion().slerp(q, min(1.0, math.radians(max_deg) / q.angle))
    fwd = q @ Vector((0, -1, 0))
    hd.rotation_quaternion = Quaternion(fwd, math.radians(roll_deg)) @ q
    upd()


def lean(P, fwd_deg=0.0, side_deg=0.0):
    """Bend the spine forward (toward -Y local) / sideways."""
    P["spine"].rotation_euler = (math.radians(fwd_deg), math.radians(side_deg), 0)
    upd()


def reach(P, side, target, pole):
    """Place a hand pivot (wrist) on a world target with the elbow toward pole."""
    return PS.two_joint_pivots(P["sh" + side], P["elbow" + side], P["hand" + side], target, pole)


def pose_sit(P, seat_z, edge=None, lean_deg=8.0, knee_deg=88.0, hands_on_seat=True, spread_deg=6.0,
             margin=0.04):
    """Sit on a surface at world height seat_z. edge=(point, outward_normal) describes the
    seat's front edge (e.g. a parapet): the figure slides along the normal until the knees
    are `margin` past it, so the shins hang over. Hands rest on the seat beside the hips."""
    root = P["root"]
    for s, sx in (("L", 1), ("R", -1)):
        P["hip" + s].rotation_euler = (math.radians(-90), math.radians(-spread_deg * sx), 0)
        P["knee" + s].rotation_euler = (math.radians(knee_deg), 0, 0)
        P["ankle" + s].rotation_euler = (math.radians(90 - knee_deg), 0, 0)
    lean(P, fwd_deg=lean_deg)
    upd()
    seat_parts = [o for o in P["parts"] if any(k in o.name for k in ("pelvis_m", "thigh"))]
    lo, hi = VF.mesh_bounds(seat_parts)
    root.location.z += seat_z - lo.z
    upd()
    if edge is not None:
        pt, n = Vector(edge[0]), Vector(edge[1]).normalized()
        knee = (P["kneeL"].matrix_world.translation + P["kneeR"].matrix_world.translation) / 2
        past = (knee - pt).dot(n)                       # how far the knees are beyond the edge
        root.location += n * (margin - past)
        upd()
    if hands_on_seat:
        R = root.matrix_world.to_3x3().normalized()
        for s, sx in (("L", 1), ("R", -1)):
            hip = P["hip" + s].matrix_world.translation
            tgt = hip + R @ Vector((sx * 0.13 * P["height"], 0.06 * P["height"], 0))
            tgt.z = seat_z + P["height"] * PROP["hand"]
            pole = hip + R @ Vector((sx * 0.5, 0.4, 0.6))
            reach(P, s, tgt, pole)
    return P


def seat_contact(P, seat_z):
    """Gap between the lowest pelvis/thigh vertex and the seat height (m)."""
    lo, hi = VF.mesh_bounds([o for o in P["parts"] if any(k in o.name for k in ("pelvis_m", "thigh"))])
    return lo.z - seat_z
