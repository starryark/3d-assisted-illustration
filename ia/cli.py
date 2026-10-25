"""cli.py — Blender-side entry point (use tools/run.py from a normal shell).

    blender --background --factory-startup --python-exit-code 1 --python ia/cli.py -- \\
            --scene scenes/rooftop_city --until render --quality preview [--cams Cam_Main] [--device CPU]
"""
import argparse
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from ia import config as CFG  # noqa: E402

ap = argparse.ArgumentParser(prog="ia/cli.py")
ap.add_argument("--scene", required=True, help="scene directory (containing scene.py) or a .py file")
ap.add_argument("--until", default="render", choices=("blockout", "assemble", "materials", "lighting", "render"))
ap.add_argument("--quality", default="preview", choices=tuple(CFG.QUALITY))
ap.add_argument("--cams", default="", help="comma-separated camera names (default: all)")
ap.add_argument("--device", choices=("GPU", "CPU"))
ap.add_argument("--seed", type=int)
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
if a.device:
    CFG.DEVICE = a.device
from ia import stages  # noqa: E402

stages.run(os.path.abspath(a.scene), until=a.until, quality=a.quality,
           cams=[c for c in a.cams.split(",") if c] or None, seed=a.seed)
