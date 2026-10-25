"""assets.py — import hygiene for downloaded models.

Downloaded assets rarely arrive with the right scale, colours or shading. Establish a
clean source asset before making fifty copies of it:

  import_file(path, collection)  FBX / OBJ / glTF / GLB / .blend (appends a collection),
                                 returning ONLY the objects that import created
  inspect(objs)                  scale, polycount, materials, missing textures, data maps
                                 mislabelled as sRGB, non-uniform/negative scale, origin offset
  normalize(objs, target, axis)  uniform scale to a known real-world size, sit on z=0
  rebind_textures(objs, dir)     re-point missing image paths to same-named files
  fix_data_colorspaces(objs)     roughness/metallic/normal/height maps -> Non-Color
  strip_material_faces(obj, kw)  delete invisible helper geometry by material name
  drop_junk(objs, min_verts)     delete parentless export leftovers (bounds cubes)
"""
import os
import bmesh
import bpy
from mathutils import Vector
from .scene import col, link, log, upd
from . import verify as VF


def import_batch(operator, **kwargs):
    """Run an import operator; return only the objects it created (never touch earlier
    imports — a 'cleanup' pass over all scene objects once deleted a real asset)."""
    before = {o.name for o in bpy.data.objects}
    operator(**kwargs)
    return [o for o in bpy.data.objects if o.name not in before]


def import_file(path, collection_name=None, blend_collection=None):
    """Import into its own collection. For .blend, append `blend_collection` (or all
    collections in the file)."""
    ext = os.path.splitext(path)[1].lower()
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    if ext == ".fbx":
        objs = import_batch(bpy.ops.wm.fbx_import, filepath=path)
    elif ext == ".obj":
        objs = import_batch(bpy.ops.wm.obj_import, filepath=path)
    elif ext in (".gltf", ".glb"):
        objs = import_batch(bpy.ops.import_scene.gltf, filepath=path)
    elif ext == ".blend":
        before = {o.name for o in bpy.data.objects}
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            dst.collections = [c for c in src.collections if blend_collection in (None, c)]
        for c in dst.collections:
            if c is not None:
                bpy.context.scene.collection.children.link(c)
        objs = [o for o in bpy.data.objects if o.name not in before]
    else:
        raise ValueError(f"unsupported asset type: {ext}")
    target = col(collection_name or os.path.splitext(os.path.basename(path))[0])
    for o in objs:
        if o.type in {'CAMERA', 'LIGHT'}:
            bpy.data.objects.remove(o, do_unlink=True)
    objs = [o for o in objs if o.name in bpy.data.objects]
    if ext != ".blend":
        for o in objs:
            link(o, target)
    upd()
    return objs


def _images_of(objs):
    imgs = []
    for o in objs:
        if o.type != 'MESH':
            continue
        for m in o.data.materials:
            if m and m.use_nodes:
                for n in m.node_tree.nodes:
                    if n.type == 'TEX_IMAGE' and n.image:
                        imgs.append((m, n))
    return imgs


def _feeds(node):
    """Names of the BSDF inputs an image node (eventually) feeds."""
    out, stack, seen = set(), [node], set()
    while stack:
        n = stack.pop()
        if n.name in seen:
            continue
        seen.add(n.name)
        for o in n.outputs:
            for lk in o.links:
                if lk.to_node.type == 'BSDF_PRINCIPLED':
                    out.add(lk.to_socket.name)
                else:
                    stack.append(lk.to_node)
    return out


def inspect(objs, expected_size=None):
    """Return a dict describing an import (and print a one-line summary)."""
    meshes = [o for o in objs if o.type == 'MESH']
    lo, hi = VF.mesh_bounds(meshes) if meshes else (Vector(), Vector())
    dims = hi - lo
    missing, wrong_space = [], []
    for m, n in _images_of(meshes):
        p = bpy.path.abspath(n.image.filepath)
        if n.image.source == 'FILE' and not n.image.packed_file and not os.path.exists(p):
            missing.append(os.path.basename(n.image.filepath))
        feeds = _feeds(n)
        if feeds and not ({"Base Color", "Emission Color"} & feeds) and n.image.colorspace_settings.name == 'sRGB':
            wrong_space.append((m.name, n.image.name, sorted(feeds)))
    rep = dict(
        objects=len(objs), meshes=len(meshes),
        polys=sum(len(o.data.polygons) for o in meshes),
        materials=sorted({m.name for o in meshes for m in o.data.materials if m}),
        size=[round(x, 3) for x in dims],
        min_z=round(lo.z, 3),
        missing_textures=sorted(set(missing)),
        data_maps_as_srgb=wrong_space,
        nonuniform_scale=[o.name for o in objs if max(o.scale) - min(o.scale) > 1e-4],
        negative_scale=[o.name for o in objs if min(o.scale) < 0],
        parentless_tiny=[o.name for o in meshes if o.parent is None and len(o.data.vertices) < 32],
    )
    if expected_size:
        rep["scale_ratio_to_expected"] = round(max(dims) / expected_size, 3) if max(dims) else None
    log(f"inspect: {rep['meshes']} meshes, {rep['polys']} polys, size {rep['size']}, "
        f"{len(rep['missing_textures'])} missing textures, {len(rep['data_maps_as_srgb'])} data maps as sRGB")
    return rep


def normalize(objs, target, axis="max", ground=True, center=True, root_name=None):
    """Parent the import's roots under one empty, scale uniformly so the chosen dimension
    ('x','y','z' or 'max') equals `target` metres, put the lowest vertex on z=0 and centre
    it on the origin. Returns the root empty."""
    meshes = [o for o in objs if o.type == 'MESH']
    root = bpy.data.objects.new(root_name or (objs[0].name + "_ROOT"), None)
    (objs[0].users_collection[0] if objs and objs[0].users_collection else bpy.context.scene.collection).objects.link(root)
    for o in objs:
        if o.parent is None:
            o.parent = root
            o.matrix_parent_inverse = root.matrix_world.inverted()
    upd()
    lo, hi = VF.mesh_bounds(meshes)
    dims = hi - lo
    cur = max(dims) if axis == "max" else dims["xyz".index(axis)]
    root.scale *= target / max(cur, 1e-9)
    upd()
    lo, hi = VF.mesh_bounds(meshes)
    c = (lo + hi) / 2
    root.location += Vector((-c.x if center else 0, -c.y if center else 0, -lo.z if ground else 0))
    upd()
    return root


def rebind_textures(objs, tex_dir, mapping=None):
    """Fix image nodes whose files are missing: explicit mapping {old_basename: new_name}
    first, then same-named files in tex_dir (case-insensitive, extension-agnostic)."""
    pool = {os.path.splitext(f)[0].lower(): os.path.join(tex_dir, f) for f in os.listdir(tex_dir)}
    mapping = {k.lower(): v for k, v in (mapping or {}).items()}
    fixed = 0
    for m, n in _images_of(objs):
        img = n.image
        p = bpy.path.abspath(img.filepath)
        if img.packed_file or os.path.exists(p):
            continue
        base = os.path.basename(img.filepath.replace("\\", "/"))
        cand = None
        if base.lower() in mapping:
            cand = os.path.join(tex_dir, mapping[base.lower()])
        else:
            cand = pool.get(os.path.splitext(base)[0].lower())
        if cand and os.path.exists(cand):
            img.filepath = cand
            img.reload()
            fixed += 1
    return fixed


def fix_data_colorspaces(objs):
    """Any image that feeds only data inputs (roughness, metallic, normal, ...) must be
    Non-Color — the file extension doesn't say what a map means."""
    fixed = 0
    for m, n in _images_of(objs):
        feeds = _feeds(n)
        if feeds and not ({"Base Color", "Emission Color"} & feeds) and n.image.colorspace_settings.name != 'Non-Color':
            n.image.colorspace_settings.name = 'Non-Color'
            fixed += 1
    return fixed


def strip_material_faces(mesh_obj, keyword):
    """Delete faces (and loose verts) whose material name contains keyword — e.g.
    invisible helper props that would corrupt contact measurements."""
    me = mesh_obj.data
    idx = {i for i, m in enumerate(me.materials) if m and keyword.lower() in m.name.lower()}
    if not idx:
        return 0
    bm = bmesh.new(); bm.from_mesh(me)
    faces = [f for f in bm.faces if f.material_index in idx]
    verts = {v for f in faces for v in f.verts}
    bmesh.ops.delete(bm, geom=faces, context='FACES_ONLY')
    bmesh.ops.delete(bm, geom=[v for v in verts if v.is_valid and not v.link_faces], context='VERTS')
    bm.to_mesh(me); bm.free(); me.update()
    return len(faces)


def drop_junk(objs, min_verts=32):
    """Remove parentless meshes with trivially few vertices (export bounds cubes etc.).
    32, not 8: glTF splits vertices per face, so an 8-vertex cube arrives with 24."""
    all_names = [o.name for o in objs]                    # snapshot: removed objects can't be read
    junk = {o.name for o in objs if o.type == 'MESH' and o.parent is None and len(o.data.vertices) < min_verts
            and not o.children}
    for n in junk:
        bpy.data.objects.remove(bpy.data.objects[n], do_unlink=True)
    return [bpy.data.objects[n] for n in all_names if n not in junk and n in bpy.data.objects]
