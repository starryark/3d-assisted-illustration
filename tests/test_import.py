"""Headless import test: every ia module loads inside Blender."""
import os, sys, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
mods = ["config", "scene", "verify", "camera", "render", "lighting", "atmosphere", "materials", "kits",
        "posing", "mannequin", "assets", "passes", "paintover", "stages"]
bad = []
for m in mods:
    try:
        importlib.import_module("ia." + m)
        print("IMPORT OK", m)
    except Exception as e:
        bad.append(m); print("IMPORT FAIL", m, repr(e))
if bad:
    raise RuntimeError("import failures: " + ", ".join(bad))
