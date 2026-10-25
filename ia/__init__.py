"""ia — 3D-assisted illustration toolkit for headless Blender 5.2.

Build a scene that gives you reliable perspective, scale and lighting; render a base
image plus the passes and masks a painter needs; hand it to 2D as a layered file.
Every stage is scripted, seeded and checked with numeric asserts.

Modules (all run inside Blender):
    config      paths, device, quality presets
    scene       collections, objects, pass-index groups
    camera      cameras, framing, aspect
    verify      Report/asserts, exact bounds, ray-cast contact, visibility, image stats
    assets      isolated import, inspection, normalisation, texture/colour-space repair
    materials   procedural material family + image-based PBR builder + unification
    kits        procedural modelling kits (buildings, landmark, rooftop props, cables, rubble, scatter)
    mannequin   articulated character placeholder with poses and contact points
    posing      armature helpers for imported rigs (analytic two-bone solves, aims)
    lighting    sun, sky, HDRI, local lights
    atmosphere  mist range, fog volume
    render      Cycles setup with device fallback, colour management, clay override
    passes      compositor: beauty, haze, mist, AO, emission, object masks -> files
    paintover   layered PSD + ORA + PNG kit for the 2D stage
    stages      stage-gated runner (blockout -> assemble -> materials -> lighting -> render)
"""
__version__ = "0.1.0"
