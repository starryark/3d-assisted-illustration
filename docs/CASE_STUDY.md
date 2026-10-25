# Case study: the scene this toolkit was generalised from

This toolkit was extracted from a single narrative scene that Claude Code (Claude Opus 5.5)
built end to end in a terminal, driving Blender 5.2 headless, with a short brief and two
human course corrections. The scene is a NieR:Automata fan piece: the android A2 playing an
electric guitar on a broken beam in a ruined street, watched by about thirty machines, with
blue static arcing from her fingers into the pickups. Its repository is private, because its
renders depict third-party models; this page describes it in text only.

## What it contained

- **New procedural assets:** a posable robot (later rebuilt to measurements taken from a
  reference model), ruined reinforced-concrete buildings with damage volumes, a collapsed
  overpass, rubble, geometry-nodes grass, a combo amp and cables, electric arcs with coronas,
  and every material.
- **Reused assets:** a character rig (re-posed, with its toon shaders converted to
  Principled) and a guitar model, posed against each other using measured geometry.
- **Checks:** 27 asserts in the final build. A fresh clone reproduced the reference build
  with all 27 measured values identical and exposure statistics identical to three decimals.

## Failures that became features here

| What went wrong there | What it became here |
|---|---|
| A vision check "confirmed" a guitar that was really an 8-vertex cube | every placement is measured; `verify.Report` |
| IK missed hand and foot targets by 10–13 cm (chain tail ≠ next joint) | `posing.two_bone`, analytic on joint heads |
| Invisible holster rings held a lying body 33 cm above the street | `assets.strip_material_faces`; contact measured on real geometry |
| Rotated parts settled on inflated bounding-box corners | `verify.mesh_bounds` (evaluated vertices) |
| A loose part settled on top of another character | `verify.ray_down(..., ignore_prefix=...)` |
| "Seated" figures were standing on their hands (long arms reached below the ground) | the sit pose rests the hands; a seated-body contact assert |
| Ray-casts hit scattered grass, so things floated on blades | scatter runs after all placement |
| GUI windows opened every iteration annoyed the user | headless only (`tools/run.py`) |
| A first-guess model "looked plausible" and wasn't faithful | measure the reference first; compare side by side |

The structure of this toolkit — stages with checkpoints, numeric gates, and a layered handoff
to 2D — is the general form of what worked there.
