"""kits.py — procedural modelling kits.

"Model the forms that define your composition; obtain reusable objects whose
complexity would otherwise consume your production time." These kits cover the first
half, so a scene can be fully built without downloads:

  MB                  mesh builder: boxes, irregular chunks, rods -> one object, material slots
  facade_building     modular tower: volume, floor bands, window module repeated per bay,
                      per-window lit glass, rooftop clutter; LOD 'near' | 'far'
  landmark_tower      custom silhouette: tapered stages, ring platforms, lattice spire, beacons
  ruin_frame          damaged RC frame (slabs, columns, spandrels, rebar) — from the case study (docs/CASE_STUDY.md)
  rubble_pile, rebar_tuft, debris_piece
  roof_slab           rooftop with parapet (the "stage" of a rooftop scene)
  hvac_unit, water_tank, door_hut, antenna_mast, utility_pole, railing, pipe_run
  elevated_rail       deck + piers + rails along a line
  cable / catenary    sagging wires between points (bezier, bevelled)
  grass_tuft + scatter  geometry-nodes instancing over up-facing faces with masks/exclusions

Everything takes a seeded random.Random so builds are reproducible.
"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler
from .scene import col
from . import materials as M


def rebar_mat():
    return M.flat("Rebar", (0.16, 0.07, 0.035), 0.75, 0.6)


class MB:
    """Accumulates boxes/prisms into one bmesh with material indices."""
    def __init__(self):
        self.bm = bmesh.new()
        self.mi = []

    def box(self, center, size, rot=(0, 0, 0), mat=0, jitter=0.0, rng=None):
        M = Matrix.Translation(Vector(center)) @ Euler(rot).to_matrix().to_4x4() @ \
            Matrix.Diagonal((size[0], size[1], size[2], 1))
        ret = bmesh.ops.create_cube(self.bm, size=1.0, matrix=M)
        if jitter and rng:
            for v in ret["verts"]:
                v.co += Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * jitter
        for f in {f for v in ret["verts"] for f in v.link_faces}:
            f.material_index = mat
        return ret

    def chunk(self, center, size, rng, mat=0, rough=0.25):
        """Irregular rubble chunk: subdivided cube with strong vertex noise."""
        M = Matrix.Translation(Vector(center)) @ Euler((rng.uniform(0, 6.3), rng.uniform(0, 6.3),
                                                       rng.uniform(0, 6.3))).to_matrix().to_4x4() @ \
            Matrix.Diagonal((size[0], size[1], size[2], 1))
        if rng.random() < 0.5:   # angular slab chunk
            ret = bmesh.ops.create_cube(self.bm, size=1.0, matrix=M)
        else:                    # rounder broken lump
            ret = bmesh.ops.create_icosphere(self.bm, subdivisions=1, radius=0.55, matrix=M)
        allv = list(ret["verts"])
        s = min(size) * rough
        for v in allv:
            v.co += Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * s
        for f in {f for v in allv for f in v.link_faces}:
            f.material_index = mat
        return allv

    def rod(self, a, b, r=0.012, mat=1, seg=6):
        a, b = Vector(a), Vector(b)
        d = b - a
        L = d.length
        if L < 1e-4:
            return
        q = d.normalized().to_track_quat('Z', 'Y')
        M = Matrix.Translation((a + b) / 2) @ q.to_matrix().to_4x4()
        ret = bmesh.ops.create_cone(self.bm, cap_ends=True, segments=seg, radius1=r, radius2=r,
                                    depth=L, matrix=M)
        for f in {f for v in ret["verts"] for f in v.link_faces}:
            f.material_index = mat

    def to_object(self, name, mats, c, bevel=0.0, smooth=False):
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me); self.bm.free()
        for m in mats:
            me.materials.append(m)
        if smooth:
            me.shade_smooth()
            try:
                me.set_sharp_from_angle(angle=math.radians(35))
            except Exception:
                pass
        o = bpy.data.objects.new(name, me)
        c.objects.link(o)
        if bevel:
            bv = o.modifiers.new("Bevel", 'BEVEL')
            bv.width = bevel; bv.segments = 1; bv.limit_method = 'ANGLE'
            bv.angle_limit = math.radians(40)
        return o


def rebar_tuft(mb, top, rng, n=4, length=(0.3, 0.9), spread=0.12, up=Vector((0, 0, 1))):
    """Bent rebar sticking out of a broken concrete end."""
    for _ in range(n):
        base = Vector(top) + Vector((rng.uniform(-spread, spread), rng.uniform(-spread, spread), 0))
        L = rng.uniform(*length)
        bend = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)) * rng.uniform(0.1, 0.6)
        mid = base + up * L * 0.55
        tip = mid + (up * 0.45 + bend).normalized() * L * 0.5
        mb.rod(base, mid, 0.011)
        mb.rod(mid, tip, 0.011)


def _in_damage(p, damage):
    for c, r in damage:
        if (Vector(p) - Vector(c)).length < r:
            return True
    return False


def ruin_frame(name, x0, x1, y0, y1, floors, fh=3.3, damage=(), seed=0, c=None,
             facade_sides=("xmin", "xmax", "ymin", "ymax"), infill=0.55):
    """Ruined RC-frame building: columns, slabs (cells), spandrels, window infill,
    damage spheres carve it away, broken edges sprout rebar."""
    rng = random.Random(seed)
    mb = MB()
    nx = max(2, round((x1 - x0) / 4.6)); ny = max(2, round((y1 - y0) / 4.6))
    xs = [x0 + (x1 - x0) * i / nx for i in range(nx + 1)]
    ys = [y0 + (y1 - y0) * j / ny for j in range(ny + 1)]
    top = floors * fh
    # slabs
    for k in range(1, floors + 1):
        z = k * fh
        for i in range(nx):
            for j in range(ny):
                cx = (xs[i] + xs[i + 1]) / 2; cy = (ys[j] + ys[j + 1]) / 2
                if _in_damage((cx, cy, z), damage) or rng.random() < 0.05:
                    # hanging slab near the hole
                    if rng.random() < 0.18 and not _in_damage((cx, cy, z + fh), damage):
                        ang = math.radians(rng.uniform(18, 50)) * rng.choice([-1, 1])
                        mb.box((cx, cy, z - 1.2), (xs[i + 1] - xs[i] - 0.1, ys[j + 1] - ys[j] - 0.1, 0.26),
                               (ang if rng.random() < .5 else 0, 0 if rng.random() < .5 else ang, 0),
                               jitter=0.06, rng=rng)
                    continue
                mb.box((cx, cy, z), (xs[i + 1] - xs[i] + 0.02, ys[j + 1] - ys[j] + 0.02, 0.28),
                       jitter=0.015, rng=rng)
                # broken edge rebar where neighbour is missing
                for (dx, dy) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ni, nj = i + dx, j + dy
                    if 0 <= ni < nx and 0 <= nj < ny:
                        ncx = (xs[ni] + xs[ni + 1]) / 2; ncy = (ys[nj] + ys[nj + 1]) / 2
                        if _in_damage((ncx, ncy, z), damage) and rng.random() < 0.6:
                            ex = cx + dx * (xs[i + 1] - xs[i]) / 2
                            ey = cy + dy * (ys[j + 1] - ys[j]) / 2
                            for _ in range(5):
                                a = Vector((ex + rng.uniform(-1.5, 1.5) * (dy != 0),
                                            ey + rng.uniform(-1.5, 1.5) * (dx != 0), z))
                                b = a + Vector((dx, dy, 0)) * rng.uniform(0.3, 1.1) + \
                                    Vector((0, 0, -rng.uniform(0.0, 0.5)))
                                mb.rod(a, b, 0.012)
    # columns
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            for k in range(floors):
                z0 = k * fh
                if _in_damage((x, y, z0 + fh * 0.5), damage):
                    continue
                h = fh
                broken = _in_damage((x, y, z0 + fh), damage) or (k == floors - 1 and rng.random() < 0.25)
                if broken:
                    h = fh * rng.uniform(0.25, 0.8)
                mb.box((x, y, z0 + h / 2), (0.5, 0.5, h), jitter=0.01, rng=rng)
                if broken:
                    rebar_tuft(mb, (x, y, z0 + h), rng, n=4, length=(0.4, 1.2), spread=0.18)
    # spandrels + infill on facades
    def facade(side):
        if side in ("xmin", "xmax"):
            x = x0 if side == "xmin" else x1
            for j in range(ny):
                for k in range(floors):
                    z = (k + 1) * fh
                    cy = (ys[j] + ys[j + 1]) / 2; w = ys[j + 1] - ys[j]
                    if _in_damage((x, cy, z - 0.4), damage):
                        continue
                    mb.box((x, cy, z - 0.45), (0.3, w, 0.9), jitter=0.02, rng=rng)   # spandrel
                    if rng.random() < infill and not _in_damage((x, cy, z - fh / 2), damage):
                        # infill wall with a window opening: sill + 2 piers
                        mb.box((x, cy, z - fh + 0.5), (0.22, w - 0.5, 1.0), jitter=0.02, rng=rng)
                        for s in (-1, 1):
                            mb.box((x, cy + s * (w / 2 - 0.7), z - fh / 2 - 0.2), (0.22, 0.9, fh - 1.4),
                                   jitter=0.02, rng=rng)
        else:
            y = y0 if side == "ymin" else y1
            for i in range(nx):
                for k in range(floors):
                    z = (k + 1) * fh
                    cx = (xs[i] + xs[i + 1]) / 2; w = xs[i + 1] - xs[i]
                    if _in_damage((cx, y, z - 0.4), damage):
                        continue
                    mb.box((cx, y, z - 0.45), (w, 0.3, 0.9), jitter=0.02, rng=rng)
                    if rng.random() < infill and not _in_damage((cx, y, z - fh / 2), damage):
                        mb.box((cx, y, z - fh + 0.5), (w - 0.5, 0.22, 1.0), jitter=0.02, rng=rng)
                        for s in (-1, 1):
                            mb.box((cx + s * (w / 2 - 0.7), y, z - fh / 2 - 0.2), (0.9, 0.22, fh - 1.4),
                                   jitter=0.02, rng=rng)
    for s in facade_sides:
        facade(s)
    o = mb.to_object(name, [M.concrete(), rebar_mat()], c or col("Env_Buildings"), bevel=0.03)
    return o


def rubble_pile(name, center, radius, height, n=140, seed=0, c=None, slabs=5, rebar=5,
                size=(0.15, 0.9)):
    """Mound of concrete chunks + a few slabs and bent rebar, one mesh."""
    rng = random.Random(seed)
    mb = MB()
    cx, cy = center[0], center[1]
    for i in range(n):
        r = radius * math.sqrt(rng.random())
        a = rng.uniform(0, 2 * math.pi)
        h = height * max(0.0, 1 - (r / radius) ** 1.6)
        s = rng.uniform(*size) * (0.6 + 0.6 * (1 - r / radius))
        p = (cx + r * math.cos(a), cy + r * math.sin(a), max(s * 0.25, h - s * 0.35))
        mb.chunk(p, (s, s * rng.uniform(0.5, 1.0), s * rng.uniform(0.35, 0.8)), rng)
    for i in range(slabs):
        r = radius * rng.uniform(0.1, 0.8); a = rng.uniform(0, 2 * math.pi)
        h = height * max(0.0, 1 - (r / radius) ** 1.6)
        L = rng.uniform(0.45, 0.95) * radius
        mb.box((cx + r * math.cos(a), cy + r * math.sin(a), h * 0.7),
               (L, L * rng.uniform(0.45, 0.8), 0.06 + 0.05 * radius),
               (math.radians(rng.uniform(-35, 35)), math.radians(rng.uniform(-35, 35)), rng.uniform(0, 6.3)),
               jitter=0.05, rng=rng)
    for i in range(rebar):
        r = radius * rng.uniform(0.0, 0.7); a = rng.uniform(0, 2 * math.pi)
        h = height * max(0.0, 1 - (r / radius) ** 1.6)
        base = Vector((cx + r * math.cos(a), cy + r * math.sin(a), h * 0.8))
        rebar_tuft(mb, base, rng, n=1, length=(0.15 * radius, 0.4 * radius), spread=0.3,
                   up=Vector((rng.uniform(-.9, .9), rng.uniform(-.9, .9), 0.6)).normalized())
    return mb.to_object(name, [M.concrete("ConcreteRubble", (0.47, 0.45, 0.41), moss=0.3), rebar_mat()],
                        c or col("Env_Rubble"), bevel=0.0)


def grass_tuft(name, rng, blades=11, h=(0.08, 0.26), c=None):
    bm = bmesh.new()
    for i in range(blades):
        a = rng.uniform(0, 2 * math.pi)
        r0 = rng.uniform(0, 0.04)
        base = Vector((r0 * math.cos(a), r0 * math.sin(a), 0))
        lean = Vector((math.cos(a), math.sin(a), 0)) * rng.uniform(0.05, 0.35)
        H = rng.uniform(*h); w = rng.uniform(0.006, 0.012)
        side = Vector((-math.sin(a), math.cos(a), 0))
        prev = None
        segs = 4
        for s in range(segs + 1):
            t = s / segs
            p = base + lean * H * t * t + Vector((0, 0, H * t))
            ww = w * (1 - t * 0.9)
            v1 = bm.verts.new(p - side * ww); v2 = bm.verts.new(p + side * ww)
            if prev:
                bm.faces.new((prev[0], prev[1], v2, v1))
            prev = (v1, v2)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    me.materials.append(M.grass_mat())
    o = bpy.data.objects.new(name, me)
    (c or col("Lib_Instances")).objects.link(o)
    return o


def debris_piece(name, rng, size, c=None):
    mb = MB()
    mb.chunk((0, 0, 0), (size, size * rng.uniform(0.5, 1), size * rng.uniform(0.3, 0.7)), rng, rough=0.3)
    return mb.to_object(name, [M.concrete("ConcreteRubble", (0.47, 0.45, 0.41), moss=0.3)],
                        c or col("Lib_Instances"))


def scatter(obj, inst_col, name, density, seed, scale=(0.7, 1.3), mask_scale=0.3,
            mask_thresh=0.5, up_only=0.6, rand_tilt=0.0, exclude=None):
    """Geometry-nodes scatter of a collection's objects over obj's up-facing faces.
    exclude = (cx, cy, r): keep a clear circle (e.g. around the hero)."""
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes.new; Lk = ng.links.new
    gi = N('NodeGroupInput'); go = N('NodeGroupOutput')
    dist = N('GeometryNodeDistributePointsOnFaces')
    dist.inputs['Density'].default_value = density
    dist.inputs['Seed'].default_value = seed
    pos = N('GeometryNodeInputPosition')
    tex = N('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value = mask_scale
    tex.inputs['Detail'].default_value = 4.0
    Lk(pos.outputs[0], tex.inputs['Vector'])
    cmp = N('FunctionNodeCompare'); cmp.data_type = 'FLOAT'; cmp.operation = 'GREATER_THAN'
    cmp.inputs[1].default_value = mask_thresh
    Lk(tex.outputs['Fac'], cmp.inputs[0])
    nrm = N('GeometryNodeInputNormal'); sep = N('ShaderNodeSeparateXYZ')
    Lk(nrm.outputs[0], sep.inputs[0])
    cmp2 = N('FunctionNodeCompare'); cmp2.data_type = 'FLOAT'; cmp2.operation = 'GREATER_THAN'
    cmp2.inputs[1].default_value = up_only
    Lk(sep.outputs['Z'], cmp2.inputs[0])
    band = N('FunctionNodeBooleanMath'); band.operation = 'AND'
    Lk(cmp.outputs[0], band.inputs[0]); Lk(cmp2.outputs[0], band.inputs[1])
    sel = band
    if exclude:
        zones = [exclude] if isinstance(exclude[0], (int, float)) else list(exclude)
        flat = N('ShaderNodeVectorMath'); flat.operation = 'MULTIPLY'
        flat.inputs[1].default_value = (1, 1, 0)
        Lk(pos.outputs[0], flat.inputs[0])
        for (cx, cy, r) in zones:          # keep clear circles (hero, camera lenses)
            dsub = N('ShaderNodeVectorMath'); dsub.operation = 'DISTANCE'
            dsub.inputs[1].default_value = (cx, cy, 0)
            Lk(flat.outputs[0], dsub.inputs[0])
            cmp3 = N('FunctionNodeCompare'); cmp3.data_type = 'FLOAT'; cmp3.operation = 'GREATER_THAN'
            cmp3.inputs[1].default_value = r
            Lk(dsub.outputs['Value'], cmp3.inputs[0])
            band2 = N('FunctionNodeBooleanMath'); band2.operation = 'AND'
            Lk(sel.outputs[0], band2.inputs[0]); Lk(cmp3.outputs[0], band2.inputs[1])
            sel = band2
    Lk(gi.outputs[0], dist.inputs['Mesh'])
    Lk(sel.outputs[0], dist.inputs['Selection'])
    ci = N('GeometryNodeCollectionInfo')
    ci.inputs['Collection'].default_value = inst_col
    ci.inputs['Separate Children'].default_value = True
    ci.inputs['Reset Children'].default_value = True
    iop = N('GeometryNodeInstanceOnPoints')
    iop.inputs['Pick Instance'].default_value = True
    Lk(dist.outputs['Points'], iop.inputs['Points'])
    Lk(ci.outputs[0], iop.inputs['Instance'])
    rr = N('FunctionNodeRandomValue'); rr.data_type = 'FLOAT_VECTOR'
    rr.inputs['Min'].default_value = (-rand_tilt, -rand_tilt, 0)
    rr.inputs['Max'].default_value = (rand_tilt, rand_tilt, 6.283)
    rr.inputs['Seed'].default_value = seed + 1
    Lk(rr.outputs['Value'], iop.inputs['Rotation'])
    # Blender 5.2 Random Value: dynamic sockets Min/Max/ID/Seed -> Value
    rs = N('FunctionNodeRandomValue'); rs.data_type = 'FLOAT'
    rs.inputs['Min'].default_value = scale[0]; rs.inputs['Max'].default_value = scale[1]
    rs.inputs['Seed'].default_value = seed + 2
    Lk(rs.outputs['Value'], iop.inputs['Scale'])
    ri = N('FunctionNodeRandomValue'); ri.data_type = 'INT'
    ri.inputs['Min'].default_value = 0; ri.inputs['Max'].default_value = 99
    ri.inputs['Seed'].default_value = seed + 3
    Lk(ri.outputs['Value'], iop.inputs['Instance Index'])
    join = N('GeometryNodeJoinGeometry')
    Lk(gi.outputs[0], join.inputs[0]); Lk(iop.outputs[0], join.inputs[0])
    Lk(join.outputs[0], go.inputs[0])
    mod = obj.modifiers.new(name, 'NODES')
    mod.node_group = ng
    return mod


def cable(name, pts, radius=0.0045, color=(0.012, 0.012, 0.012), c=None):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'; cu.bevel_depth = radius; cu.bevel_resolution = 3
    sp = cu.splines.new('BEZIER')
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = Vector(p)
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
    cu.materials.append(M.flat("CableRubber", color, 0.45))
    o = bpy.data.objects.new(name, cu)
    (c or col("Props")).objects.link(o)
    return o


def floor_path(a, b, rng, n=6, wiggle=0.25, z=0.012):
    """Points lying on the floor between a and b with lazy S-bends."""
    a, b = Vector(a), Vector(b)
    d = b - a; d.z = 0
    side = Vector((-d.y, d.x, 0)).normalized()
    pts = []
    for i in range(1, n):
        t = i / n
        p = a.lerp(b, t) + side * math.sin(t * math.pi * 1.5 + rng.uniform(-.4, .4)) * wiggle * (1 - abs(2 * t - 1) * 0.3)
        p.z = z
        pts.append(p)
    return pts


# ====================================================================== cities
def facade_grid(name="FacadeGrid", wall=(0.32, 0.31, 0.3), window=(0.03, 0.035, 0.045),
                lit=(1.0, 0.7, 0.4), lit_strength=2.5, bay=(3.2, 3.4), lit_fraction=0.2):
    """Far-LOD facade: a brick-texture window grid in object space (windows = bricks,
    walls = mortar), random per-window lighting. One quad per wall, no window geometry —
    detail is allocated by how many pixels it will occupy."""
    m, nt = M._new(name)
    if nt is None:
        return m
    L = nt.links
    b = nt.nodes["Principled BSDF"]
    tc = M._n(nt, "ShaderNodeTexCoord", (-1100, 0))
    geo = M._n(nt, "ShaderNodeNewGeometry", (-1100, -300))
    sep = M._n(nt, "ShaderNodeSeparateXYZ", (-900, -300)); L.new(geo.outputs["Normal"], sep.inputs[0])
    # project onto the wall plane: use (x+y, z) so both facade orientations get a grid
    sx = M._n(nt, "ShaderNodeSeparateXYZ", (-900, 0)); L.new(tc.outputs["Object"], sx.inputs[0])
    u = M._n(nt, "ShaderNodeMath", (-700, 50)); u.operation = 'ADD'
    L.new(sx.outputs["X"], u.inputs[0]); L.new(sx.outputs["Y"], u.inputs[1])
    cmb = M._n(nt, "ShaderNodeCombineXYZ", (-550, 0))
    L.new(u.outputs[0], cmb.inputs["X"]); L.new(sx.outputs["Z"], cmb.inputs["Y"])
    br = nt.nodes.new("ShaderNodeTexBrick"); br.location = (-350, 0)
    br.offset = 0.0; br.squash = 1.0
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = bay[0]
    br.inputs["Row Height"].default_value = bay[1]
    br.inputs["Mortar Size"].default_value = 0.9
    br.inputs["Mortar Smooth"].default_value = 0.0
    br.inputs["Bias"].default_value = 0.0
    br.inputs["Color1"].default_value = (0, 0, 0, 1); br.inputs["Color2"].default_value = (1, 1, 1, 1)
    br.inputs["Mortar"].default_value = (*wall, 1)
    L.new(cmb.outputs[0], br.inputs["Vector"])
    # mortar factor: 1 = wall, 0 = window
    is_win = M._n(nt, "ShaderNodeMath", (-150, -150)); is_win.operation = 'SUBTRACT'
    is_win.inputs[0].default_value = 1.0; L.new(br.outputs["Fac"], is_win.inputs[1])
    # brick colour (0..1 random per window) -> lit if below lit_fraction
    rnd = M._n(nt, "ShaderNodeRGBToBW", (-150, 50)); L.new(br.outputs["Color"], rnd.inputs[0])
    lt = M._n(nt, "ShaderNodeMath", (0, 50)); lt.operation = 'LESS_THAN'; lt.inputs[1].default_value = lit_fraction
    L.new(rnd.outputs[0], lt.inputs[0])
    # walls facing up/down get no windows
    vert = M._n(nt, "ShaderNodeMath", (-700, -300)); vert.operation = 'ABSOLUTE'; L.new(sep.outputs["Z"], vert.inputs[0])
    side = M._n(nt, "ShaderNodeMath", (-550, -300)); side.operation = 'LESS_THAN'; side.inputs[1].default_value = 0.5
    L.new(vert.outputs[0], side.inputs[0])
    win = M._n(nt, "ShaderNodeMath", (0, -150)); win.operation = 'MULTIPLY'
    L.new(is_win.outputs[0], win.inputs[0]); L.new(side.outputs[0], win.inputs[1])
    mixc = M._n(nt, "ShaderNodeMix", (200, 100)); mixc.data_type = 'RGBA'
    L.new(win.outputs[0], mixc.inputs["Factor"])
    mixc.inputs[6].default_value = (*wall, 1); mixc.inputs[7].default_value = (*window, 1)
    L.new(mixc.outputs[2], b.inputs["Base Color"])
    em = M._n(nt, "ShaderNodeMath", (200, -100)); em.operation = 'MULTIPLY'
    L.new(win.outputs[0], em.inputs[0]); L.new(lt.outputs[0], em.inputs[1])
    es = M._n(nt, "ShaderNodeMath", (350, -100)); es.operation = 'MULTIPLY'; es.inputs[1].default_value = lit_strength
    L.new(em.outputs[0], es.inputs[0])
    b.inputs["Emission Color"].default_value = (*lit, 1)
    L.new(es.outputs[0], b.inputs["Emission Strength"])
    rough = M._n(nt, "ShaderNodeMapRange", (350, 250))
    rough.inputs["To Min"].default_value = 0.9; rough.inputs["To Max"].default_value = 0.15
    L.new(win.outputs[0], rough.inputs["Value"]); L.new(rough.outputs[0], b.inputs["Roughness"])
    return m


def facade_building(name, center, w, d, h, rng, lod="near", floor_h=3.4, bay=3.2, c=None,
                    wall_tint=(0.36, 0.35, 0.33), lit_fraction=0.18, rooftop=True, setback=None):
    """Modular tower. lod='near': real window module (inset pane + sill) repeated per bay
    and floor on all four sides, floor bands, rooftop clutter. lod='far': one volume with
    the facade_grid material. setback=(height_frac, inset) adds an upper stage."""
    cx, cy, z0 = center
    mb = MB()
    stages = [(z0, z0 + h, w, d)]
    if setback:
        hf, ins = setback
        zs = z0 + h * hf
        stages = [(z0, zs, w, d), (zs, z0 + h, max(2.0, w - 2 * ins), max(2.0, d - 2 * ins))]
    for (za, zb, ww, dd) in stages:
        mb.box((cx, cy, (za + zb) / 2), (ww, dd, zb - za), mat=0)
        if lod != "near":
            continue
        floors = max(1, int((zb - za) // floor_h))
        for k in range(floors):
            zf = za + k * floor_h
            mb.box((cx, cy, zf + 0.05), (ww + 0.12, dd + 0.12, 0.22), mat=0)          # floor band
            for side in range(4):
                along = ww if side < 2 else dd
                nb = max(1, int(along // bay))
                for i in range(nb):
                    t = (i + 0.5) / nb - 0.5
                    pz = zf + floor_h * 0.55
                    pw, ph = along / nb * 0.62, floor_h * 0.55
                    if side == 0:   p, s = (cx + t * ww, cy - dd / 2 - 0.02, pz), (pw, 0.04, ph)
                    elif side == 1: p, s = (cx + t * ww, cy + dd / 2 + 0.02, pz), (pw, 0.04, ph)
                    elif side == 2: p, s = (cx - ww / 2 - 0.02, cy + t * dd, pz), (0.04, pw, ph)
                    else:           p, s = (cx + ww / 2 + 0.02, cy + t * dd, pz), (0.04, pw, ph)
                    mb.box(p, s, mat=1)                                                   # pane (island)
                    sill = (p[0], p[1], pz - ph / 2 - 0.06)
                    mb.box(sill, (s[0] + (0.12 if s[0] > 0.1 else 0.1), s[1] + (0.12 if s[1] > 0.1 else 0.1), 0.08), mat=0)
        # parapet
        for (px, py, sx, sy) in ((cx, cy - dd / 2, ww, 0.25), (cx, cy + dd / 2, ww, 0.25),
                                 (cx - ww / 2, cy, 0.25, dd), (cx + ww / 2, cy, 0.25, dd)):
            mb.box((px, py, zb + 0.5), (sx, sy, 1.0), mat=0)
    if rooftop and lod == "near":
        top = stages[-1]
        zb, ww, dd = top[1], top[2], top[3]
        for k in range(rng.randint(1, 4)):
            s = (rng.uniform(1.2, 3.0), rng.uniform(1.2, 2.5), rng.uniform(0.8, 2.2))
            mb.box((cx + rng.uniform(-ww / 3, ww / 3), cy + rng.uniform(-dd / 3, dd / 3), zb + s[2] / 2), s, mat=2)
    mats = [M.concrete(f"Facade_{wall_tint}", wall_tint, moss=0.15),
            M.window_glass(lit_fraction=lit_fraction), M.dark_metal("RoofUnits", (0.12, 0.12, 0.12), 0.5)]
    if lod != "near":
        mats = [facade_grid(f"FacadeGrid_{wall_tint}", wall=wall_tint, lit_fraction=lit_fraction)]
    o = mb.to_object(name, mats, c or col("City"), bevel=0.0)
    return o


def landmark_tower(name, base, height, rng, radius=9.0, stages=5, c=None, beacon=(1.0, 0.1, 0.05)):
    """A custom, recognisable silhouette — worth modelling yourself because the composition
    depends on its exact shape: tapered stages, ring platforms, a lattice spire, beacons."""
    bx, by, bz = base
    bm = bmesh.new()
    mi = []

    def cyl(r0, r1, z0, z1, seg=24, mat=0):
        ret = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r0, radius2=r1, depth=z1 - z0,
                                    matrix=Matrix.Translation((bx, by, (z0 + z1) / 2)))
        for f in {f for v in ret["verts"] for f in v.link_faces}:
            f.material_index = mat
    body_h = height * 0.72
    z = bz
    r = radius
    for s in range(stages):
        hseg = body_h / stages
        r_next = r * rng.uniform(0.72, 0.86)
        cyl(r, r_next, z, z + hseg, 32, 0)
        cyl(r_next * 1.25, r_next * 1.25, z + hseg - 0.6, z + hseg, 40, 1)          # ring platform
        z += hseg
        r = r_next
    # lattice spire: 4 legs + cross bracing
    top = bz + height
    legs = 4
    mats_spire = 1
    pts = []
    for k in range(legs):
        a = 2 * math.pi * k / legs + math.pi / 4
        pts.append((Vector((bx + math.cos(a) * r * 0.9, by + math.sin(a) * r * 0.9, z)),
                    Vector((bx + math.cos(a) * 0.15, by + math.sin(a) * 0.15, top))))

    def rod(a, b, rr=0.12, mat=1):
        d = b - a
        if d.length < 1e-4:
            return
        q = d.normalized().to_track_quat('Z', 'Y')
        ret = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=rr, radius2=rr, depth=d.length,
                                    matrix=Matrix.Translation((a + b) / 2) @ q.to_matrix().to_4x4())
        for f in {f for v in ret["verts"] for f in v.link_faces}:
            f.material_index = mat
    for (a, b) in pts:
        rod(a, b, 0.22)
    nlev = 9
    for i in range(nlev):
        t0, t1 = i / nlev, (i + 1) / nlev
        for k in range(legs):
            a0 = pts[k][0].lerp(pts[k][1], t0); b1 = pts[(k + 1) % legs][0].lerp(pts[(k + 1) % legs][1], t1)
            rod(a0, b1, 0.07)
            rod(a0, pts[(k + 1) % legs][0].lerp(pts[(k + 1) % legs][1], t0), 0.07)
    # beacons
    for t in (0.35, 0.7, 1.0):
        for k in range(legs):
            p = pts[k][0].lerp(pts[k][1], t)
            ret = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.35 + 0.15 * t, matrix=Matrix.Translation(p))
            for f in {f for v in ret["verts"] for f in v.link_faces}:
                f.material_index = 2
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in (M.concrete("LandmarkConcrete", (0.5, 0.5, 0.52), moss=0.05),
              M.dark_metal("LandmarkSteel", (0.18, 0.18, 0.19), 0.4),
              M.emissive("Beacon", beacon, 25.0, base=(0.5, 0.05, 0.02))):
        me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    (c or col("City")).objects.link(o)
    return o


def elevated_rail(name, a, b, height, width=7.0, pier_every=24.0, c=None):
    """Elevated railway deck + piers + rails from a to b (ground points)."""
    a, b = Vector(a), Vector(b)
    d = b - a; d.z = 0
    L = d.length; u = d.normalized(); side = Vector((-u.y, u.x, 0))
    yaw = math.atan2(u.y, u.x)
    mb = MB()
    mid = (a + b) / 2
    mb.box((mid.x, mid.y, a.z + height), (L, width, 1.2), (0, 0, yaw), mat=0)
    for s in (-1, 1):
        p = mid + side * s * (width / 2 - 0.2)
        mb.box((p.x, p.y, a.z + height + 0.95), (L, 0.25, 0.7), (0, 0, yaw), mat=0)        # parapets
        p = mid + side * s * 0.75
        mb.box((p.x, p.y, a.z + height + 0.68), (L, 0.12, 0.15), (0, 0, yaw), mat=1)       # rails
    n = max(1, int(L // pier_every))
    for i in range(n + 1):
        p = a + u * (L * i / n)
        mb.box((p.x, p.y, a.z + (height - 0.6) / 2), (2.2, 2.2, height - 0.6), (0, 0, yaw), mat=0)
    return mb.to_object(name, [M.concrete("RailConcrete", (0.42, 0.41, 0.4), moss=0.2),
                               M.dark_metal("RailSteel", (0.2, 0.2, 0.2), 0.35)], c or col("City"))


# ====================================================================== rooftop kit
def roof_slab(name, x0, x1, y0, y1, z=0.0, parapet=1.05, thick=0.35, open_side=None, c=None, depth=30.0):
    """Rooftop surface with a parapet wall; the building continues `depth` m below so
    it reads from oblique views. open_side in {'ymin','ymax','xmin','xmax',None}."""
    mb = MB()
    # walkable surface (roofing membrane) top is exactly z; the structure sits under it
    mb.box(((x0 + x1) / 2, (y0 + y1) / 2, z - 0.04 - depth / 2), (x1 - x0, y1 - y0, depth), mat=0)   # building
    mb.box(((x0 + x1) / 2, (y0 + y1) / 2, z - 0.02), (x1 - x0 - 0.5, y1 - y0 - 0.5, 0.04), mat=1)    # roofing
    t = thick
    walls = {"ymin": ((x0 + x1) / 2, y0 + t / 2, x1 - x0, t), "ymax": ((x0 + x1) / 2, y1 - t / 2, x1 - x0, t),
             "xmin": (x0 + t / 2, (y0 + y1) / 2, t, y1 - y0), "xmax": (x1 - t / 2, (y0 + y1) / 2, t, y1 - y0)}
    for k, (px, py, sx, sy) in walls.items():
        if k == open_side:
            continue
        mb.box((px, py, z + parapet / 2 - 0.02), (sx, sy, parapet + 0.04), mat=0)
        mb.box((px, py, z + parapet + 0.04), (sx + 0.08, sy + 0.08, 0.08), mat=0)            # coping
    return mb.to_object(name, [M.concrete("RoofConcrete", (0.46, 0.45, 0.43), moss=0.5), M.roofing()],
                        c or col("Rooftop"), bevel=0.01)


def hvac_unit(name, loc, size=(1.6, 1.1, 1.0), yaw=0.0, rng=None, c=None):
    """Rooftop condenser: cabinet, louvres, a fan shroud with grille, feet."""
    rng = rng or random.Random(1)
    sx, sy, sz = size
    mb = MB()
    x, y, z = loc
    R = Euler((0, 0, yaw)).to_matrix()
    P = lambda dx, dy, dz: tuple(Vector((x, y, z)) + R @ Vector((dx, dy, dz)))
    mb.box(P(0, 0, sz / 2 + 0.08), size, (0, 0, yaw), mat=0)
    for i in range(7):                                                          # louvres
        mb.box(P(0, -sy / 2 - 0.01, 0.2 + i * (sz - 0.3) / 7), (sx * 0.9, 0.03, 0.04), (0.5, 0, yaw), mat=1)
    for fx in (-sx / 4, sx / 4):
        mb.rod(P(fx, 0, sz + 0.08), P(fx, 0, sz + 0.3), r=min(sx, sy) * 0.22, mat=1, seg=20)    # fan shroud
        mb.box(P(fx, 0, sz + 0.31), (min(sx, sy) * 0.44, 0.02, 0.02), (0, 0, yaw), mat=1)
        mb.box(P(fx, 0, sz + 0.31), (0.02, min(sx, sy) * 0.44, 0.02), (0, 0, yaw), mat=1)
    for fx in (-sx / 2 + 0.1, sx / 2 - 0.1):
        for fy in (-sy / 2 + 0.1, sy / 2 - 0.1):
            mb.box(P(fx, fy, 0.04), (0.12, 0.12, 0.08), (0, 0, yaw), mat=1)
    return mb.to_object(name, [M.painted_metal("HVACPaint", paint=(0.55, 0.56, 0.54), rust=0.25, metal=0.4,
                                               rust_cols=((0.12, 0.07, 0.04), (0.3, 0.16, 0.08))),
                               M.dark_metal("HVACDark", (0.08, 0.08, 0.08), 0.45)], c or col("Rooftop"), bevel=0.01)


def water_tank(name, loc, radius=1.3, height=2.2, legs=1.8, c=None):
    """Classic rooftop water tank: drum, conical cap, four legs, cross braces, ladder."""
    x, y, z = loc
    mb = MB()
    bm = mb.bm
    ret = bmesh.ops.create_cone(bm, cap_ends=True, segments=28, radius1=radius, radius2=radius, depth=height,
                                matrix=Matrix.Translation((x, y, z + legs + height / 2)))
    for f in {f for v in ret["verts"] for f in v.link_faces}:
        f.material_index = 0
    ret = bmesh.ops.create_cone(bm, cap_ends=True, segments=28, radius1=radius * 1.05, radius2=0.05, depth=0.7,
                                matrix=Matrix.Translation((x, y, z + legs + height + 0.35)))
    for f in {f for v in ret["verts"] for f in v.link_faces}:
        f.material_index = 0
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        p = Vector((x + math.cos(a) * radius * 0.8, y + math.sin(a) * radius * 0.8, z))
        mb.rod(p, p + Vector((0, 0, legs + 0.1)), 0.07, mat=1)
        q = Vector((x + math.cos(a + math.pi / 2) * radius * 0.8, y + math.sin(a + math.pi / 2) * radius * 0.8, z))
        mb.rod(p + Vector((0, 0, 0.2)), q + Vector((0, 0, legs - 0.1)), 0.03, mat=1)
    lx, ly = x + radius + 0.05, y
    for s in (-0.22, 0.22):
        mb.rod((lx, ly + s, z), (lx, ly + s, z + legs + height), 0.025, mat=1)
    for i in range(int((legs + height) / 0.3)):
        mb.rod((lx, ly - 0.22, z + 0.3 * (i + 1)), (lx, ly + 0.22, z + 0.3 * (i + 1)), 0.018, mat=1)
    return mb.to_object(name, [M.painted_metal("TankPaint", paint=(0.42, 0.36, 0.3), rust=0.55, metal=0.3,
                                               rust_cols=((0.12, 0.06, 0.03), (0.32, 0.16, 0.07))),
                               M.dark_metal("TankSteel", (0.1, 0.1, 0.1), 0.5)], c or col("Rooftop"))


def door_hut(name, loc, size=(2.6, 2.2, 2.7), yaw=0.0, lamp=True, c=None):
    """Stair-access hut with a door and a small lamp (a warm accent the eye can find)."""
    x, y, z = loc
    sx, sy, sz = size
    R = Euler((0, 0, yaw)).to_matrix()
    P = lambda dx, dy, dz: tuple(Vector((x, y, z)) + R @ Vector((dx, dy, dz)))
    mb = MB()
    mb.box(P(0, 0, sz / 2), size, (0, 0, yaw), mat=0)
    mb.box(P(0, 0, sz + 0.06), (sx + 0.3, sy + 0.3, 0.12), (0, 0, yaw), mat=0)
    mb.box(P(0.3, -sy / 2 - 0.02, 1.05), (0.95, 0.06, 2.1), (0, 0, yaw), mat=1)               # door
    if lamp:
        mb.box(P(0.3, -sy / 2 - 0.12, 2.35), (0.3, 0.18, 0.12), (0, 0, yaw), mat=2)
    return mb.to_object(name, [M.concrete("HutConcrete", (0.5, 0.49, 0.46), moss=0.3),
                               M.painted_metal("DoorPaint", paint=(0.18, 0.28, 0.3), rust=0.4, metal=0.3,
                                               rust_cols=((0.1, 0.06, 0.03), (0.28, 0.14, 0.07))),
                               M.emissive("HutLamp", (1.0, 0.75, 0.45), 30.0, base=(1, 0.9, 0.8))],
                        c or col("Rooftop"), bevel=0.01)


def antenna_mast(name, base, height=6.0, c=None):
    x, y, z = base
    mb = MB()
    mb.rod((x, y, z), (x, y, z + height), 0.05, mat=0, seg=8)
    for i, h in enumerate((0.55, 0.72, 0.86)):
        L = 1.2 - 0.3 * i
        mb.rod((x - L / 2, y, z + height * h), (x + L / 2, y, z + height * h), 0.02, mat=0)
    for k in range(3):
        a = 2 * math.pi * k / 3
        mb.rod((x, y, z + height * 0.6), (x + math.cos(a) * height * 0.28, y + math.sin(a) * height * 0.28, z), 0.008, mat=0)
    return mb.to_object(name, [M.dark_metal("MastSteel", (0.12, 0.12, 0.12), 0.4)], c or col("Rooftop"))


def utility_pole(name, base, height=9.0, c=None):
    """Pole + two crossarms + insulators. Returns (object, [insulator tip points])."""
    x, y, z = base
    mb = MB()
    mb.rod((x, y, z), (x, y, z + height), 0.14, mat=0, seg=10)
    tips = []
    for h, L in ((0.93, 2.2), (0.82, 1.6)):
        zz = z + height * h
        mb.box((x, y, zz), (L, 0.12, 0.12), mat=0)
        for s in (-1, 1):
            p = Vector((x + s * L * 0.42, y, zz + 0.06))
            mb.rod(p, p + Vector((0, 0, 0.18)), 0.04, mat=1)
            tips.append(p + Vector((0, 0, 0.18)))
    return mb.to_object(name, [M.flat("PoleWood", (0.16, 0.12, 0.09), 0.8), M.flat("Insulator", (0.6, 0.62, 0.6), 0.3)],
                        c or col("Rooftop")), tips


def railing(name, pts, height=1.05, post_every=1.5, c=None):
    """Posts + top and mid rail along a polyline (points at floor level)."""
    pts = [Vector(p) for p in pts]
    mb = MB()
    for a, b in zip(pts, pts[1:]):
        L = (b - a).length
        n = max(1, int(L // post_every))
        for i in range(n + 1):
            p = a.lerp(b, i / n)
            mb.rod(p, p + Vector((0, 0, height)), 0.025, mat=0, seg=8)
        for h in (height, height * 0.5):
            mb.rod(a + Vector((0, 0, h)), b + Vector((0, 0, h)), 0.022, mat=0, seg=8)
    return mb.to_object(name, [M.painted_metal("RailPaint", paint=(0.5, 0.18, 0.12), rust=0.5, metal=0.4,
                                               rust_cols=((0.12, 0.06, 0.03), (0.3, 0.14, 0.07)))],
                        c or col("Rooftop"))


def pipe_run(name, pts, radius=0.09, support_every=2.0, floor_z=None, c=None):
    """Pipe along a polyline with elbow joints and floor supports — give it a plausible
    structural logic: it should start and end at something (a unit, a wall)."""
    pts = [Vector(p) for p in pts]
    mb = MB()
    bm = mb.bm
    for a, b in zip(pts, pts[1:]):
        mb.rod(a, b, radius, mat=0, seg=14)
        L = (b - a).length
        if floor_z is not None:
            for i in range(1, max(1, int(L // support_every)) + 1):
                p = a.lerp(b, i / (int(L // support_every) + 1))
                if p.z - floor_z > radius * 1.5:
                    mb.rod((p.x, p.y, floor_z), (p.x, p.y, p.z - radius), 0.03, mat=1)
                    mb.box((p.x, p.y, floor_z + 0.02), (0.25, 0.25, 0.04), mat=1)
    for p in pts[1:-1]:
        ret = bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=radius * 1.15, matrix=Matrix.Translation(p))
        for f in {f for v in ret["verts"] for f in v.link_faces}:
            f.material_index = 0
    return mb.to_object(name, [M.painted_metal("PipePaint", paint=(0.62, 0.55, 0.3), rust=0.45, metal=0.4,
                                               rust_cols=((0.12, 0.06, 0.03), (0.3, 0.15, 0.07))),
                               M.dark_metal("PipeSupport", (0.1, 0.1, 0.1), 0.5)], c or col("Rooftop"))


def catenary(a, b, sag=0.6, n=12):
    """Points of a sagging wire between a and b (parabolic approximation)."""
    a, b = Vector(a), Vector(b)
    return [a.lerp(b, i / n) - Vector((0, 0, 4 * sag * (i / n) * (1 - i / n))) for i in range(n + 1)]
