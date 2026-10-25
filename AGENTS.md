# Notes for coding agents

This repository was built by a coding agent (Claude Code) and is meant to be extended by one.

## Rules

- **Headless only.** `python tools/run.py scenes/<name> [--until <stage>] [--quality draft|preview|final]`.
  Never open a Blender GUI per iteration.
- **One stage at a time.** Run the checkpoint, read the report
  (`out/<scene>/reports/report_<stage>_<quality>.json`) **and** look at
  `out/<scene>/checkpoints/<stage>_<cam>.png` (plus `_gray.png`) before moving on.
- **Every placement gets a check.** `ctx.check(label, ok, detail)`: contact, reach, framing,
  visibility. Labels must be static strings (reports are compared label by label); put
  measured values in `detail`. Never write `ok or True`.
- **Measure contact with `ia.verify.mesh_bounds` / `contact_offset` / `settle`.** Never use
  `world_bbox`; rotated parts inflate it.
- **Scatter after placement.** `scene.ray_cast` hits geometry-nodes instances.
- **Determinism.** All randomness comes from `ctx.rng` (or a `random.Random(seed)`). No `hash()`,
  no time-based seeds. Layout data is generated in a function shared by blockout and assemble.
- **No third-party assets in git.** `assets/`, `out/` and `*.blend` are ignored. Fetch CC0 assets
  with `tools/fetch_cc0.py`; import others through `ia.assets` and record their licence.
- When a check fails, find the cause before changing the threshold. A threshold change needs a
  reason that holds for every scene (e.g. per-camera value gates: hero strict, overview lenient).

## Map

```
ia/stages.py      runner + generic checkpoint checks          ia/cli.py  Blender entry
ia/kits.py        procedural modelling kits                    ia/mannequin.py  placeholder figure
ia/materials.py   material family, image_pbr, unify            ia/assets.py  import hygiene
ia/lighting.py    sun / sky / HDRI / local lights              ia/atmosphere.py  mist, fog
ia/camera.py      cameras, level + shift                       ia/posing.py  imported rigs
ia/verify.py      Report, bounds, ray-casts, image stats       ia/passes.py  compositor outputs
ia/paintover.py   PSD / ORA writer                             ia/render.py  Cycles, AgX, clay
scenes/<name>/scene.py   TITLE, RESOLUTION, MASKS, HAZE, SEED, VALUE_SEPARATION + stage functions
tools/run.py  new_scene.py  check_report.py  verify_paintover.py  fetch_cc0.py
```

## Adding a scene

`python tools/new_scene.py <name> "<Title>"`, then fill the stages one at a time in
`scenes/<name>/scene.py`. Declare `MASKS` for everything the painter will want to select, and
`ctx.subject(group, objects, points_fn)` for the focal subject: the runner checks its visibility
and grayscale readability in every camera.

## Before committing

```bash
python tools/run.py scenes/rooftop_city --quality preview --compare scenes/rooftop_city/reference
blender --background --factory-startup --python-exit-code 1 --python tests/test_assets_roundtrip.py
python tools/verify_paintover.py out/rooftop_city/paintover/Cam_Main      # needs psd-tools
```

Refresh `scenes/rooftop_city/reference/` and `media/` only when a visual change is intended.
Blender 5.2 API traps: `docs/LESSONS.md`.
