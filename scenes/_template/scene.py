"""__TITLE__ — scene template (copy with: python tools/new_scene.py <name> "<Title>").

Fill the stages in order and run each checkpoint before moving on:

    python tools/run.py scenes/__NAME__ --until blockout     # does the image work as a thumbnail?
    python tools/run.py scenes/__NAME__ --until assemble     # does detail support the composition?
    python tools/run.py scenes/__NAME__ --until materials    # do the objects belong to one place?
    python tools/run.py scenes/__NAME__ --until lighting     # is the focal point clear in grayscale?
    python tools/run.py scenes/__NAME__                      # passes + layered paintover kit

Every stage function receives ctx (ia.stages.Ctx): ctx.rng (seeded), ctx.camera(...),
ctx.subject(...), ctx.check(label, ok, detail), ctx.data (shared dict), ctx.q (quality).
This template is a minimal, valid scene: a figure standing beside a block under one sun.
"""
import math
from mathutils import Vector
from ia import scene as S, kits as K, materials as M, mannequin as MQ, lighting as LI, atmosphere as AT
from ia import verify as VF

TITLE = "__TITLE__"
RESOLUTION = (1920, 1080)                 # decide the aspect first: it changes the arrangement
SEED = 1
MASKS = {"figure": 1, "set": 2}           # one mask per group the painter will want to select
HAZE = dict(color=(0.8, 0.82, 0.86), start=0.05, end=0.9, amount=0.5)
VALUE_SEPARATION = 0.08                   # subject vs its surroundings in grayscale (lit stages)


def blockout(ctx):
    """Camera, simple masses, the character placeholder, one light."""
    ctx.camera("Cam_Main", (0.0, -7.0, 1.6), (0.0, 0.0, 1.1), lens=35)
    mb = K.MB()
    mb.box((0, 0, -0.05), (40, 40, 0.1))                        # ground
    mb.box((1.6, 1.0, 1.2), (1.5, 1.5, 2.4))                    # a mass to compose against
    S.tag(mb.to_object("Set", [M.concrete()], S.col("Set")), "set")
    fig = MQ.build("Figure", (-0.6, 0.0, 0.0), yaw_deg=20.0, color=(0.15, 0.14, 0.14))
    MQ.look_at(fig, (1.6, 1.0, 1.6))
    S.tag(fig["parts"], "figure")
    ctx.subject("figure", fig["parts"], lambda: [MQ.head_center(fig), fig["spine"].matrix_world.translation])
    LI.sun(azimuth=200, elevation=35, energy=3.5)
    lo, hi = VF.mesh_bounds(fig["parts"])
    ctx.check("figure stands on the ground (|z| < 1 cm)", abs(lo.z) < 0.01, round(lo.z, 4))


def assemble(ctx):
    """Replace / dress the blockout with detailed geometry (kits, imported assets)."""


def materials(ctx):
    """Establish the material family; unify imported materials (ia.materials.unify)."""


def lighting(ctx):
    """Sun/sky (or ia.lighting.hdri), local accents, atmosphere (ia.atmosphere.mist)."""
    LI.sky_gradient(strength=0.7)
    AT.mist(start=5.0, depth=60.0)
