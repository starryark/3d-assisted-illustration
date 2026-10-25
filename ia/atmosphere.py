"""atmosphere.py — depth through contrast.

Two tools:
  * mist (composited haze): the Mist pass gives normalised distance; passes.py mixes a
    haze colour into the beauty by it. Cheap, art-directable — start here.
  * fog volume: real scattering for light shafts. Density is scale-dependent; a number
    copied from another scene means nothing.
"""
import bpy
from .scene import col


def mist(start=10.0, depth=200.0, falloff='QUADRATIC'):
    w = bpy.context.scene.world
    ms = w.mist_settings
    ms.start, ms.depth, ms.falloff = start, depth, falloff
    bpy.context.view_layer.use_pass_mist = True
    return ms


def fog_volume(center, size, density=0.004, anisotropy=0.4, color=(0.85, 0.85, 0.85), name="Fog"):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    for c in list(o.users_collection):
        c.objects.unlink(o)
    col("Atmosphere").objects.link(o)
    m = bpy.data.materials.new(name + "_vol"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = density
    vol.inputs["Anisotropy"].default_value = anisotropy
    vol.inputs["Color"].default_value = (*color, 1)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    o.data.materials.append(m)
    return o
