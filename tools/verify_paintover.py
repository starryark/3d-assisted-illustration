#!/usr/bin/env python3
"""verify_paintover.py — read a paintover kit back and check it (needs: pip install psd-tools).

    python tools/verify_paintover.py out/rooftop_city/paintover/Cam_Main

For the .psd: every layer named in LAYERS.md exists with the right size, visibility and
blend mode, and its pixels equal the exported layers/*.png (exactly). For the .ora: the
zip has the OpenRaster structure (mimetype first and stored, stack.xml, every src
present). Exit code 1 on any mismatch.
"""
import glob
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
from psd_tools import PSDImage

BLEND = {"normal": "NORMAL", "multiply": "MULTIPLY", "screen": "SCREEN", "overlay": "OVERLAY", "add": "LINEAR_DODGE"}


def safe(name):
    return "".join(ch if ch.isalnum() else "_" for ch in name).strip("_")


def parse_layers_md(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        if line.startswith("| ") and not line.startswith("| Layer") and not line.startswith("|---"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows.append(dict(name=cells[0], visible=cells[1] == "yes", blend=cells[2].split()[0]))
    return rows


def main(kit):
    errors = []
    psd_path = glob.glob(os.path.join(kit, "*.psd"))[0]
    ora_path = glob.glob(os.path.join(kit, "*.ora"))[0]
    spec = parse_layers_md(os.path.join(kit, "LAYERS.md"))
    psd = PSDImage.open(psd_path)
    layers = {l.name: l for l in psd}
    print(f"PSD {os.path.basename(psd_path)}: {psd.width}x{psd.height}, {len(layers)} layers")
    for s in spec:
        L = layers.get(s["name"])
        if L is None:
            errors.append(f"missing layer {s['name']}")
            continue
        if L.visible != s["visible"]:
            errors.append(f"{s['name']}: visible={L.visible}, expected {s['visible']}")
        if L.blend_mode.name != BLEND[s["blend"]]:
            errors.append(f"{s['name']}: blend {L.blend_mode.name}, expected {BLEND[s['blend']]}")
        a = np.asarray(L.numpy() * 255.0 + 0.5, dtype=np.uint8) if L.numpy() is not None else None
        ref = np.asarray(Image.open(os.path.join(kit, "layers", safe(s["name"]) + ".png")).convert("RGBA"))
        if a is None or a.shape[:2] != ref.shape[:2]:
            errors.append(f"{s['name']}: size {None if a is None else a.shape} vs {ref.shape}")
            continue
        if a.shape[2] == 3:
            a = np.concatenate([a, np.full(a.shape[:2] + (1,), 255, np.uint8)], 2)
        diff = int(np.abs(a.astype(int) - ref.astype(int)).max())
        status = "OK" if diff <= 1 else "MISMATCH"
        print(f"  {status:8s} {s['name']:24s} visible={L.visible!s:5s} blend={L.blend_mode.name:12s} max|diff|={diff}")
        if diff > 1:
            errors.append(f"{s['name']}: pixel diff {diff}")
    comp = np.asarray(psd.composite().convert("RGB"))
    print(f"  composite {comp.shape[1]}x{comp.shape[0]} mean {comp.mean():.1f}")
    with zipfile.ZipFile(ora_path) as z:
        names = z.namelist()
        first = z.infolist()[0]
        if first.filename != "mimetype" or first.compress_type != zipfile.ZIP_STORED or z.read("mimetype") != b"image/openraster":
            errors.append("ora: mimetype must be the first, stored entry")
        stack = ET.fromstring(z.read("stack.xml"))
        srcs = [l.get("src") for l in stack.iter("layer")]
        missing = [s for s in srcs if s not in names]
        if missing:
            errors.append(f"ora: missing {missing}")
        for req in ("mergedimage.png", "Thumbnails/thumbnail.png"):
            if req not in names:
                errors.append(f"ora: missing {req}")
        print(f"ORA {os.path.basename(ora_path)}: {len(srcs)} layers, {stack.get('w')}x{stack.get('h')}")
    if errors:
        print("FAILED:\n  " + "\n  ".join(errors))
        sys.exit(1)
    print("paintover kit OK")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out/rooftop_city/paintover/Cam_Main")
