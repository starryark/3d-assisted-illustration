"""Above the Haze — worked example of the 3D-assisted illustration workflow.

A figure sits on the parapet of an old rooftop at golden hour, looking at a distant
landmark tower rising out of the haze over a dense industrial city. Fully procedural
(no downloads), so it builds anywhere — including CI.

    python tools/run.py scenes/rooftop_city --until blockout     # composition check (clay)
    python tools/run.py scenes/rooftop_city                      # all five stages + paintover kit

Composition (decided in blockout, checked numerically):
  * camera at the back of the roof, level (verticals stay parallel), 24 mm so both the
    roof surface and the tower's top fit; figure on the left third, tower on the right third;
  * clear space behind the figure: near buildings in her sightline are kept below the
    parapet line so she reads against the bright haze, not against dark facades;
  * rooftop props sit inside the visible wedge as framing masses (hut left, units/tank right).

Coordinates: the rooftop is at z = 0, street level at z = -30; the figure faces +Y.
"""
import math
import random
import bpy
from mathutils import Vector
from ia import scene as S, kits as K, materials as M, mannequin as MQ, lighting as LI, atmosphere as AT
from ia import verify as VF

TITLE = "Above the Haze"
RESOLUTION = (1920, 1080)          # 16:9 — set the aspect early; it decides the arrangement
SEED = 7
MASKS = {"figure": 1, "rooftop": 2, "city_near": 3, "city_far": 4, "landmark": 5}
HAZE = dict(color=(0.86, 0.77, 0.67), start=0.05, end=0.85, amount=0.7)
VALUE_SEPARATION = {"Cam_Main": 0.20, "default": 0.06}   # hero view must read strongly; the overview less so

GROUND = -30.0
ROOF = dict(x0=-6.0, x1=6.0, y0=-8.0, y1=4.0, parapet=1.05)
SEAT_Z = ROOF["parapet"] + 0.08            # top of the parapet coping
EDGE = ((0.0, ROOF["y1"], SEAT_Z), (0.0, 1.0, 0.0))
FIGURE_XY = (-4.4, 3.55)
LANDMARK = dict(base=(70.0, 320.0, GROUND), height=150.0, radius=13.0)
CAM_MAIN = dict(loc=(-3.0, -2.6, 1.65), target=(-4.4, 97.4, 4.0), lens=24, level=True)
CAM_WIDE = dict(loc=(5.6, -9.8, 5.8), target=(-5.0, 25.0, 1.5), lens=24, level=False)


def _angle_from_cam(x, y):
    cx, cy = CAM_MAIN["loc"][:2]
    return math.degrees(math.atan2(x - cx, y - cy))


# ---------------------------------------------------------------- layout (shared by stages)
def layout(ctx):
    """Seeded city plan: street-grid lots near, two clusters with a lower gap far.
    Every stage regenerates it identically, so blockout masses and final buildings agree."""
    if "layout" in ctx.data:
        return ctx.data["layout"]
    rng = ctx.rng
    fig_ang = _angle_from_cam(*FIGURE_XY)
    lots = []
    for gx in range(-6, 7):
        for gy in range(0, 6):
            x = gx * 15.0 + rng.uniform(-2, 2)
            y = 16.0 + gy * 15.0 + rng.uniform(-2, 2)
            w, d = rng.uniform(8, 12), rng.uniform(8, 12)
            h = rng.choice([rng.uniform(8, 22), rng.uniform(8, 22), rng.uniform(24, 38)])
            if abs(_angle_from_cam(x, y) - fig_ang) < 9:          # clear space behind the figure
                h = min(h, -GROUND - 4.0)
            lots.append(dict(x=x, y=y, w=w, d=d, h=h, district="near"))
    for gx in range(-14, 15):
        for gy in range(0, 12):
            x = gx * 22.0 + rng.uniform(-5, 5)
            y = 120.0 + gy * 24.0 + rng.uniform(-6, 6)
            if (Vector((x, y)) - Vector(LANDMARK["base"][:2])).length < 30:
                continue
            cluster = math.exp(-((x + 120) / 85) ** 2) + math.exp(-((x - 190) / 80) ** 2)
            gap = 0.4 if -50 < x < 30 else 1.0
            h = (16 + 62 * cluster * rng.uniform(0.6, 1.2)) * gap + rng.uniform(0, 10)
            lots.append(dict(x=x, y=y, w=rng.uniform(12, 18), d=rng.uniform(12, 18), h=h, district="far"))
    ctx.data["layout"] = lots
    return lots


# ---------------------------------------------------------------- 1. blockout
def blockout(ctx):
    """Camera first, then masses, the figure placeholder and one light — judge the image
    as a thumbnail before any detail exists."""
    c_b = S.col("Blockout")
    ctx.camera("Cam_Main", CAM_MAIN["loc"], CAM_MAIN["target"], CAM_MAIN["lens"], level=CAM_MAIN["level"])
    ctx.camera("Cam_Wide", CAM_WIDE["loc"], CAM_WIDE["target"], CAM_WIDE["lens"], level=CAM_WIDE["level"])
    roof = K.roof_slab("Roof", ROOF["x0"], ROOF["x1"], ROOF["y0"], ROOF["y1"], 0.0, ROOF["parapet"],
                       depth=-GROUND, c=S.col("Rooftop"))
    S.tag(roof, "rooftop")
    street = K.MB(); street.box((0, 300, GROUND - 0.5), (1600, 1400, 1.0))
    S.tag(street.to_object("Street", [M.asphalt()], S.col("City")), "city_near")
    for i, L in enumerate(layout(ctx)):
        mb = K.MB(); mb.box((L["x"], L["y"], GROUND + L["h"] / 2), (L["w"], L["d"], L["h"]))
        o = mb.to_object(f"Mass_{i:03d}", [M.flat("BlockoutMass", (0.5, 0.5, 0.5))], c_b)
        S.tag(o, "city_near" if L["district"] == "near" else "city_far")
    mb = K.MB()
    bx, by, bz = LANDMARK["base"]
    mb.box((bx, by, bz + LANDMARK["height"] * 0.36), (LANDMARK["radius"] * 1.4,) * 2 + (LANDMARK["height"] * 0.72,))
    mb.rod((bx, by, bz + LANDMARK["height"] * 0.72), (bx, by, bz + LANDMARK["height"]), 2.0)
    S.tag(mb.to_object("Mass_Landmark", [M.flat("BlockoutMass", (0.5, 0.5, 0.5))], c_b), "landmark")
    fig = MQ.build("Figure", (FIGURE_XY[0], FIGURE_XY[1], 0.0), yaw_deg=180.0, height=1.68,
                   color=(0.13, 0.12, 0.12), c=S.col("Character"))     # dark coat: a silhouette against the haze
    MQ.pose_sit(fig, SEAT_Z, edge=EDGE, lean_deg=12.0)
    MQ.look_at(fig, (bx, by, bz + LANDMARK["height"] * 0.55))
    S.tag(fig["parts"], "figure")
    ctx.data["fig"] = fig
    ctx.subject("figure", fig["parts"], lambda: [MQ.head_center(fig), fig["handL"].matrix_world.translation,
                                                  fig["handR"].matrix_world.translation,
                                                  fig["spine"].matrix_world.translation])
    LI.sun(azimuth=22, elevation=12, energy=4.0, color=(1.0, 0.82, 0.62))
    # contact checks keep the placeholder honest
    gap = MQ.seat_contact(fig, SEAT_Z)
    ctx.check("figure sits on the parapet (|gap| < 1 cm)", abs(gap) < 0.01, round(gap, 4))
    knee = (fig["kneeL"].matrix_world.translation + fig["kneeR"].matrix_world.translation) / 2
    past = (knee - Vector(EDGE[0])).dot(Vector(EDGE[1]))
    ctx.check("knees clear the parapet edge (shins hang over)", 0.0 < past < 0.12, round(past, 3))
    hz = [fig["hand" + s].matrix_world.translation.z - SEAT_Z for s in "LR"]
    ctx.check("hands rest on the parapet (wrists 5-25 cm above the coping)", all(0.05 < z < 0.25 for z in hz),
              [round(z, 3) for z in hz])
    # composition: thirds, measured in the main camera
    S.upd()
    cam = bpy.data.objects["Cam_Main"]
    fx = VF.in_frame(cam, MQ.head_center(fig))
    lx = VF.in_frame(cam, (bx, by, bz + LANDMARK["height"] * 0.7))
    ctx.put("thirds", dict(figure=fx, landmark=lx))
    ctx.check("figure on the left third, landmark on the right third (Cam_Main)",
              fx is not None and lx is not None and 0.2 < fx[0] < 0.45 and 0.55 < lx[0] < 0.8,
              dict(figure=[round(v, 3) for v in fx] if fx else None, landmark=[round(v, 3) for v in lx] if lx else None))
    top = VF.in_frame(cam, (bx, by, bz + LANDMARK["height"]))
    ctx.check("landmark spire top inside the frame (Cam_Main)", top is not None and top[1] < 0.97,
              [round(v, 3) for v in top] if top else None)


# ---------------------------------------------------------------- 2. assemble
def assemble(ctx):
    """Detailed versions at the blockout positions; detail allocated by image size."""
    S.set_hide(S.col("Blockout"), render=True, viewport=True)
    rng = ctx.rng
    cam = Vector(CAM_MAIN["loc"])
    c_city, c_far = S.col("City"), S.col("City_Far")
    near_n = 0
    for i, L in enumerate(layout(ctx)):
        lod = "near" if (Vector((L["x"], L["y"], 0)) - cam).length < 80 else "far"
        near_n += lod == "near"
        setback = (rng.uniform(0.55, 0.8), rng.uniform(1.5, 3.0)) if L["h"] > 40 and rng.random() < 0.6 else None
        o = K.facade_building(f"Bld_{i:03d}", (L["x"], L["y"], GROUND), L["w"], L["d"], L["h"], rng, lod=lod,
                              c=c_city if lod == "near" else c_far,
                              wall_tint=rng.choice([(0.36, 0.35, 0.33), (0.42, 0.4, 0.37), (0.3, 0.31, 0.32)]),
                              lit_fraction=rng.uniform(0.08, 0.25), setback=setback)
        S.tag(o, "city_near" if L["district"] == "near" else "city_far")
    ctx.put("near_lod_buildings", near_n)
    S.tag(K.landmark_tower("Landmark", LANDMARK["base"], LANDMARK["height"], rng, radius=LANDMARK["radius"]),
          "landmark")
    S.tag(K.elevated_rail("Rail", (-420, 104, GROUND), (420, 108, GROUND), 13.0), "city_near")
    # rooftop kit inside the visible wedge; give it structural logic (pipes connect units, cables reach the pole)
    c_r = S.col("Rooftop")
    props = [
        K.door_hut("Hut", (1.2, 2.5, 0.0), yaw=0.0, c=c_r),                     # right frame edge, lamp faces camera
        K.hvac_unit("HVAC_1", (-0.7, 1.7, 0.0), (1.8, 1.2, 1.1), yaw=0.08, rng=rng, c=c_r),
        K.hvac_unit("HVAC_2", (0.9, -0.6, 0.0), (1.6, 1.1, 1.0), yaw=-0.05, rng=rng, c=c_r),
        K.water_tank("Tank", (4.6, 2.5, 0.0), radius=1.1, height=2.1, legs=1.7, c=c_r),
        K.antenna_mast("Mast", (4.2, -1.0, 0.0), 6.0, c=c_r),
    ]
    pole, tips = K.utility_pole("Pole", (-5.55, 3.55, 0.0), 7.5, c=c_r)
    props.append(pole)
    # pipe along the left parapet leads the eye to the figure; another links the units to the hut
    pipes = [K.pipe_run("Pipe_1", [(-5.55, -3.0, 0.4), (-5.55, 2.9, 0.4), (-5.55, 2.9, 0.95)], radius=0.08,
                        floor_z=0.0, c=c_r),
             K.pipe_run("Pipe_2", [(0.2, 1.7, 0.3), (0.6, 1.7, 0.3), (0.6, 1.25, 0.3)], radius=0.06, floor_z=0.0, c=c_r)]
    K.railing("Railing", [(-5.7, -7.4, 0.0), (-5.7, -4.0, 0.0)], c=c_r)
    for k, tip in enumerate(tips[:2]):
        K.cable(f"Cable_{k}", K.catenary(tip, (-30.0 - 6 * k, 30.0, GROUND + 24.0), sag=2.0), radius=0.012, c=c_r)
    K.cable("Cable_mast", K.catenary((4.2, -1.0, 5.6), tips[2], sag=0.8), radius=0.008, c=c_r)
    S.tag_collection(c_r, "rooftop")
    offs = {o.name: VF.contact_offset([o]) for o in props}
    ctx.check("rooftop props rest on the roof (<2 cm)", all(v is not None and abs(v) < 0.02 for v in offs.values()),
              {k: (round(v, 3) if v is not None else None) for k, v in offs.items()})
    c_lib = S.col("Lib_Grass")
    for i in range(3):
        K.grass_tuft(f"Tuft_{i}", random.Random(40 + i), blades=8 + 3 * i, c=c_lib)
    c_lib.hide_render = True
    for o in c_lib.objects:
        o.location.z = -500


# ---------------------------------------------------------------- 3. materials
def materials(ctx):
    """One family: related concretes, tar roofing, painted metal, dark steel, glass. The
    kits assign them; here the family is tuned (and imported assets would be unified)."""
    K.scatter(bpy.data.objects["Roof"], bpy.data.collections["Lib_Grass"], "RoofWeeds",
              density=1.6 * ctx.q["density"], seed=3, scale=(0.4, 1.0), mask_scale=0.9, mask_thresh=0.55,
              up_only=0.8, exclude=[(FIGURE_XY[0], FIGURE_XY[1], 1.2), (CAM_MAIN["loc"][0], CAM_MAIN["loc"][1], 2.0)])
    n = M.unify([m for m in bpy.data.materials if m.name.startswith("Facade_")], saturation=0.8, value=0.95)
    ctx.put("unified_materials", n)


# ---------------------------------------------------------------- 4. lighting
def lighting(ctx):
    """Low sun from beyond the city: long shadows, a rim on the figure, the tower in soft
    light; the sky fills the shadows; one warm accent at the hut door."""
    for o in [o for o in bpy.data.objects if o.type == 'LIGHT' and o.name.startswith("Sun")]:
        bpy.data.objects.remove(o, do_unlink=True)
    LI.sun(azimuth=22, elevation=12, energy=6.5, color=(1.0, 0.78, 0.55), angle_deg=1.5)
    LI.sky_gradient(horizon=(1.0, 0.74, 0.52), zenith=(0.30, 0.42, 0.62), ground=(0.08, 0.07, 0.06), strength=0.6)
    LI.point("HutLampLight", (1.2 + 0.3, 2.5 - 1.35, 2.3), energy=30.0, color=(1.0, 0.72, 0.42), radius=0.08)
    LI.area("Fill", (-1.0, -12.0, 4.0), (-3.0, 3.5, 1.0), energy=40.0, size=6.0, color=(0.62, 0.72, 0.9))
    AT.mist(start=20.0, depth=520.0, falloff='LINEAR')
    cam = bpy.data.objects["Cam_Main"]
    bx, by, bz = LANDMARK["base"]
    pts = [Vector((bx, by, bz + LANDMARK["height"] * t)) for t in (0.5, 0.65, 0.8, 0.95)]
    vis = VF.visible_frac(cam, pts, {"Landmark"})
    ctx.check("landmark visible in Cam_Main (>=50% of tower points)", vis >= 0.5, round(vis, 2))
    fig = ctx.data["fig"]
    head = MQ.head_center(fig)
    fwd = (fig["head"].matrix_world.to_3x3() @ Vector((0, -1, 0))).normalized()
    to_lm = (Vector((bx, by, bz + LANDMARK["height"] * 0.55)) - head).normalized()
    ang = math.degrees(fwd.angle(to_lm))
    ctx.check("figure looks toward the landmark (<20 deg)", ang < 20, round(ang, 1))
