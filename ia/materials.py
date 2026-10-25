"""materials.py — a small, coherent material family.

Assets from different sources clash in saturation, roughness, texture scale and
contrast. Establish a family (related concretes, painted metal, dark steel, glass, a few
accents) and adapt everything to it — `unify()` does that for imported materials.

Procedural (no texture files): concrete, asphalt, roofing, painted_metal, dark_metal,
glass, window_glass (per-window lit/unlit), emissive, flat, grass, arc/halo FX.
Image-based: image_pbr() wires base/roughness/metallic/normal/height maps with the
correct colour spaces (only base colour is sRGB; the rest are Non-Color data).
"""
import os
import bpy


def _new(name):
    m = bpy.data.materials.get(name)
    if m:
        return m, None
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree


def _n(nt, kind, loc=(0, 0), **inputs):
    n = nt.nodes.new(kind)
    n.location = loc
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n


def _ramp(nt, loc, stops):
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.location = loc
    cr = r.color_ramp
    while len(cr.elements) > 2:
        cr.elements.remove(cr.elements[-1])
    for i, (pos, col) in enumerate(stops):
        e = cr.elements[i] if i < 2 else cr.elements.new(pos)
        e.position = pos
        e.color = col if len(col) == 4 else (*col, 1)
    return r


def painted_metal(name="PaintedMetal", paint=(0.50, 0.40, 0.27), rust=0.35, soot=0.0, metal=0.0,
                  rust_cols=((0.20, 0.075, 0.03), (0.42, 0.20, 0.08)), rough_rng=(0.5, 0.9), chips=0.0):
    """Tan machine paint with rust blotches, cavity grime and worn bare-metal edges.
    Per-object variation via Object Info > Random."""
    m, nt = _new(name)
    if nt is None:
        return m
    L = nt.links
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.location = (900, 0)
    tc = _n(nt, "ShaderNodeTexCoord", (-1400, 0))
    oi = _n(nt, "ShaderNodeObjectInfo", (-1400, -300))
    add = _n(nt, "ShaderNodeVectorMath", (-1200, 0)); add.operation = 'ADD'
    sc = _n(nt, "ShaderNodeVectorMath", (-1200, -250)); sc.operation = 'SCALE'
    L.new(oi.outputs["Random"], sc.inputs["Scale"])
    sc.inputs[0].default_value = (37.0, 11.0, 23.0)
    L.new(tc.outputs["Object"], add.inputs[0]); L.new(sc.outputs[0], add.inputs[1])
    # rust blotches
    n1 = _n(nt, "ShaderNodeTexNoise", (-1000, 200), Scale=4.5, Detail=10.0, Roughness=0.62)
    L.new(add.outputs[0], n1.inputs["Vector"])
    r1 = _ramp(nt, (-800, 200), [(0.5 - rust * 0.22, (0, 0, 0)), (0.62 - rust * 0.22, (1, 1, 1))])
    L.new(n1.outputs["Fac"], r1.inputs["Fac"])
    # streaks (stretched noise along Z = rain-run rust)
    mp = _n(nt, "ShaderNodeMapping", (-1000, -50)); mp.inputs["Scale"].default_value = (9, 9, 1.2)
    L.new(add.outputs[0], mp.inputs["Vector"])
    n2 = _n(nt, "ShaderNodeTexNoise", (-800, -50), Scale=3.0, Detail=6.0)
    L.new(mp.outputs[0], n2.inputs["Vector"])
    r2 = _ramp(nt, (-600, -50), [(0.55, (0, 0, 0)), (0.75, (1, 1, 1))])
    L.new(n2.outputs["Fac"], r2.inputs["Fac"])
    rmask = _n(nt, "ShaderNodeMath", (-400, 150)); rmask.operation = 'MAXIMUM'
    L.new(r1.outputs["Color"], rmask.inputs[0]); L.new(r2.outputs["Color"], rmask.inputs[1])
    # edge wear: 1 - dot(N, bevelN) is resolution independent (pointiness is not on
    # low-poly primitives), broken up by noise so wear is patchy
    geo = _n(nt, "ShaderNodeNewGeometry", (-1200, -350))
    bev = nt.nodes.new("ShaderNodeBevel"); bev.location = (-1200, -500)
    bev.inputs["Radius"].default_value = 0.012
    dot = _n(nt, "ShaderNodeVectorMath", (-1000, -400)); dot.operation = 'DOT_PRODUCT'
    L.new(geo.outputs["Normal"], dot.inputs[0]); L.new(bev.outputs["Normal"], dot.inputs[1])
    inv = _n(nt, "ShaderNodeMath", (-850, -400)); inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    L.new(dot.outputs["Value"], inv.inputs[1])
    nw = _n(nt, "ShaderNodeTexNoise", (-1000, -250), Scale=14.0, Detail=6.0)
    L.new(add.outputs[0], nw.inputs["Vector"])
    ew = _n(nt, "ShaderNodeMath", (-700, -400)); ew.operation = 'MULTIPLY'
    L.new(inv.outputs[0], ew.inputs[0]); L.new(nw.outputs["Fac"], ew.inputs[1])
    r3 = _ramp(nt, (-550, -350), [(0.012, (0, 0, 0)), (0.05, (1, 1, 1))])
    L.new(ew.outputs[0], r3.inputs["Fac"])
    # paint chips: small speckles of bare metal across the surface
    nch = _n(nt, "ShaderNodeTexNoise", (-1000, -700), Scale=55.0, Detail=3.0, Roughness=0.55)
    L.new(add.outputs[0], nch.inputs["Vector"])
    rch = _ramp(nt, (-800, -700), [(0.74 - 0.05 * chips, (0, 0, 0)), (0.755 - 0.05 * chips, (1, 1, 1))])
    L.new(nch.outputs["Fac"], rch.inputs["Fac"])

    # cavity grime from AO
    ao = _n(nt, "ShaderNodeAmbientOcclusion", (-1000, -600)); ao.inputs["Distance"].default_value = 0.06
    r4 = _ramp(nt, (-800, -600), [(0.35, (1, 1, 1)), (0.9, (0, 0, 0))])
    L.new(ao.outputs["AO"], r4.inputs["Fac"])
    # colors
    paint_rgb = _n(nt, "ShaderNodeRGB", (-600, 450)); paint_rgb.outputs[0].default_value = (*paint, 1)
    hue = _n(nt, "ShaderNodeHueSaturation", (-400, 450))
    L.new(paint_rgb.outputs[0], hue.inputs["Color"])
    vr = _n(nt, "ShaderNodeMapRange", (-600, 650)); vr.inputs["To Min"].default_value = 0.85
    vr.inputs["To Max"].default_value = 1.12
    L.new(oi.outputs["Random"], vr.inputs["Value"]); L.new(vr.outputs[0], hue.inputs["Value"])
    rust_rgb = _ramp(nt, (-400, 300), [(0.0, rust_cols[0]), (1.0, rust_cols[1])])
    L.new(n2.outputs["Fac"], rust_rgb.inputs["Fac"])
    mix1 = _n(nt, "ShaderNodeMix", (-150, 300)); mix1.data_type = 'RGBA'
    L.new(rmask.outputs[0], mix1.inputs["Factor"])
    L.new(hue.outputs[0], mix1.inputs[6]); L.new(rust_rgb.outputs["Color"], mix1.inputs[7])
    grime = _n(nt, "ShaderNodeMix", (100, 300)); grime.data_type = 'RGBA'
    gf = _n(nt, "ShaderNodeMath", (-150, -600)); gf.operation = 'MULTIPLY'
    gf.inputs[1].default_value = 0.75 + soot * 0.25
    L.new(r4.outputs["Color"], gf.inputs[0]); L.new(gf.outputs[0], grime.inputs["Factor"])
    L.new(mix1.outputs[2], grime.inputs[6])
    grime.inputs[7].default_value = (0.04, 0.03, 0.022, 1)
    soot_mix = _n(nt, "ShaderNodeMix", (300, 300)); soot_mix.data_type = 'RGBA'
    soot_mix.inputs["Factor"].default_value = soot
    L.new(grime.outputs[2], soot_mix.inputs[6]); soot_mix.inputs[7].default_value = (0.03, 0.028, 0.026, 1)
    edge = _n(nt, "ShaderNodeMix", (520, 300)); edge.data_type = 'RGBA'
    ef = _n(nt, "ShaderNodeMath", (300, -350)); ef.operation = 'MULTIPLY'
    ef.inputs[1].default_value = 0.8 * (1 - soot)
    L.new(r3.outputs["Color"], ef.inputs[0]); L.new(ef.outputs[0], edge.inputs["Factor"])
    L.new(soot_mix.outputs[2], edge.inputs[6]); edge.inputs[7].default_value = (0.52, 0.49, 0.45, 1)
    # chips reveal dark pitted rust (as on the reference model), not polished metal
    chf = _n(nt, "ShaderNodeMath", (650, 450)); chf.operation = 'MULTIPLY'; chf.inputs[1].default_value = chips
    L.new(rch.outputs["Color"], chf.inputs[0])
    chm = _n(nt, "ShaderNodeMix", (760, 300)); chm.data_type = 'RGBA'
    L.new(chf.outputs[0], chm.inputs["Factor"])
    L.new(edge.outputs[2], chm.inputs[6]); chm.inputs[7].default_value = (0.035, 0.024, 0.017, 1)
    L.new(chm.outputs[2], bsdf.inputs["Base Color"])
    # roughness / metallic
    rough = _n(nt, "ShaderNodeMapRange", (520, 0))
    rough.inputs["To Min"].default_value = rough_rng[0]; rough.inputs["To Max"].default_value = rough_rng[1]
    L.new(rmask.outputs[0], rough.inputs["Value"]); L.new(rough.outputs[0], bsdf.inputs["Roughness"])
    # painted steel: base metallic where not rusted, bare metal at worn edges
    nm_ = _n(nt, "ShaderNodeMath", (520, -150)); nm_.operation = 'MULTIPLY_ADD'
    nm_.inputs[1].default_value = -metal; nm_.inputs[2].default_value = metal
    L.new(rmask.outputs[0], nm_.inputs[0])
    mx_ = _n(nt, "ShaderNodeMath", (700, -150)); mx_.operation = 'MAXIMUM'
    L.new(nm_.outputs[0], mx_.inputs[0]); L.new(ef.outputs[0], mx_.inputs[1])
    L.new(mx_.outputs[0], bsdf.inputs["Metallic"])
    # bump (pitting + rust relief)
    n3 = _n(nt, "ShaderNodeTexNoise", (300, -800), Scale=60.0, Detail=4.0)
    L.new(add.outputs[0], n3.inputs["Vector"])
    bsum = _n(nt, "ShaderNodeMath", (520, -700)); bsum.operation = 'ADD'
    L.new(n3.outputs["Fac"], bsum.inputs[0]); L.new(rmask.outputs[0], bsum.inputs[1])
    bump = _n(nt, "ShaderNodeBump", (700, -500)); bump.inputs["Strength"].default_value = 0.12
    bump.inputs["Distance"].default_value = 0.004
    L.new(bsum.outputs[0], bump.inputs["Height"]); L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def dark_metal(name="DarkSteel", col=(0.055, 0.05, 0.045), rough=0.45):
    m, nt = _new(name)
    if nt is None:
        return m
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Metallic"].default_value = 0.85
    b.inputs["Roughness"].default_value = rough
    return m


def emissive(name, col, strength, base=(0.02, 0.02, 0.02)):
    m, nt = _new(name)
    if nt is None:
        return m
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Emission Color"].default_value = (*col, 1)
    b.inputs["Emission Strength"].default_value = strength
    b.inputs["Roughness"].default_value = 0.2
    return m


def flat(name, col, rough=0.6, metal=0.0):
    m, nt = _new(name)
    if nt is None:
        return m
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def burnt_interior(name="Burnt"):
    """Charred interior for boolean wounds: near-black with ember-orange speckle."""
    m, nt = _new(name)
    if nt is None:
        return m
    L = nt.links
    b = nt.nodes["Principled BSDF"]
    n = _n(nt, "ShaderNodeTexNoise", (-600, 0), Scale=25.0, Detail=8.0)
    r = _ramp(nt, (-400, 0), [(0.45, (0.012, 0.010, 0.009)), (0.75, (0.10, 0.05, 0.025))])
    L.new(n.outputs["Fac"], r.inputs["Fac"])
    L.new(r.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.9
    b.inputs["Metallic"].default_value = 0.4
    return m


def concrete(name="Concrete", tint=(0.44, 0.42, 0.39), moss=0.6, dark=0.0):
    m, nt = _new(name)
    if nt is None:
        return m
    L = nt.links; n = _n; ramp = _ramp
    b = nt.nodes["Principled BSDF"]; b.location = (900, 0)
    tc = n(nt, "ShaderNodeTexCoord", (-1500, 0))
    oi = n(nt, "ShaderNodeObjectInfo", (-1500, -300))
    off = n(nt, "ShaderNodeVectorMath", (-1300, -200)); off.operation = 'SCALE'
    off.inputs[0].default_value = (13.0, 7.0, 3.0)
    L.new(oi.outputs["Random"], off.inputs["Scale"])
    co = n(nt, "ShaderNodeVectorMath", (-1150, 0)); co.operation = 'ADD'
    L.new(tc.outputs["Object"], co.inputs[0]); L.new(off.outputs[0], co.inputs[1])
    big = n(nt, "ShaderNodeTexNoise", (-950, 300), Scale=0.35, Detail=6.0, Roughness=0.6)
    L.new(co.outputs[0], big.inputs["Vector"])
    fine = n(nt, "ShaderNodeTexNoise", (-950, 50), Scale=6.0, Detail=10.0, Roughness=0.7)
    L.new(co.outputs[0], fine.inputs["Vector"])
    mix = n(nt, "ShaderNodeMath", (-750, 200)); mix.operation = 'MULTIPLY_ADD'
    L.new(big.outputs["Fac"], mix.inputs[0]); mix.inputs[1].default_value = 0.7
    L.new(fine.outputs["Fac"], mix.inputs[2])
    base = ramp(nt, (-550, 250), [(0.55, tuple(c * (0.55 - dark * 0.3) for c in tint)),
                                  (1.05, tint)])
    L.new(mix.outputs[0], base.inputs["Fac"])
    # vertical grime streaks
    mp = n(nt, "ShaderNodeMapping", (-950, -250)); mp.inputs["Scale"].default_value = (3.5, 3.5, 0.25)
    L.new(co.outputs[0], mp.inputs["Vector"])
    st = n(nt, "ShaderNodeTexNoise", (-750, -250), Scale=2.5, Detail=4.0)
    L.new(mp.outputs[0], st.inputs["Vector"])
    stm = ramp(nt, (-550, -250), [(0.5, (0, 0, 0)), (0.72, (1, 1, 1))])
    L.new(st.outputs["Fac"], stm.inputs["Fac"])
    g1 = n(nt, "ShaderNodeMix", (-300, 200)); g1.data_type = 'RGBA'
    L.new(stm.outputs["Color"], g1.inputs["Factor"])
    L.new(base.outputs["Color"], g1.inputs[6]); g1.inputs[7].default_value = (0.11, 0.10, 0.09, 1)
    # cavity AO
    ao = n(nt, "ShaderNodeAmbientOcclusion", (-750, -500)); ao.inputs["Distance"].default_value = 0.5
    aor = ramp(nt, (-550, -500), [(0.2, (0.35, 0.35, 0.35)), (0.85, (1, 1, 1))])
    L.new(ao.outputs["AO"], aor.inputs["Fac"])
    g2 = n(nt, "ShaderNodeMix", (-80, 200)); g2.data_type = 'RGBA'; g2.blend_type = 'MULTIPLY'
    g2.inputs["Factor"].default_value = 1.0
    L.new(g1.outputs[2], g2.inputs[6]); L.new(aor.outputs["Color"], g2.inputs[7])
    # moss on up-facing surfaces, broken by noise
    geo = n(nt, "ShaderNodeNewGeometry", (-950, -750))
    sep = n(nt, "ShaderNodeSeparateXYZ", (-750, -750))
    L.new(geo.outputs["Normal"], sep.inputs[0])
    upm = ramp(nt, (-550, -750), [(0.55, (0, 0, 0)), (0.9, (1, 1, 1))])
    L.new(sep.outputs["Z"], upm.inputs["Fac"])
    mn = n(nt, "ShaderNodeTexNoise", (-750, -950), Scale=1.6, Detail=8.0, Roughness=0.65)
    L.new(co.outputs[0], mn.inputs["Vector"])
    mnr = ramp(nt, (-550, -950), [(0.52 - moss * 0.12, (0, 0, 0)), (0.6 - moss * 0.12, (1, 1, 1))])
    L.new(mn.outputs["Fac"], mnr.inputs["Fac"])
    mm = n(nt, "ShaderNodeMath", (-300, -800)); mm.operation = 'MULTIPLY'
    L.new(upm.outputs["Color"], mm.inputs[0]); L.new(mnr.outputs["Color"], mm.inputs[1])
    mcol = ramp(nt, (-300, -1000), [(0.3, (0.05, 0.075, 0.02)), (0.8, (0.16, 0.19, 0.06))])
    L.new(fine.outputs["Fac"], mcol.inputs["Fac"])
    g3 = n(nt, "ShaderNodeMix", (150, 200)); g3.data_type = 'RGBA'
    L.new(mm.outputs[0], g3.inputs["Factor"])
    L.new(g2.outputs[2], g3.inputs[6]); L.new(mcol.outputs["Color"], g3.inputs[7])
    L.new(g3.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.92
    # bump
    bn = n(nt, "ShaderNodeTexNoise", (300, -500), Scale=24.0, Detail=6.0)
    L.new(co.outputs[0], bn.inputs["Vector"])
    bs = n(nt, "ShaderNodeMath", (500, -500)); bs.operation = 'ADD'
    L.new(bn.outputs["Fac"], bs.inputs[0]); L.new(mm.outputs[0], bs.inputs[1])
    bump = n(nt, "ShaderNodeBump", (700, -400)); bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.02
    L.new(bs.outputs[0], bump.inputs["Height"]); L.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def asphalt(name="Asphalt"):
    m, nt = _new(name)
    if nt is None:
        return m
    L = nt.links; n = _n; ramp = _ramp
    b = nt.nodes["Principled BSDF"]; b.location = (900, 0)
    tc = n(nt, "ShaderNodeTexCoord", (-1400, 0))
    dust = n(nt, "ShaderNodeTexNoise", (-1100, 300), Scale=0.18, Detail=8.0, Roughness=0.62)
    L.new(tc.outputs["Object"], dust.inputs["Vector"])
    fine = n(nt, "ShaderNodeTexNoise", (-1100, 50), Scale=9.0, Detail=12.0, Roughness=0.75)
    L.new(tc.outputs["Object"], fine.inputs["Vector"])
    dr = ramp(nt, (-850, 300), [(0.42, (0.075, 0.072, 0.07)), (0.62, (0.30, 0.28, 0.25))])
    L.new(dust.outputs["Fac"], dr.inputs["Fac"])
    fm = n(nt, "ShaderNodeMix", (-600, 250)); fm.data_type = 'RGBA'; fm.blend_type = 'OVERLAY'
    fm.inputs["Factor"].default_value = 0.5
    L.new(dr.outputs["Color"], fm.inputs[6]); L.new(fine.outputs["Color"], fm.inputs[7])
    # cracks: voronoi distance-to-edge
    vor = nt.nodes.new("ShaderNodeTexVoronoi"); vor.location = (-1100, -250)
    vor.feature = 'DISTANCE_TO_EDGE'; vor.inputs["Scale"].default_value = 0.55
    wn = n(nt, "ShaderNodeTexNoise", (-1300, -250), Scale=1.5, Detail=4.0)
    L.new(tc.outputs["Object"], wn.inputs["Vector"])
    warp = n(nt, "ShaderNodeVectorMath", (-1200, -400)); warp.operation = 'MULTIPLY_ADD'
    L.new(wn.outputs["Color"], warp.inputs[0]); warp.inputs[1].default_value = (0.6, 0.6, 0.6)
    L.new(tc.outputs["Object"], warp.inputs[2]); L.new(warp.outputs[0], vor.inputs["Vector"])
    cr = ramp(nt, (-850, -250), [(0.0, (1, 1, 1)), (0.035, (0, 0, 0))])
    L.new(vor.outputs["Distance"], cr.inputs["Fac"])
    c1 = n(nt, "ShaderNodeMix", (-350, 250)); c1.data_type = 'RGBA'
    L.new(cr.outputs["Color"], c1.inputs["Factor"])
    L.new(fm.outputs[2], c1.inputs[6]); c1.inputs[7].default_value = (0.02, 0.022, 0.012, 1)
    # puddles: low areas of a broad noise -> dark + glossy
    pn = n(nt, "ShaderNodeTexNoise", (-1100, -650), Scale=0.25, Detail=3.0)
    L.new(tc.outputs["Object"], pn.inputs["Vector"])
    pr = ramp(nt, (-850, -650), [(0.30, (1, 1, 1)), (0.34, (0, 0, 0))])
    L.new(pn.outputs["Fac"], pr.inputs["Fac"])
    c2 = n(nt, "ShaderNodeMix", (-100, 250)); c2.data_type = 'RGBA'
    L.new(pr.outputs["Color"], c2.inputs["Factor"])
    L.new(c1.outputs[2], c2.inputs[6]); c2.inputs[7].default_value = (0.02, 0.02, 0.022, 1)
    L.new(c2.outputs[2], b.inputs["Base Color"])
    rr = n(nt, "ShaderNodeMapRange", (300, -100))
    rr.inputs["From Min"].default_value = 0; rr.inputs["From Max"].default_value = 1
    rr.inputs["To Min"].default_value = 0.9; rr.inputs["To Max"].default_value = 0.04
    L.new(pr.outputs["Color"], rr.inputs["Value"]); L.new(rr.outputs[0], b.inputs["Roughness"])
    bs = n(nt, "ShaderNodeMath", (300, -400)); bs.operation = 'SUBTRACT'
    L.new(fine.outputs["Fac"], bs.inputs[0]); L.new(cr.outputs["Color"], bs.inputs[1])
    bm_ = n(nt, "ShaderNodeMath", (450, -400)); bm_.operation = 'MULTIPLY'
    bm_.inputs[1].default_value = 1.0
    inv = n(nt, "ShaderNodeMath", (300, -600)); inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0; L.new(pr.outputs["Color"], inv.inputs[1])
    L.new(bs.outputs[0], bm_.inputs[0]); L.new(inv.outputs[0], bm_.inputs[1])
    bump = n(nt, "ShaderNodeBump", (650, -400)); bump.inputs["Strength"].default_value = 0.45
    bump.inputs["Distance"].default_value = 0.01
    L.new(bm_.outputs[0], bump.inputs["Height"]); L.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def grass_mat():
    m, nt = _new("Grass")
    if nt is None:
        return m
    L = nt.links
    b = nt.nodes["Principled BSDF"]
    oi = _n(nt, "ShaderNodeObjectInfo", (-700, 0))
    r = _ramp(nt, (-450, 0), [(0.0, (0.06, 0.09, 0.02)), (0.6, (0.17, 0.2, 0.05)), (1.0, (0.33, 0.29, 0.1))])
    L.new(oi.outputs["Random"], r.inputs["Fac"])
    L.new(r.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.6
    b.inputs["Subsurface Weight"].default_value = 0.0
    try:
        b.inputs["Transmission Weight"].default_value = 0.15
    except Exception:
        pass
    return m


def arc_material(name="ArcBlue", col=(0.22, 0.58, 1.0), strength=16.0):
    return emissive(name, col, strength, base=(0.1, 0.3, 0.6))


def halo_material(name="ArcHalo", col=(0.12, 0.42, 1.0), strength=3.0, opacity=0.35):
    """Soft translucent corona around an arc: transparent + emission mix."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*col, 1); em.inputs["Strength"].default_value = strength
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mx = nt.nodes.new("ShaderNodeMixShader"); mx.inputs[0].default_value = opacity
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    return m


def glass(name="Glass", tint=(0.8, 0.85, 0.9), rough=0.05):
    m, nt = _new(name)
    if nt is None:
        return m
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*tint, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Transmission Weight"].default_value = 1.0
    return m


def window_glass(name="WindowGlass", lit_fraction=0.18, lit_color=(1.0, 0.72, 0.42), lit_strength=3.0,
                 dark=(0.03, 0.035, 0.04)):
    """Window panes: each pane (mesh island) is randomly lit or dark via
    Geometry > Random Per Island, so one material serves a whole facade."""
    m, nt = _new(name)
    if nt is None:
        return m
    L = nt.links
    b = nt.nodes["Principled BSDF"]
    geo = _n(nt, "ShaderNodeNewGeometry", (-900, 0))
    oi = _n(nt, "ShaderNodeObjectInfo", (-900, -250))
    add = _n(nt, "ShaderNodeMath", (-700, 0)); add.operation = 'ADD'
    L.new(geo.outputs["Random Per Island"], add.inputs[0]); L.new(oi.outputs["Random"], add.inputs[1])
    frac = _n(nt, "ShaderNodeMath", (-550, 0)); frac.operation = 'FRACT'
    L.new(add.outputs[0], frac.inputs[0])
    lit = _n(nt, "ShaderNodeMath", (-400, 0)); lit.operation = 'LESS_THAN'
    lit.inputs[1].default_value = lit_fraction
    L.new(frac.outputs[0], lit.inputs[0])
    var = _n(nt, "ShaderNodeMapRange", (-400, -250))
    var.inputs["To Min"].default_value = 0.5; var.inputs["To Max"].default_value = 1.3
    L.new(frac.outputs[0], var.inputs["Value"])
    mul = _n(nt, "ShaderNodeMath", (-200, -100)); mul.operation = 'MULTIPLY'
    L.new(lit.outputs[0], mul.inputs[0]); L.new(var.outputs[0], mul.inputs[1])
    es = _n(nt, "ShaderNodeMath", (0, -100)); es.operation = 'MULTIPLY'; es.inputs[1].default_value = lit_strength
    L.new(mul.outputs[0], es.inputs[0])
    b.inputs["Base Color"].default_value = (*dark, 1)
    b.inputs["Roughness"].default_value = 0.08
    b.inputs["Metallic"].default_value = 0.6
    b.inputs["Emission Color"].default_value = (*lit_color, 1)
    L.new(es.outputs[0], b.inputs["Emission Strength"])
    return m


def roofing(name="Roofing", tint=(0.11, 0.105, 0.1)):
    """Tar/membrane roof: dark, rough, with patchy repairs and puddle gloss."""
    m, nt = _new(name)
    if nt is None:
        return m
    L = nt.links
    b = nt.nodes["Principled BSDF"]
    tc = _n(nt, "ShaderNodeTexCoord", (-900, 0))
    pn = _n(nt, "ShaderNodeTexNoise", (-700, 200), Scale=0.6, Detail=6.0)
    L.new(tc.outputs["Object"], pn.inputs["Vector"])
    r = _ramp(nt, (-500, 200), [(0.4, tuple(c * 0.7 for c in tint)), (0.7, tuple(min(1, c * 1.8) for c in tint))])
    L.new(pn.outputs["Fac"], r.inputs["Fac"]); L.new(r.outputs["Color"], b.inputs["Base Color"])
    wet = _n(nt, "ShaderNodeTexNoise", (-700, -150), Scale=0.35, Detail=2.0)
    L.new(tc.outputs["Object"], wet.inputs["Vector"])
    rr = _ramp(nt, (-500, -150), [(0.3, (0.08, 0.08, 0.08)), (0.36, (0.85, 0.85, 0.85))])
    L.new(wet.outputs["Fac"], rr.inputs["Fac"]); L.new(rr.outputs["Color"], b.inputs["Roughness"])
    fn = _n(nt, "ShaderNodeTexNoise", (-700, -400), Scale=40.0, Detail=4.0)
    L.new(tc.outputs["Object"], fn.inputs["Vector"])
    bump = _n(nt, "ShaderNodeBump", (-300, -400)); bump.inputs["Strength"].default_value = 0.2
    L.new(fn.outputs["Fac"], bump.inputs["Height"]); L.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def image_pbr(name, maps, scale=1.0, normal_strength=1.0, bump_strength=0.3):
    """maps: {"base": path, "roughness": path, "metallic": path, "normal": path, "height": path}.
    Base colour is sRGB; every other map is Non-Color data (a normal-map PNG is still data).
    Object-space box projection keeps texel size consistent across objects (scale = 1/m)."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; L = nt.links
    b = nt.nodes["Principled BSDF"]
    tc = _n(nt, "ShaderNodeTexCoord", (-1200, 0))
    mp = _n(nt, "ShaderNodeMapping", (-1000, 0)); mp.inputs["Scale"].default_value = (scale, scale, scale)
    L.new(tc.outputs["Object"], mp.inputs["Vector"])

    def tex(path, data, y):
        t = nt.nodes.new("ShaderNodeTexImage"); t.location = (-700, y)
        t.image = bpy.data.images.load(path, check_existing=True)
        t.image.colorspace_settings.name = 'Non-Color' if data else 'sRGB'
        t.projection = 'BOX'; t.projection_blend = 0.2
        L.new(mp.outputs["Vector"], t.inputs["Vector"])
        return t
    y = 300
    if maps.get("base"):
        L.new(tex(maps["base"], False, y).outputs["Color"], b.inputs["Base Color"]); y -= 280
    if maps.get("roughness"):
        L.new(tex(maps["roughness"], True, y).outputs["Color"], b.inputs["Roughness"]); y -= 280
    if maps.get("metallic"):
        L.new(tex(maps["metallic"], True, y).outputs["Color"], b.inputs["Metallic"]); y -= 280
    nrm_in = None
    if maps.get("normal"):
        nm = _n(nt, "ShaderNodeNormalMap", (-300, y)); nm.inputs["Strength"].default_value = normal_strength
        L.new(tex(maps["normal"], True, y).outputs["Color"], nm.inputs["Color"]); nrm_in = nm.outputs["Normal"]; y -= 280
    if maps.get("height"):
        bp = _n(nt, "ShaderNodeBump", (-150, y)); bp.inputs["Strength"].default_value = bump_strength
        L.new(tex(maps["height"], True, y).outputs["Color"], bp.inputs["Height"])
        if nrm_in:
            L.new(nrm_in, bp.inputs["Normal"])
        nrm_in = bp.outputs["Normal"]
    if nrm_in:
        L.new(nrm_in, b.inputs["Normal"])
    return m


def unify(materials, saturation=0.85, value=1.0, roughness_add=0.0, tint=None):
    """Pull imported materials toward the scene's family: a Hue/Saturation/Value node on
    each Principled base colour (texture or flat), optional tint and roughness offset."""
    done = 0
    for m in materials:
        if not m or not m.use_nodes:
            continue
        nt = m.node_tree
        b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if b is None or nt.nodes.get("IA_Unify"):
            continue
        hsv = nt.nodes.new("ShaderNodeHueSaturation"); hsv.name = "IA_Unify"
        hsv.inputs["Saturation"].default_value = saturation
        hsv.inputs["Value"].default_value = value
        base = b.inputs["Base Color"]
        if base.links:
            src = base.links[0].from_socket
            nt.links.remove(base.links[0])
            nt.links.new(src, hsv.inputs["Color"])
        else:
            hsv.inputs["Color"].default_value = base.default_value
        out = hsv.outputs["Color"]
        if tint:
            mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
            mix.inputs[0].default_value = 1.0
            nt.links.new(out, mix.inputs[6]); mix.inputs[7].default_value = (*tint, 1)
            out = mix.outputs[2]
        nt.links.new(out, base)
        if roughness_add and not b.inputs["Roughness"].links:
            r = b.inputs["Roughness"]
            r.default_value = min(1.0, max(0.0, r.default_value + roughness_add))
        done += 1
    return done
