"""scene.py — collections, objects and mask groups."""
import bpy
from mathutils import Vector


def log(*a):
    print("IA |", *a, flush=True)


def upd():
    bpy.context.view_layer.update()


def reset_scene():
    """Empty the current file (keeps the scene + world datablock slots)."""
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.scene.world = None          # "no world" = the scene hasn't set one (checkpoints add a neutral sky)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for blocks in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
                   bpy.data.curves, bpy.data.armatures, bpy.data.images, bpy.data.node_groups,
                   bpy.data.worlds):
        for b in list(blocks):
            if b.users == 0:
                blocks.remove(b)


def col(name, parent=None):
    """Get or create a collection (under parent or the scene root)."""
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent.children if parent else bpy.context.scene.collection.children).link(c)
    return c


def link(o, c):
    for uc in list(o.users_collection):
        uc.objects.unlink(o)
    c.objects.link(o)
    return o


def empty(name, loc=(0, 0, 0), c=None, size=0.1, kind='PLAIN_AXES', parent=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = kind
    e.empty_display_size = size
    e.parent = parent
    e.location = Vector(loc)
    (c or bpy.context.scene.collection).objects.link(e)
    return e


def set_mat(o, m):
    if o.data.materials:
        o.data.materials[0] = m
    else:
        o.data.materials.append(m)


def collection_objects(c, types=None):
    return [o for o in c.all_objects if types is None or o.type in types]


def set_hide(c, render=None, viewport=None):
    if render is not None:
        c.hide_render = render
    if viewport is not None:
        c.hide_viewport = viewport


# ------------------------------------------------------------------ mask groups
# Every renderable object gets a pass_index; the passes module turns each index into
# a mask image (ID Mask) so the painter can select "the figure", "near city", ...
MASK_GROUPS = {}          # name -> index (filled by the scene via declare_masks)


def declare_masks(groups):
    """groups: {"figure": 1, "rooftop": 2, ...}. Index 0 is reserved for 'sky'
    (background / nothing hit)."""
    MASK_GROUPS.clear()
    MASK_GROUPS.update(groups)
    return MASK_GROUPS


def tag(objs, group):
    """Assign objects (and their mesh/curve children) to a mask group."""
    idx = MASK_GROUPS[group]
    if not isinstance(objs, (list, tuple, set)):
        objs = [objs]
    for o in objs:
        for x in [o] + list(o.children_recursive):
            if x.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT'}:
                x.pass_index = idx
    return objs


def tag_collection(c, group):
    return tag([o for o in c.all_objects], group)
