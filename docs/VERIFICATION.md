# Verification

**Measure, don't eyeball.** Every stage writes `out/<scene>/reports/report_<stage>_<quality>.json`
with labelled asserts (`ok` plus the measured detail), exposure statistics per camera, and
value-separation numbers. `tools/run.py` exits non-zero if any assert fails; so does Blender
itself, because runs use `--python-exit-code 1`.

## Generic checks (every scene, from `ia.stages`)

| Stage | Check |
|---|---|
| all | at least one camera; subject ≥ 60 % visible in every camera (ray-cast from the camera to the subject's key points, so occlusion counts, not just being in frame); subject mask non-empty |
| lighting, render | **subject reads in grayscale:** \|mean luma inside the subject mask − mean luma in a ring just outside it\| ≥ `VALUE_SEPARATION`; exposure in bounds (0.08 < mean < 0.7, crushed < 15 %, clipped < 5 %) |
| render | every expected pass written (beauty, final, mist, AO, emission, haze, one mask per group plus sky); PSD and ORA written |

The value-separation gate turns the classic "check it in grayscale" advice into a number. It
applies only to lit stages: under the blockout's single clay material, value separation is a
lighting decision that hasn't been made yet, so it is recorded but not enforced.

## Scene checks (written in the scene, with `ctx.check`)

From the example (`scenes/rooftop_city/scene.py`):

- the figure sits on the parapet (|gap| < 1 cm); the knees clear the edge; the hands rest on
  the coping;
- the figure is on the left third and the landmark on the right third; the spire top is in
  frame;
- every rooftop prop rests on the roof (< 2 cm);
- the landmark is ≥ 50 % visible through the haze; the figure looks toward the landmark
  (< 20°).

## What the gates caught while building the example

Each of these failed a check first, then was fixed:

- **A dark default world:** the clay sky was near-black, an unfair silhouette test. The
  runner now drops the default world, so checkpoints use a neutral sky.
- **A pale figure against pale haze:** value separation 0.045. The fix was a dark-clothed
  placeholder, a lighter haze and less fill, giving 0.33 in the main camera.
- **Props 4 cm inside the roof:** the roofing membrane's top sat at +4 cm, not at z = 0.
- **A pole reading 4 cm off a roof it stood on:** the old probe skipped the ignored object's
  base and the surface coplanar with it. Ignored objects are now hidden for the cast.
- **A template camera pointing at the sky:** `look_at` used a stale `matrix_world` on a
  freshly created camera.
- **glTF imports keeping their junk cube:** per-face vertex splitting turns 8 vertices into
  24, so the junk threshold is now 32.

## Comparing builds

```bash
python tools/check_report.py out/rooftop_city/reports/report_render_preview.json \
       --compare scenes/rooftop_city/reference/report_render_preview.json
```

This passes when the assert outcomes are identical and each camera's exposure is within
tolerance (mean and median ±0.02, crushed ±1 pp, clipped ±0.5 pp). Builds are deterministic
(all randomness is seeded, with no time or hash seeds), but pixels are not compared: GPU and
CPU Cycles, and different GPUs, produce different sampling noise.

## Tests

| Test | Runs in CI | What |
|---|---|---|
| `tests/test_import.py` | yes | every `ia` module imports inside Blender |
| `tests/test_assets_roundtrip.py` | yes | generated textured mesh → FBX/OBJ/GLB → `ia.assets`: isolation, inspection, junk removal, normalisation, texture rebinding, colour-space repair |
| `tools/run.py scenes/rooftop_city --quality draft` | yes (CPU) | the whole example, all stages |
| `tools/verify_paintover.py` | yes | PSD/ORA read-back, pixel-exact |
