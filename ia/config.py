"""config.py — paths, device and quality presets (env-overridable).

    IA_OUT      outputs root                     (./out)
    IA_ASSETS   optional downloaded assets        (./assets)
    IA_DEVICE   GPU (OptiX > CUDA > HIP > Metal > oneAPI, CPU fallback) or CPU   (GPU)
"""
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.abspath(os.environ.get("IA_OUT", os.path.join(REPO, "out")))
ASSETS = os.path.abspath(os.environ.get("IA_ASSETS", os.path.join(REPO, "assets")))
DEVICE = os.environ.get("IA_DEVICE", "GPU").upper()

# quality presets: (resolution scale of the scene's base resolution, samples, scatter density factor)
QUALITY = {
    "draft":   dict(scale=0.25, samples=16, density=0.3),
    "preview": dict(scale=0.5, samples=48, density=0.6),
    "final":   dict(scale=1.0, samples=256, density=1.0),
}


def scene_out(scene_name):
    d = os.path.join(OUT, scene_name)
    for sub in ("checkpoints", "passes", "paintover", "reports", "logs"):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    return d
