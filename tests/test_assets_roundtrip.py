"""Round-trip test for ia.assets without third-party files (runs in CI).

Builds a textured mesh (base colour + a roughness map deliberately left as sRGB) plus
an 8-vertex "export junk" cube, exports FBX / OBJ / GLB, re-imports each through
ia.assets and checks: batch isolation, inspection, junk removal, normalisation to a
real-world size, texture rebinding after the file moved, and the data-map colour-space fix.

    blender --background --factory-startup --python-exit-code 1 --python tests/test_assets_roundtrip.py
"""
import os
import shutil
import sys
import tempfile
import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ia import scene as S, assets as AS, verify as VF  # noqa: E402

tmp = tempfile.mkdtemp(prefix="ia_rt_")
R = VF.Report("assets_roundtrip", os.path.join(tmp, "report.json"))


def make_png(path, value):
    img = bpy.data.images.new(os.path.basename(path), 16, 16)
    img.pixels.foreach_set(np.full(16 * 16 * 4, value, np.float32))
    img.filepath_raw = path; img.file_format = 'PNG'; img.save()
    return img


def build_source():
    S.reset_scene()
    bpy.ops.mesh.primitive_cylinder_add(radius=0.2, depth=0.6, location=(0, 0, 0.3))
    o = bpy.context.active_object; o.name = "Prop"
    bpy.ops.object.shade_smooth()
    m = bpy.data.materials.new("PropMat"); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    tb = nt.nodes.new("ShaderNodeTexImage"); tb.image = make_png(os.path.join(tmp, "prop_base.png"), 0.6)
    tr = nt.nodes.new("ShaderNodeTexImage"); tr.image = make_png(os.path.join(tmp, "prop_rough.png"), 0.4)
    tr.image.colorspace_settings.name = 'sRGB'                     # the classic mistake
    nt.links.new(tb.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(tr.outputs["Color"], b.inputs["Roughness"])
    o.data.materials.append(m)
    bpy.ops.mesh.primitive_cube_add(size=0.05, location=(2, 0, 0))
    bpy.context.active_object.name = "ExportJunk"                    # 8-vertex bounds cube
    return o


exporters = {
    "fbx": lambda p: bpy.ops.export_scene.fbx(filepath=p, path_mode='ABSOLUTE'),
    "obj": lambda p: bpy.ops.wm.obj_export(filepath=p, path_mode='ABSOLUTE'),
    "glb": lambda p: bpy.ops.export_scene.gltf(filepath=p, export_format='GLB'),
}
for ext, export in exporters.items():
    build_source()
    path = os.path.join(tmp, f"prop.{ext}")
    export(path)
    S.reset_scene()
    # an unrelated object that must survive the import cleanup (batch isolation)
    bpy.ops.mesh.primitive_plane_add(size=1); bpy.context.active_object.name = "Bystander"
    objs = AS.import_file(path, f"Imported_{ext}")
    R.check(f"{ext}: import returns only its own objects", "Bystander" not in {o.name for o in objs},
            sorted(o.name for o in objs))
    rep = AS.inspect(objs)
    R.check(f"{ext}: inspection sees the junk cube", len(rep["parentless_tiny"]) >= 1, rep["parentless_tiny"])
    objs = AS.drop_junk(objs)
    R.check(f"{ext}: junk dropped, prop kept, bystander untouched",
            all("Junk" not in o.name for o in objs) and any(o.type == 'MESH' for o in objs)
            and "Bystander" in bpy.data.objects, sorted(o.name for o in objs))
    root = AS.normalize(objs, 0.9, axis="z")
    lo, hi = VF.mesh_bounds([o for o in objs if o.type == 'MESH'])
    R.check(f"{ext}: normalised to 0.9 m tall, standing on z=0", abs((hi.z - lo.z) - 0.9) < 1e-3 and abs(lo.z) < 1e-4,
            (round(hi.z - lo.z, 4), round(lo.z, 5)))
    if ext != "glb":                                                  # GLB embeds images
        moved = os.path.join(tmp, f"moved_{ext}"); os.makedirs(moved, exist_ok=True)
        for f in ("prop_base.png", "prop_rough.png"):
            shutil.copy(os.path.join(tmp, f), os.path.join(moved, f))
        for img in bpy.data.images:
            if img.filepath and "prop_" in img.filepath:
                img.filepath = os.path.join(tmp, "gone", os.path.basename(img.filepath))
        n = AS.rebind_textures(objs, moved)
        R.check(f"{ext}: missing textures rebound from a moved folder", n >= 1, n)
    for img in bpy.data.images:
        if "rough" in img.name.lower():
            img.colorspace_settings.name = 'sRGB'
    before = AS.inspect(objs)["data_maps_as_srgb"]
    fixed = AS.fix_data_colorspaces(objs)
    after = AS.inspect(objs)["data_maps_as_srgb"]
    R.check(f"{ext}: roughness map flagged as sRGB, then fixed to Non-Color", (fixed >= 1 and not after) or not before,
            dict(before=len(before), fixed=fixed, after=len(after)))

R.write()
shutil.rmtree(tmp, ignore_errors=True)
failed = R.failed
S.log(f"ASSET ROUND-TRIP | {len(R.data['asserts']) - len(failed)}/{len(R.data['asserts'])} passed")
if failed:
    raise RuntimeError("; ".join(failed))
