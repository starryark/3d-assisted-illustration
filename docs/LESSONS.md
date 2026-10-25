# Lessons and Blender 5.2 traps

Everything here was hit while building this toolkit or its case study, and was verified on
Blender 5.2.2, not recalled.

## Compositor and render output

| Trap | What works |
|---|---|
| No `scene.node_tree`, no Composite node | Create a `CompositorNodeTree` group, add an interface output socket, end in `NodeGroupOutput`, and assign `scene.compositing_node_group`. |
| File Output node API | `node.file_output_items.new(socket_type, name)` writes `<name>.png` into `node.directory` (no frame suffix for stills). Set `format.media_type = 'IMAGE'` **before** `file_format = 'PNG'`, otherwise only multilayer EXR is accepted. |
| Per-item format overrides | `item.override_node_format` plus editing `item.format` **crashed Blender** (access violation). Use one node-level format; use two nodes if you need two formats. |
| Data passes and the view transform | FLOAT sockets (mist, masks) are written **raw** regardless of `save_as_render`. Colour sockets follow `item.save_as_render` (True = AgX applied). Verified: a wall at 10 m with mist depth 20 reads exactly 0.5. |
| Glare, Lens Distortion, ID Mask | Settings are input sockets, e.g. `glare.inputs["Type"].default_value = "Fog Glow"`, `idmask.inputs["Index"]`, `idmask.inputs["Anti-Alias"]`. |
| Mix colours in the compositor | `CompositorNodeMixRGB` is gone; `ShaderNodeMix` (data_type `RGBA`) works there too. |
| Render to PNG | `image_settings.media_type = 'IMAGE'` first. |

## Geometry, placement, measuring

- **Fresh objects have a stale `matrix_world`.** Aiming a just-created camera with
  `matrix_world.translation` aims from the world origin. Use `obj.location` (`ia.camera.look_at`
  does), or `view_layer.update()` first.
- **Bounding boxes lie for rotated objects.** `obj.bound_box` transformed to world space is the
  AABB of a rotated local box; a tumbled sphere's box corner sits about 0.4 r below it. Use
  evaluated vertices for contact and height (`verify.mesh_bounds`).
- **Ray-casting "past" an object skips coplanar surfaces.** An object resting on a surface has
  its base coplanar with it. Stepping the ray below an ignored hit also skips the surface
  underneath. Hide the ignored objects for the cast (`verify.ray_down`).
- **`scene.ray_cast` hits geometry-nodes instances.** Scatter only after all ray-cast placement.
- **Probe contact from just above the object,** not from the sky: an object in a window stands
  under the slab above it.
- `bmesh.ops.subdivide_edges` invalidates references to the original vertices.
- **glTF splits vertices per face.** An 8-vertex cube comes back with 24, so junk thresholds
  need headroom.
- Pointiness depends on mesh density, so it is useless for edge wear on low-poly primitives.
  `1 - dot(N, Bevel.N)` is resolution independent.

## Imported character rigs

- **Blender IK puts the chain tail on the target.** On many imported rigs (MMD among them) the
  elbow and knee tails don't sit on the next joint, so IK misses by centimetres. Solve two-bone
  chains analytically on joint heads (`posing.two_bone`).
- Rig-provided leg IK with knee limits can stall from a straight rest pose. Mute it, solve with
  FK, and restore the foot's rest rotation so heeled shoes stay planted.
- Bowing the head swings long hair out stiffly; resetting hair to rest detaches the scalp.
  Blend per chain instead: scalp follows the head, back chains follow the upper torso, front
  strands get partial gravity (`posing.hair_settle`).
- Converting toon shaders to Principled (reusing the model's diffuse and normal maps) makes a
  character respond properly to coloured key, rim and local light.

## Checkpoint design

- **Clay renders can't pass a value test.** One neutral material means separation is purely a
  lighting matter. Gate grayscale readability at the lit stages; record it earlier.
- **The default world is near-black.** A checkpoint sky must be neutral, or every silhouette
  test is unfair. Clear the default world, and add a neutral one when the scene has none.
- **An assert written as `ok or True` is worse than none.** Review the report, not just its
  PASS count.

## Headless operation

- `blender --background --factory-startup --python-exit-code 1 --python script.py -- args`:
  factory startup leaves user preferences untouched, and the exit code makes a failing assert
  fail the run.
- Cycles device selection: iterate `OPTIX, CUDA, HIP, METAL, ONEAPI` with `get_devices()`, then
  fall back to CPU. A "HIP dynamic library" warning on NVIDIA machines is harmless.
- blender.org's download server answers scripted downloads with a bot challenge; CI uses an
  official mirror plus the published SHA-256.
