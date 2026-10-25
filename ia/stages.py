"""stages.py — the stage-gated runner.

A scene module (scenes/<name>/scene.py) defines any of these functions, each taking a
Ctx, plus a few constants:

    TITLE, RESOLUTION=(w, h), MASKS={"figure": 1, ...}, SEED, HAZE=dict(...)
    blockout(ctx)   camera(s), simple masses, the character placeholder, one light
    assemble(ctx)   detailed geometry replacing / dressing the blockout
    materials(ctx)  the material family; adapt imported materials
    lighting(ctx)   sun/sky/HDRI, local lights, atmosphere
    render(ctx)     anything render-specific (optional)

`run(module, until=stage)` executes the stages in order up to `until`, then renders a
CHECKPOINT for that stage and checks it:

    blockout, assemble   clay override (one neutral material) + default light if none
    materials            real materials, neutral default light if none
    lighting, render     everything; render also writes all passes + the paintover kit

Each checkpoint writes <out>/<scene>/checkpoints/<stage>_<cam>{,_gray,_thumb}.png and
the report <out>/<scene>/reports/report_<stage>_<quality>.json. Generic asserts:
subject visible (ray-cast) in every camera, subject readable in grayscale (value
separation against its surroundings), exposure inside bounds (lit stages), passes and
paintover files written (render stage). Scenes add their own with ctx.check(...).
"""
import importlib.util
import math
import os
import random
import time
import bpy
import numpy as np
from . import config as CFG
from . import scene as S
from . import verify as VF
from . import render as RD
from . import passes as PA
from . import paintover as PO
from . import camera as CA
from . import lighting as LI

STAGES = ("blockout", "assemble", "materials", "lighting", "render")


class Ctx:
    def __init__(self, module, quality, seed):
        self.module = module
        self.name = getattr(module, "NAME", os.path.basename(os.path.dirname(module.__file__)))
        self.quality = quality
        self.q = CFG.QUALITY[quality]
        self.out = CFG.scene_out(self.name)
        self.rng = random.Random(seed)
        self.report = None
        self.cams = []
        self.subject_group = None
        self.subject_points = lambda: []
        self.subject_objects = []
        self.data = {}                    # free-form sharing between stages

    def check(self, label, ok, detail=""):
        return self.report.check(label, ok, detail)

    def put(self, k, v):
        self.report.put(k, v)

    def camera(self, name, loc, target, lens=35, **kw):
        cam = CA.add_cam(name, loc, target, lens, **kw)
        self.cams.append(cam)
        return cam

    def subject(self, group, objects, points_fn):
        """Declare the focal subject: its mask group, its objects, and a function returning
        world points that should be visible (head, hands, ...)."""
        self.subject_group, self.subject_objects, self.subject_points = group, objects, points_fn


def load_scene(path):
    p = path if path.endswith(".py") else os.path.join(path, "scene.py")
    spec = importlib.util.spec_from_file_location("ia_scene_" + os.path.basename(os.path.dirname(os.path.abspath(p))), p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _gray_and_thumb(src, stem):
    rgba = VF.load_rgba(src)
    y = np.clip(VF.luma(rgba), 0, 1)
    H, W = y.shape
    g = np.stack([y, y, y, np.ones_like(y)], axis=2)
    PO._save_png(stem + "_gray.png", PO._to8(g))
    k = max(1, W // 240)
    t = rgba[: (H // k) * k, : (W // k) * k].reshape(H // k, k, W // k, k, 4).mean(axis=(1, 3))
    t[..., 3] = 1.0
    PO._save_png(stem + "_thumb.png", PO._to8(t))


def _default_light(stage):
    if any(o.type == 'LIGHT' for o in bpy.data.objects) and bpy.context.scene.world:
        return []
    added = []
    if not any(o.type == 'LIGHT' for o in bpy.data.objects):
        added.append(LI.sun(azimuth=35, elevation=35, energy=3.0, color=(1, 1, 1), name="IA_CheckpointSun"))
    if bpy.context.scene.world is None:
        LI.sky_gradient(horizon=(0.7, 0.72, 0.75), zenith=(0.45, 0.5, 0.58), strength=0.7, name="IA_CheckpointSky")
    return added


def checkpoint(ctx, stage, cams=None):
    R = ctx.report
    lit = stage in ("lighting", "render")
    RD.clay(stage in ("blockout", "assemble"))
    tmp_lights = [] if lit else _default_light(stage)
    RD.setup_cycles(samples=max(8, ctx.q["samples"] // (1 if lit else 2)))
    haze = getattr(ctx.module, "HAZE", None) if lit else None
    want = [c for c in ctx.cams if not cams or c.name in cams]
    R.check(f"{stage}: at least one camera", len(want) > 0, [c.name for c in want])
    for cam in want:
        pdir = os.path.join(ctx.out, "passes" if stage == "render" else "checkpoints", f"{stage}_{cam.name}")
        fo = PA.setup(pdir, haze=haze, look=lit, ao=(stage == "render"), emission=(stage == "render"))
        t = time.time()
        main = os.path.join(ctx.out, "checkpoints", f"{stage}_{cam.name}.png")
        RD.render(cam, main)
        secs = round(time.time() - t, 1)
        _gray_and_thumb(main, main[:-4])
        img_for_value = os.path.join(pdir, "final.png" if os.path.exists(os.path.join(pdir, "final.png")) else "beauty.png")
        st = VF.image_stats(main)
        st["secs"] = secs
        R.data.setdefault("exposure", {})[f"{stage}:{cam.name}"] = st
        if ctx.subject_group:
            pts = ctx.subject_points()
            names = {o.name for o in ctx.subject_objects}
            vis = VF.visible_frac(cam, pts, names) if pts else 0.0
            R.check(f"{stage}: subject visible in {cam.name} (>=60% of key points)", vis >= 0.6, round(vis, 2))
            mpath = os.path.join(pdir, f"mask_{ctx.subject_group}.png")
            if os.path.exists(mpath):
                sep = VF.value_separation(img_for_value, mpath)
                R.data.setdefault("value_separation", {})[f"{stage}:{cam.name}"] = sep
                R.check(f"{stage}: subject mask non-empty in {cam.name}", sep["coverage"] > 0.05, sep["coverage"])
                if lit:   # grayscale readability is a lighting decision; clay stages only record it
                    need = getattr(ctx.module, "VALUE_SEPARATION", 0.08)
                    if isinstance(need, dict):        # per camera: the hero view gets the strict gate
                        need = need.get(cam.name, need.get("default", 0.08))
                    R.check(f"{stage}: subject reads in grayscale in {cam.name} (|inside-ring| >= {need})",
                            sep["delta"] >= need, sep)
        if lit:
            R.check(f"{stage}: exposure in bounds in {cam.name} (0.08<mean<0.7, crush<15%, clip<5%)",
                    0.08 < st["mean"] < 0.7 and st["crush"] < 15 and st["clip"] < 5, st)
        if stage == "render":
            got = PA.written(pdir)
            need = {"beauty", "mist", "final", "ao", "emission"} | {f"mask_{g}" for g in S.MASK_GROUPS} | {"mask_sky"}
            if haze:
                need.add("haze")
            R.check(f"render: all passes written for {cam.name}", need <= set(got), sorted(need - set(got)))
            kit = PO.build_kit(ctx.name, cam.name, pdir, os.path.join(ctx.out, "paintover", cam.name),
                               haze_color=(haze or {}).get("color", (0.8, 0.82, 0.85)))
            R.check(f"render: paintover kit written for {cam.name} (psd + ora)",
                    os.path.getsize(kit["psd"]) > 1000 and os.path.getsize(kit["ora"]) > 1000, kit["layers"])
            R.data.setdefault("paintover", {})[cam.name] = kit
    for o in tmp_lights:
        bpy.data.objects.remove(o, do_unlink=True)
    RD.clay(False)


def run(scene_path, until="render", quality="preview", cams=None, seed=None):
    t0 = time.time()
    mod = load_scene(scene_path)
    if until not in STAGES:
        raise ValueError(f"--until must be one of {STAGES}")
    S.reset_scene()
    S.declare_masks(getattr(mod, "MASKS", {}))
    ctx = Ctx(mod, quality, seed if seed is not None else getattr(mod, "SEED", 1))
    ctx.report = VF.Report(f"{ctx.name}_{until}_{quality}",
                           os.path.join(ctx.out, "reports", f"report_{until}_{quality}.json"))
    w, h = getattr(mod, "RESOLUTION", (1920, 1080))
    CA.set_resolution(w, h, ctx.q["scale"])
    RD.color_management(*getattr(mod, "COLOR", ("AgX", "AgX - Medium High Contrast")))
    ctx.put("title", getattr(mod, "TITLE", ctx.name))
    ctx.put("stage", until); ctx.put("quality", quality); ctx.put("resolution", [bpy.context.scene.render.resolution_x,
                                                                                   bpy.context.scene.render.resolution_y])
    for st in STAGES:
        fn = getattr(mod, st, None)
        if fn:
            S.log(f"--- stage {st}")
            fn(ctx)
        if st == until:
            break
    checkpoint(ctx, until, cams)
    blend = os.path.join(ctx.out, f"{ctx.name}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    ctx.put("blend", os.path.relpath(blend, CFG.REPO).replace("\\", "/"))
    ctx.put("blender", bpy.app.version_string); ctx.put("device", bpy.context.scene.cycles.device)
    ctx.put("seconds", round(time.time() - t0, 1))
    path = ctx.report.write()
    n = len(ctx.report.data["asserts"]); f = ctx.report.failed
    S.log(f"STAGE {until} COMPLETE | {n - len(f)}/{n} asserts | report: {path}")
    if f:
        raise RuntimeError("asserts failed: " + "; ".join(f))
    return ctx
