"""posing.py — posing imported armatures and pivot rigs without trusting IK.

Lesson from the case study (docs/CASE_STUDY.md): Blender IK puts the chain TAIL on the target, and many
imported rigs (MMD among them) have elbow/knee tails that don't sit on the next joint,
so IK misses by centimetres. These helpers aim joint HEADS analytically instead:

  bend(arm, bone, world_axis, deg)      FK rotation about a world axis through the head
  aim(arm, bone, child, target)         minimal rotation so child's head lies toward target
  two_bone(arm, upper, lower, end, target, pole)   exact 2-bone solve on joint heads
  mute_constraints / restore_rest_rotation        disable rig IK, keep feet planted
  hair_settle                            scalp follows head, back chains follow torso
  rest_hand_frame / hand_target_rotation / add_hand_rot / curl_fingers  (bone-name maps)
  two_joint_pivots                       the same solve for empty-hierarchy rigs (mannequin)
"""
import math
import bpy
from mathutils import Vector, Matrix, Quaternion
from .scene import upd, empty




def bone_head(arm, name):
    return arm.matrix_world @ arm.pose.bones[name].head


def bone_tail(arm, name):
    return arm.matrix_world @ arm.pose.bones[name].tail


def rest_head(arm, name):
    return arm.matrix_world @ arm.data.bones[name].head_local


def bend(arm, name, axis_world, deg):
    """Rotate a pose bone about a WORLD axis through its head (FK, no constraints)."""
    p = arm.pose.bones[name]
    M = p.matrix.copy()
    head = M.translation.copy()
    ax = (arm.matrix_world.to_3x3().inverted() @ Vector(axis_world)).normalized()
    R = Matrix.Rotation(math.radians(deg), 4, ax)
    p.matrix = Matrix.Translation(head) @ R @ Matrix.Translation(-head) @ M
    upd()


def move_bone(arm, name, delta_world):
    p = arm.pose.bones[name]
    M = p.matrix.copy()
    M.translation += arm.matrix_world.to_3x3().inverted() @ Vector(delta_world)
    p.matrix = M
    upd()


def aim(arm, bone, child, target_world):
    """Minimal rotation of `bone` about its head so `child`'s head lands on the line
    toward target_world (uses joint heads, so tail offsets don't matter)."""
    upd()
    h = bone_head(arm, bone)
    cur = (bone_head(arm, child) - h).normalized()
    want = (Vector(target_world) - h).normalized()
    axis, ang = cur.rotation_difference(want).to_axis_angle()
    if ang > 1e-6:
        bend(arm, bone, axis, math.degrees(ang))


def two_bone(arm, upper, lower, end, target, pole_world):
    """Analytic 2-bone FK solve: `end` head -> target, `lower` head (elbow/knee) bent
    toward pole_world. Returns residual distance."""
    upd()
    S = bone_head(arm, upper)
    a = (bone_head(arm, lower) - S).length
    b = (bone_head(arm, end) - bone_head(arm, lower)).length
    tgt = Vector(target)
    d = min((tgt - S).length, (a + b) * 0.9995)
    u = (tgt - S).normalized()
    pv = Vector(pole_world) - S
    v = (pv - pv.dot(u) * u).normalized()
    cosA = max(-1.0, min(1.0, (a * a + d * d - b * b) / (2 * a * d)))
    E = S + a * (cosA * u + math.sqrt(max(0.0, 1 - cosA * cosA)) * v)
    aim(arm, upper, lower, E)
    aim(arm, lower, end, S + u * d)
    upd()
    return (bone_head(arm, end) - tgt).length


def mute_constraints(arm, bones, types=None):
    for n in bones:
        for c in arm.pose.bones[n].constraints:
            if types is None or c.type in types:
                c.mute = True
                c.influence = 0.0
    upd()


def restore_rest_rotation(arm, bone):
    """Set a bone's armature-space rotation back to its rest rotation (keep position)."""
    p = arm.pose.bones[bone]
    head = p.matrix.translation.copy()
    p.matrix = Matrix.Translation(head) @ arm.data.bones[bone].matrix_local.to_3x3().to_4x4()
    upd()


def hair_settle(arm, torso_bone="上半身2", root="hair long root", prefix="hair long",
                back_w=(0.0, 0.45, 0.8, 1.0), front_g=(0.0, 0.3, 0.55, 0.65, 0.7)):
    """Settle hair chains after the head was bowed. Scalp segments keep following the
    head; BACK chains blend toward the upper-torso orientation (hair lies on the back),
    FRONT strands blend toward their rest world rotation (gravity)."""
    rest = lambda n: arm.data.bones[n].matrix_local.to_3x3().to_quaternion()
    tp = arm.pose.bones[torso_bone]
    tq = tp.matrix.to_3x3().to_quaternion() @ rest(torso_bone).inverted()
    rdepth = len(arm.pose.bones[root].parent_recursive)
    bones = [p for p in arm.pose.bones if p.name.startswith(prefix) and p.name != root]
    for p in sorted(bones, key=lambda p: len(p.parent_recursive)):
        i = len(p.parent_recursive) - rdepth - 1
        cur = p.matrix.to_3x3().to_quaternion()
        if " back " in p.name:
            w = back_w[min(i, len(back_w) - 1)]
            tgt = tq @ rest(p.name)
        else:
            w = front_g[min(i, len(front_g) - 1)]
            tgt = rest(p.name)
        head = p.matrix.translation.copy()
        p.matrix = Matrix.Translation(head) @ cur.slerp(tgt, w).to_matrix().to_4x4()
        upd()


def orthobasis(f, p):
    f = f.normalized()
    p = (p - p.dot(f) * f).normalized()
    return Matrix((f, p, f.cross(p))).transposed()


# ------------------------------------------------------------------ hands (bone names as parameters)
# Bone-name maps: {s} = side ("L"/"R"), {f} = finger stem, {j} = joint index.
MMD_NAMES = dict(wrist="手首.{s}", middle1="中指１.{s}", index1="人指１.{s}", pinky1="小指１.{s}",
                 finger="{f}{j}.{s}", fingers=("人指", "中指", "薬指", "小指"), joints=("１", "２", "３"),
                 thumb="親指{j}.{s}", thumb_joints=("０", "１", "２"), chest="上半身2")
RIGIFY_NAMES = dict(wrist="hand.{s}", middle1="f_middle.01.{s}", index1="f_index.01.{s}", pinky1="f_pinky.01.{s}",
                    finger="f_{f}.0{j}.{s}", fingers=("index", "middle", "ring", "pinky"), joints=("1", "2", "3"),
                    thumb="thumb.0{j}.{s}", thumb_joints=("1", "2", "3"), chest="spine.003")


def rest_hand_frame(arm, side, names=MMD_NAMES):
    """Rest-pose finger direction + palm normal of a hand (armature space), derived from
    finger-bone heads: palm = (middle - wrist) x (index - pinky), negated on the right."""
    b = arm.data.bones
    nm = lambda k: names[k].format(s=side)
    wrist = b[nm("wrist")].head_local
    f = (b[nm("middle1")].head_local - wrist).normalized()
    palm = f.cross(b[nm("index1")].head_local - b[nm("pinky1")].head_local).normalized()
    return f, (-palm if side == "R" else palm)


def hand_target_rotation(arm, side, fingers_world, palm_world, names=MMD_NAMES):
    """World rotation (3x3) for the wrist bone so the fingers point along fingers_world
    and the palm faces palm_world."""
    rot_aw = arm.matrix_world.to_3x3()
    f_r, p_r = rest_hand_frame(arm, side, names)
    Mrest = arm.data.bones[names["wrist"].format(s=side)].matrix_local.to_3x3()
    B_l = orthobasis(Mrest.transposed() @ f_r, Mrest.transposed() @ p_r)
    B_d = orthobasis(rot_aw.inverted() @ Vector(fingers_world), rot_aw.inverted() @ Vector(palm_world))
    return rot_aw @ (B_d @ B_l.transposed())


def add_hand_rot(arm, side, rot_world_3x3, names=MMD_NAMES, c=None, name=None):
    """Drive the wrist with a world-space COPY_ROTATION from an empty."""
    wrist = names["wrist"].format(s=side)
    e = bpy.data.objects.get(name or f"HandRot_{side}")
    if e is None:
        e = empty(name or f"HandRot_{side}", c=c, size=0.05, kind='ARROWS')
    e.matrix_world = Matrix.Translation(bone_head(arm, wrist)) @ rot_world_3x3.to_4x4()
    p = arm.pose.bones[wrist]
    for k in [k for k in p.constraints if k.name.startswith("IA_ROT")]:
        p.constraints.remove(k)
    cr = p.constraints.new('COPY_ROTATION')
    cr.name = "IA_ROT"; cr.target = e
    cr.target_space = 'WORLD'; cr.owner_space = 'WORLD'
    upd()
    return e


def curl_fingers(arm, side, curls, thumb=(0.3, 0.3, 0.3), names=MMD_NAMES):
    """curls: {finger_stem: (j1, j2, j3) radians} toward the palm, about each finger
    bone's rest lateral axis (finger dir x palm)."""
    f_r, p_r = rest_hand_frame(arm, side, names)

    def curl(bone_name, a):
        if bone_name not in arm.pose.bones:
            return
        b = arm.data.bones[bone_name]
        d = (b.tail_local - b.head_local).normalized()
        axis_l = (b.matrix_local.to_3x3().transposed() @ d.cross(p_r).normalized()).normalized()
        p = arm.pose.bones[bone_name]
        p.rotation_mode = 'QUATERNION'
        p.rotation_quaternion = Quaternion(axis_l, a)
    for fin in names["fingers"]:
        for j, a in zip(names["joints"], curls.get(fin, (0, 0, 0))):
            curl(names["finger"].format(f=fin, j=j, s=side), a)
    for j, a in zip(names["thumb_joints"], thumb):
        curl(names["thumb"].format(j=j, s=side), a)
    upd()


# ------------------------------------------------------------------ pivot-hierarchy rigs (empties)
def align_neg_z(obj, direction):
    """Rotate obj (world) so its local -Z points along direction (keeps location/scale)."""
    d = Vector(direction).normalized()
    q = (-d).to_track_quat('Z', 'Y')
    loc = obj.matrix_world.translation.copy()
    sc = obj.matrix_world.to_scale()
    obj.matrix_world = Matrix.Translation(loc) @ q.to_matrix().to_4x4() @ Matrix.Diagonal((*sc, 1))


def two_joint_pivots(root_pv, mid_pv, end_pv, target, pole):
    """Analytic two-joint solve for a chain of pivot empties whose segments hang along
    local -Z (shoulder -> elbow -> hand, hip -> knee -> ankle): end -> target, middle
    joint bent toward pole. Returns the residual distance."""
    upd()
    S = root_pv.matrix_world.translation.copy()
    a = (mid_pv.matrix_world.translation - S).length
    b = (end_pv.matrix_world.translation - mid_pv.matrix_world.translation).length
    T = Vector(target)
    d = min((T - S).length, (a + b) * 0.9995)
    u = (T - S).normalized()
    pv = Vector(pole) - S
    v = (pv - pv.dot(u) * u).normalized()
    cosA = max(-1.0, min(1.0, (a * a + d * d - b * b) / (2 * a * d)))
    E = S + a * (cosA * u + math.sqrt(max(0.0, 1 - cosA * cosA)) * v)
    align_neg_z(root_pv, E - S); upd()
    align_neg_z(mid_pv, (S + u * d) - E); upd()
    return (end_pv.matrix_world.translation - T).length
