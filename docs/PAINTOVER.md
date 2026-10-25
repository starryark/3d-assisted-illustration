# The paintover kit

`out/<scene>/paintover/<camera>/` contains:

| File | What |
|---|---|
| `<scene>_<camera>.psd` | layered Photoshop document: 8-bit RGB, one RGBA layer per pass, blend modes and visibility set |
| `<scene>_<camera>.ora` | the same stack as OpenRaster (Krita, GIMP, MyPaint) |
| `layers/*.png` | every layer as an 8-bit RGBA PNG (for apps that don't read either format) |
| `masks/*.png` | grayscale selection masks |
| `LAYERS.md` | the stack with blend modes and suggested uses |

## The stack (top → bottom)

| Layer | Visible | Blend | Use |
|---|---|---|---|
| `ref: final render` | no | normal | the render with haze, glare and vignette; flip it on to compare |
| `mask: <group>` | no | normal | a solid colour whose alpha is the object mask. Photoshop/SAI2/Krita/CSP: Ctrl/Cmd-click the thumbnail to load it as a selection |
| `emission` | no | screen | boost windows, lamps and signs |
| `ambient occlusion` | no | multiply 60 % | deepen contact shadows where they help the form |
| `haze` | yes | normal | the haze colour, with alpha = distance haze. Lower the opacity for clarity, or paint into it |
| `base` | yes | normal | the beauty render; paint on new layers above it |

The masks come from object pass indices declared in the scene (`MASKS = {"figure": 1, ...}`),
plus `sky` (index 0, where nothing was hit). Declare one group for each thing you will want to
select separately.

## Suggested order of work

1. **Large shapes.** Merge distracting clutter into simpler masses, adjust the sky, and simplify
   distant clusters (use `mask: city_far`).
2. **Edges.** Sharpen near the focal area and soften or lose them elsewhere. Uniform sharpness
   makes everything compete.
3. **Materials.** Reduce microtexture, repaint obvious repetition, and let brush marks follow
   the forms.
4. **Light.** Strengthen the main light shape and simplify scattered highlights.
5. **The figure.** Paint face, hair, clothing and gesture over the placeholder, using its light
   and shadow as the guide.
6. **Story.** Add the signs, damage and small objects that would be slow to build in 3D.

Check at thumbnail size: the painted version should have clearer emphasis than the render.

## Verifying a kit

```bash
pip install psd-tools pillow numpy
python tools/verify_paintover.py out/rooftop_city/paintover/Cam_Main
```

This checks that every layer listed in `LAYERS.md` exists in the PSD with the right size,
visibility and blend mode, and that its pixels equal the exported PNG exactly. It also checks
the ORA structure. CI runs it on every push.
