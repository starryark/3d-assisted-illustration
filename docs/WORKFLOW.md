# The workflow, stage by stage

The goal of the 3D stage is not a finished render. It is a **base image you can trust**:
correct perspective, believable scale, a coherent light direction, and the masks to work
with them. The finished artwork is made in 2D. This document covers what to decide in each
stage, how the toolkit supports it, and what the checkpoint verifies.

Run any stage with `python tools/run.py scenes/<name> --until <stage>`.

---

## 0. Before Blender: what should the image express?

Write it down in `scenes/<name>/BRIEF.md`: the narrative in one sentence, the references, and
a thumbnail sketch showing where the subject sits and where the largest light and dark
masses go. Then **fix the aspect ratio** (`RESOLUTION`). A wide frame and a vertical one
need different arrangements of the same objects.

## 1. Blockout — composition with boxes

Build only:

- the camera or cameras;
- simple masses for the large forms;
- the character placeholder;
- one light.

Then judge the thumbnail.

**Camera rules** (`ia.camera`):

- **Position decides perspective; focal length only crops.** Place the camera first, then
  choose the lens.
- Tilting the camera makes verticals converge. `add_cam(..., level=True)` keeps it level
  and frames the target with lens shift, so towers stay vertical.
- For strong foreground presence, go closer and wider. For a dense, layered skyline, go
  further away and use a longer lens.

**Character placeholder** (`ia.mannequin`): a figure with human proportions that solves body
scale against the architecture, the pose, the contact points and which parts catch light.
The face, hair and clothes are drawn later. `pose_sit(fig, seat_z, edge=(point, normal))`
sits it on a ledge with the knees past the edge and the hands on the seat.

**Shared layout:** generate the plan from `ctx.rng` in a function used by both blockout and
assemble (see `layout()` in the example). The boxes and the final buildings then agree
exactly.

**Checkpoint:** a clay render (one neutral material on everything) with a grayscale version
and a thumbnail. The scene's own checks run here, for example:

- the figure sits on the parapet within 1 cm;
- the knees clear the edge;
- the hands rest on the coping;
- the figure falls on the left third and the landmark on the right third;
- the spire top is inside the frame.

These are measured, not eyeballed (`ia.verify.in_frame`, `mesh_bounds`).

## 2. Assemble — detail where it will be seen

Replace the masses with detailed versions at the same positions (`S.set_hide(blockout)`).

- **Allocate detail by how many pixels a feature will occupy.** In the example, buildings
  within 80 m of the camera get real window modules (`facade_building(lod="near")`).
  Distant ones are a single volume with a shader-only window grid (`lod="far"`).
- **Model what defines the composition; obtain what is merely complex.** The landmark's
  silhouette carries the image, so it is custom (`landmark_tower`). A motorbike or a
  detailed vending machine is worth downloading (see [ASSETS.md](ASSETS.md)).
- **Give kitbashed parts a structural logic.** Pipes start and end at something, cables run
  between supports, and doors lead somewhere.
- **Use structured variation.** Group the skyline into clusters with a lower gap, so the eye
  has somewhere to rest. Vary height, facade and rooftop equipment, but keep doors and floor
  heights believable.
- **Keep clear space around the subject.** The example lowers near buildings that would sit
  directly behind the figure's silhouette.

**Checkpoint:** clay again, plus contact checks (every rooftop prop rests on the roof within
2 cm). Contacts are measured with exact evaluated vertices and a ray-cast that ignores the
object itself. This matters: an object's base is coplanar with the surface it stands on.

## 3. Materials — one family

Downloaded assets clash in saturation, roughness, texture scale and contrast. Choose a small
family, then adapt everything to it:

- a few related concretes;
- painted metal;
- dark steel;
- glass;
- a limited set of accents.

The kits use `ia.materials`. For imported materials, use `unify()` (saturation, value, tint,
roughness) and `ia.assets.fix_data_colorspaces()`: roughness, metallic, normal and height
maps are data (Non-Color), whatever their file extension says. Put dirt where water and wear
put it, not everywhere.

**Checkpoint:** real materials under neutral light (a default sun and sky are added if the
scene has none yet).

## 4. Lighting — one clear idea

- **One dominant light, usually the sun.** Set its direction by azimuth and elevation, and
  its softness by angular size. Then add a sky or HDRI for ambient light, and a few local
  accents. If you use an HDRI with a visible sun, align the two; competing shadow directions
  read as wrong.
- **Decide where the light/dark boundaries fall.** In the example the figure is a dark
  silhouette against a bright haze, a deliberate light area behind the most important shape.
- **Depth through contrast.** Near forms keep strong contrast, middle forms are moderated,
  and far forms move toward the atmospheric colour. `atmosphere.mist(start, depth)` defines
  the distance range. The scene's `HAZE` constant decides how much haze is mixed in, and
  that amount stays adjustable in the paintover.
- **Fix the view transform early** (AgX by default) and don't judge materials under a moving
  target.

**Checkpoint:** the lit image, and the key gate, **grayscale readability**. The mean
luminance inside the subject's mask is compared with a ring just outside it; it must differ
by at least `VALUE_SEPARATION`. Exposure must also stay in bounds (no large crushed or
clipped areas). In the example this gate rejected two versions before the figure read
properly (see [VERIFICATION.md](VERIFICATION.md)).

## 5. Render — the handoff

The render stage writes, per camera:

| Output | Purpose |
|---|---|
| `beauty` | the paint base (view-transformed, no haze, no lens look) |
| `haze` | the haze factor, from the remapped Mist pass |
| `mist` | raw distance |
| `ao` | contact shadows (raw) |
| `emission` | lights and lit windows |
| `mask_<group>` | anti-aliased object masks from pass indices, plus `mask_sky` |
| `final` | the composited render with haze, glare and vignette |

These are assembled into the layered paintover kit ([PAINTOVER.md](PAINTOVER.md)).

Render small while the composition, materials and light are still changing (`--quality
draft|preview`). When denoising, check that thin cables and railings survive.

## 6. Paint

The 3D stage gives spatial consistency; painting decides what the viewer receives:

- simplify busy distant geometry;
- sharpen edges near the focal area and lose them elsewhere;
- repaint conspicuous repetition;
- develop the figure;
- add the story details that would be slow to build.

Compare the render and the paintover at thumbnail size. The painting should have clearer
emphasis.
