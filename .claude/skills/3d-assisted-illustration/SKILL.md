---
name: 3d-assisted-illustration
description: Build an illustration base in headless Blender with the stage-gated 3D-assisted illustration workflow (blockout -> assemble -> materials -> lighting -> render -> layered PSD/ORA paintover kit), checking every stage with numeric asserts. Use when asked to block out a scene, compose a camera, build a 3D base or reference for a painting or illustration, make a paintover, export render passes and masks for painting, or create a new scene in this repository.
---

# 3D-assisted illustration (headless Blender, verified stages)

You build the 3D part of an illustration: a scene with reliable perspective, scale and light,
rendered with the passes and masks a painter needs, delivered as a layered PSD/ORA. Work in the
repository `starryark/3d-assisted-illustration` (clone it if it isn't present). Blender 5.2+ is
required; never open the Blender GUI.

## Loop

1. **Brief.** Write `scenes/<name>/BRIEF.md`: what the image expresses, the subject, the aspect,
   and where the largest light and dark masses go. Scaffold the scene with
   `python tools/new_scene.py <name> "<Title>"`.
2. **One stage at a time**, in `scenes/<name>/scene.py`:
   - `blockout(ctx)`: cameras (position decides perspective; the lens only crops;
     `level=True` keeps verticals parallel), simple masses from a seeded layout function, the
     placeholder (`ia.mannequin`), one light. Check contact and composition with `ctx.check`.
   - `assemble(ctx)`: detailed geometry at the blockout positions (`ia.kits`, or imports via
     `ia.assets`); allocate detail by pixel size; keep clear space behind the subject.
   - `materials(ctx)`: one material family (`ia.materials`); `unify()` imported materials; run
     `fix_data_colorspaces()` on imports.
   - `lighting(ctx)`: one dominant light, sky/HDRI, few accents, `ia.atmosphere.mist`; design a
     lighter area behind the subject's silhouette.
3. **Run the checkpoint:** `python tools/run.py scenes/<name> --until <stage> --quality draft`.
4. **Read the report** (`out/<name>/reports/report_<stage>_draft.json`) **and look at**
   `out/<name>/checkpoints/<stage>_<cam>.png` and `_gray.png`. A failed check is information:
   find the cause (composition, contact, light) before touching a threshold.
5. **Final:** `python tools/run.py scenes/<name> --quality final`. Deliver
   `out/<name>/paintover/<cam>/` (PSD + ORA + layers + masks + LAYERS.md) and, if psd-tools is
   available, run `python tools/verify_paintover.py out/<name>/paintover/<cam>`.

## Gates the runner enforces

- The subject is visible (ray-cast) in every camera, and its mask is non-empty.
- Lit stages: the subject reads in grayscale (`VALUE_SEPARATION`, which can be set per camera);
  exposure is in bounds.
- Render: every pass is written; the PSD and ORA are written.

## Pitfalls (see docs/LESSONS.md)

- Use `ia.verify.mesh_bounds`, not bounding boxes, for anything rotated.
- Scatter after all ray-cast placement.
- Create cameras with `ia.camera.add_cam`, which aims from `location`, not from the stale
  `matrix_world`.
- Don't commit `assets/`, `out/` or `.blend` files.
- Record the licence of every asset you obtain.
