"""passes.py — the render outputs a painter needs, written as separate files.

    beauty      display-referred render (AgX), no haze, no lens look      -> paint base
    haze        haze factor (0..1) from the Mist pass, remapped            -> haze layer alpha
    mist        raw normalised distance (data)
    ao          ambient occlusion (data)                                   -> multiply layer
    emission    emitted light (display-referred)                           -> screen layer
    mask_<g>    anti-aliased object masks per mask group (+ mask_sky)      -> selections
    final       beauty + haze + glare/vignette: the "finished render" preview

Blender 5.2 compositor facts this relies on (probed, see docs/LESSONS.md):
  * the compositor is a node group assigned to scene.compositing_node_group, ending in
    a Group Output (no Composite node);
  * File Output items: node.file_output_items.new(type, name) -> "<name>.png";
    format.media_type must be 'IMAGE' before file_format can be 'PNG';
    per-item format overrides crash — keep ONE node-level format;
  * FLOAT sockets are written raw (no view transform); colour sockets honour
    item.save_as_render (True = view transform applied).
"""
import os
import bpy
from .scene import log, MASK_GROUPS


def _haze_chain(ng, mist_socket, lo, hi, amount):
    mr = ng.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = lo
    mr.inputs["From Max"].default_value = hi
    mr.inputs["To Min"].default_value = 0.0
    mr.inputs["To Max"].default_value = amount
    mr.clamp = True
    ng.links.new(mist_socket, mr.inputs["Value"])
    return mr.outputs[0]


def setup(out_dir, haze=None, look=True, ao=True, emission=True, masks=True):
    """Build the compositor. haze = dict(color=(r,g,b), start=0..1, end=0..1, amount=0..1)
    in Mist-pass units (atmosphere.mist sets the metric range). Returns the File Output node."""
    sc = bpy.context.scene
    vl = bpy.context.view_layer
    vl.use_pass_mist = True
    vl.use_pass_ambient_occlusion = ao
    vl.use_pass_emit = emission
    vl.use_pass_object_index = masks
    ng = bpy.data.node_groups.new("IA_Passes", 'CompositorNodeTree')
    ng.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
    N, Lk = ng.nodes.new, ng.links.new
    rl = N("CompositorNodeRLayers")
    fo = N("CompositorNodeOutputFile")
    fo.format.media_type = 'IMAGE'
    fo.format.file_format = 'PNG'
    fo.format.color_mode = 'RGBA'
    fo.format.color_depth = '16'
    fo.directory = out_dir
    fo.file_name = ""

    def item(kind, name, socket, as_render=True):
        it = fo.file_output_items.new(kind, name)
        it.save_as_render = as_render
        Lk(socket, fo.inputs[name])
        return it
    item('RGBA', "beauty", rl.outputs["Image"], True)
    item('FLOAT', "mist", rl.outputs["Mist"])
    final = rl.outputs["Image"]
    if haze:
        hf = _haze_chain(ng, rl.outputs["Mist"], haze.get("start", 0.0), haze.get("end", 1.0), haze.get("amount", 0.8))
        item('FLOAT', "haze", hf)
        mix = N("ShaderNodeMix"); mix.data_type = 'RGBA'
        Lk(hf, mix.inputs[0]); Lk(final, mix.inputs[6])
        mix.inputs[7].default_value = (*haze["color"], 1)
        final = mix.outputs[2]
    if ao:
        item('RGBA', "ao", rl.outputs["Ambient Occlusion"], False)
    if emission:
        item('RGBA', "emission", rl.outputs["Emission"], True)
    if masks:
        groups = dict(MASK_GROUPS); groups["sky"] = 0
        for g, idx in groups.items():
            idm = N("CompositorNodeIDMask")
            idm.inputs["Index"].default_value = idx
            idm.inputs["Anti-Alias"].default_value = True
            Lk(rl.outputs["Object Index"], idm.inputs["ID value"])
            item('FLOAT', f"mask_{g}", idm.outputs[0])
    if look:
        gl = N("CompositorNodeGlare")
        for t in ("Fog Glow", "FOG_GLOW", "Bloom"):
            try:
                gl.inputs["Type"].default_value = t
                break
            except Exception:
                continue
        gl.inputs["Threshold"].default_value = 1.0
        gl.inputs["Strength"].default_value = 0.35
        gl.inputs["Size"].default_value = 0.55
        Lk(final, gl.inputs["Image"])
        em = N("CompositorNodeEllipseMask"); em.inputs["Size"].default_value = (0.95, 0.85)
        bl = N("CompositorNodeBlur")
        res = sc.render.resolution_x
        bl.inputs["Size"].default_value = (res * 0.15, res * 0.15)
        Lk(em.outputs["Mask"], bl.inputs["Image"])
        vg = N("ShaderNodeMix"); vg.data_type = 'RGBA'; vg.blend_type = 'MULTIPLY'
        vg.inputs[0].default_value = 0.3
        Lk(gl.outputs["Image"], vg.inputs[6]); Lk(bl.outputs["Image"], vg.inputs[7])
        final = vg.outputs[2]
    item('RGBA', "final", final, True)
    out = N("NodeGroupOutput")
    Lk(final, out.inputs[0])
    sc.compositing_node_group = ng
    sc.render.use_compositing = True
    return fo


def set_dir(fo, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    fo.directory = out_dir


def disable():
    bpy.context.scene.render.use_compositing = False


EXPECTED = ("beauty", "mist", "final")


def written(out_dir):
    return sorted(f[:-4] for f in os.listdir(out_dir) if f.endswith(".png")) if os.path.isdir(out_dir) else []
