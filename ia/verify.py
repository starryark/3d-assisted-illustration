"""verify.py — measure, don't eyeball.

Report/asserts, exact evaluated bounds, ray-cast ground contact, ray-cast visibility,
and image statistics including the grayscale value-separation test (is the subject
readable as a value shape against what surrounds it?).
"""
import json
import os
import bpy
import numpy as np
from mathutils import Vector
from .scene import log, upd


# ------------------------------------------------------------------ report
class Report:
    """Collects asserts (label, ok, detail) and arbitrary values; written as JSON.
    Labels must be static strings: reports are compared label by label."""

    def __init__(self, name, path):
        self.name, self.path = name, path
        self.data = {"name": name, "asserts": []}

    def put(self, key, value):
        if isinstance(value, Vector):
            value = [round(x, 4) for x in value]
        self.data[key] = value

    def check(self, label, ok, detail=""):
        ok = bool(ok)
        self.data["asserts"].append({"label": label, "ok": ok, "detail": str(detail)})
        log(("PASS " if ok else "FAIL ") + label, detail)
        return ok

    @property
    def failed(self):
        return [a["label"] for a in self.data["asserts"] if not a["ok"]]

    def write(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1, default=str)
        return self.path


# ------------------------------------------------------------------ geometry
def world_bbox(objs):
    """Fast AABB from transformed local box corners. INFLATED for rotated objects —
    use mesh_bounds for contact/height work."""
    lo = Vector((1e9, 1e9, 1e9)); hi = -lo
    for o in objs:
        if o.type != 'MESH':
            continue
        for c in o.bound_box:
            v = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, v)); hi = Vector(map(max, hi, v))
    return lo, hi


def mesh_bounds(objs, depsgraph=None):
    """Exact world AABB from evaluated vertices (modifiers, booleans, armatures)."""
    dg = depsgraph or bpy.context.evaluated_depsgraph_get()
    lo = Vector((1e9, 1e9, 1e9)); hi = -lo
    for o in objs:
        if o.type not in {'MESH', 'CURVE'}:
            continue
        ev = o.evaluated_get(dg)
        try:
            me = ev.to_mesh()
        except RuntimeError:
            continue
        if me is None or not len(me.vertices):
            ev.to_mesh_clear()
            continue
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        M = np.array(ev.matrix_world)
        w = co @ M[:3, :3].T + M[:3, 3]
        lo = Vector(np.minimum(np.array(lo), w.min(0))); hi = Vector(np.maximum(np.array(hi), w.max(0)))
        ev.to_mesh_clear()
    return lo, hi


def world_verts(o, depsgraph=None):
    dg = depsgraph or bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    mw = ev.matrix_world
    out = [mw @ v.co for v in me.vertices]
    ev.to_mesh_clear()
    return out


def ray_down(x, y, z_from=100.0, ignore=(), ignore_prefix=()):
    """z of the first surface below (x, y, z_from), ignoring named objects / prefixes.

    Ignored objects are hidden for the cast rather than stepped through: an object resting
    on a surface has its base COPLANAR with that surface, and stepping past the ignored
    hit would also skip the surface it stands on."""
    sc = bpy.context.scene
    pref = tuple(ignore_prefix) if ignore_prefix else ()
    hidden = [o for o in sc.objects if not o.hide_viewport and
              (o.name in ignore or (pref and o.name.startswith(pref)))]
    for o in hidden:
        o.hide_viewport = True
    try:
        upd()
        dg = bpy.context.evaluated_depsgraph_get()
        hit, loc, nrm, idx, obj, mtx = sc.ray_cast(dg, Vector((x, y, z_from)), Vector((0, 0, -1)))
    finally:
        for o in hidden:
            o.hide_viewport = False
        if hidden:
            upd()
    return (loc.z, obj) if hit else (None, None)


def contact_offset(objs, probe_above=0.5, ignore_prefix=()):
    """Signed gap between the objects' lowest vertex and the surface under their
    centre, probing from just above them (so slabs overhead don't count)."""
    lo, hi = mesh_bounds(objs)
    names = {o.name for o in objs}
    gz, _ = ray_down((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z + probe_above, ignore=names,
                     ignore_prefix=ignore_prefix)
    return (lo.z - gz) if gz is not None else None


def settle(root, objs, lift=0.0, ignore_prefix=()):
    """Move `root` vertically so the lowest evaluated vertex of `objs` touches the
    surface below their centre."""
    upd()
    lo, hi = mesh_bounds(objs)
    names = {o.name for o in objs} | {root.name}
    gz, _ = ray_down((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, ignore=names, ignore_prefix=ignore_prefix)
    gz = 0.0 if gz is None else gz
    root.location.z += gz - lo.z + lift
    upd()
    return gz


def visible_frac(cam, pts, target_names, see_through=("Fog",)):
    """Fraction of world points inside cam's frame AND not occluded (camera ray)."""
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    origin = cam.matrix_world.translation
    vis = 0
    for p in pts:
        co = world_to_camera_view(sc, cam, Vector(p))
        if not (0.0 <= co.x <= 1.0 and 0.0 <= co.y <= 1.0 and co.z > 0):
            continue
        d = Vector(p) - origin
        hit, loc, nrm, idx, obj, mtx = sc.ray_cast(dg, origin, d.normalized(), distance=d.length - 0.01)
        if not hit or obj.name in target_names or obj.name.startswith(tuple(see_through)):
            vis += 1
    return vis / max(len(pts), 1)


def in_frame(cam, p):
    from bpy_extras.object_utils import world_to_camera_view
    co = world_to_camera_view(bpy.context.scene, cam, Vector(p))
    return (co.x, co.y) if co.z > 0 else None


# ------------------------------------------------------------------ images
def load_rgba(path):
    """Image file -> float array (H, W, 4), raw values (no colour conversion)."""
    img = bpy.data.images.load(path, check_existing=False)
    img.colorspace_settings.name = 'Non-Color'
    w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)[::-1]          # top row first


def luma(rgba):
    return rgba[..., :3] @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def image_stats(path):
    y = luma(load_rgba(path))
    return dict(mean=round(float(y.mean()), 3), p50=round(float(np.median(y)), 3),
                crush=round(float((y < 0.02).mean()) * 100, 2), clip=round(float((y > 0.98).mean()) * 100, 2))


def dilate(mask, r):
    """Binary dilation by r pixels with shifted ORs (no scipy inside Blender)."""
    out = mask.copy()
    for dy in range(-r, r + 1, max(1, r // 4)):
        for dx in range(-r, r + 1, max(1, r // 4)):
            if dx * dx + dy * dy > r * r:
                continue
            out |= np.roll(np.roll(mask, dy, 0), dx, 1)
    return out


def value_separation(image_path, mask_path, ring_frac=0.04):
    """The grayscale readability test made numeric: mean luma inside the subject mask
    versus a ring just outside it (ring width = ring_frac of the image height).
    Returns dict(inside, ring, delta, coverage)."""
    y = luma(load_rgba(image_path))
    m = luma(load_rgba(mask_path)) > 0.5
    if not m.any():
        return dict(inside=None, ring=None, delta=0.0, coverage=0.0)
    r = max(2, int(ring_frac * y.shape[0]))
    ring = dilate(m, r) & ~m
    inside, around = float(y[m].mean()), float(y[ring].mean()) if ring.any() else float(y[~m].mean())
    return dict(inside=round(inside, 3), ring=round(around, 3), delta=round(abs(inside - around), 3),
                coverage=round(float(m.mean()) * 100, 2))


def mask_coverage(mask_path):
    m = luma(load_rgba(mask_path)) > 0.5
    return round(float(m.mean()) * 100, 3)
