"""render.py — Cycles setup (device fallback), colour management, clay override."""
import bpy
from . import config as CFG
from .scene import log


def setup_cycles(samples=64, device=None, denoise=True, bounces=8):
    """Cycles with the first available GPU backend (OptiX > CUDA > HIP > Metal > oneAPI),
    falling back to CPU; IA_DEVICE=CPU forces CPU."""
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    device = (device or CFG.DEVICE).upper()
    sc.cycles.device = 'CPU'
    if device == 'GPU':
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for backend in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
            try:
                prefs.compute_device_type = backend
                prefs.get_devices()
            except Exception:
                continue
            gpus = [d for d in prefs.devices if d.type == backend]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == backend
                sc.cycles.device = 'GPU'
                log("Cycles device:", backend, [d.name for d in gpus])
                break
        else:
            log("no GPU backend found - rendering on CPU")
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = denoise
    sc.cycles.max_bounces = bounces
    sc.cycles.transparent_max_bounces = 16
    sc.cycles.volume_bounces = 1
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.film_transparent = False
    return sc


def color_management(view="AgX", look="AgX - Medium High Contrast", exposure=0.0):
    """AgX handles bright light gracefully (desaturates toward white). Decide this early
    and keep it fixed while judging materials and lights."""
    vs = bpy.context.scene.view_settings
    vs.view_transform = view
    try:
        vs.look = look
    except TypeError:
        vs.look = 'None'
    vs.exposure = exposure


def render(cam, path):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


_CLAY = None


def clay(on=True, color=(0.62, 0.62, 0.62), rough=0.8):
    """Blockout look: one neutral material for everything (view-layer override), so
    composition and light are judged without texture noise. Emitters are kept."""
    global _CLAY
    vl = bpy.context.view_layer
    if not on:
        vl.material_override = None
        return
    if _CLAY is None or _CLAY.name not in bpy.data.materials:
        _CLAY = bpy.data.materials.new("IA_Clay")
        _CLAY.use_nodes = True
        b = _CLAY.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*color, 1)
        b.inputs["Roughness"].default_value = rough
    vl.material_override = _CLAY
