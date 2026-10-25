"""paintover.py — hand the render to 2D as a layered file.

Writes, per camera, into <out>/<scene>/paintover/<cam>/:
    <scene>_<cam>.psd      layered Photoshop file (opens in Photoshop, SAI2, Krita, CSP, GIMP)
    <scene>_<cam>.ora      OpenRaster (Krita, GIMP, MyPaint) — same stack
    layers/*.png           every layer as an 8-bit RGBA PNG
    masks/*.png            grayscale selection masks
    LAYERS.md              what each layer is and how to use it

Stack (top -> bottom):
    ref: final render            hidden   the composited render with lens look, for flipping
    mask: <group> ...            hidden   solid colour, alpha = mask (Ctrl/Cmd-click = select)
    emission                     hidden   screen — boost lights/signs
    ambient occlusion            hidden   multiply — deepen contact shadows
    haze                         visible  haze colour, alpha = distance haze (opacity = amount)
    base                         visible  the beauty render (no haze, no look)

Pure numpy + bpy image I/O: no Pillow/psd libraries needed. The PSD writer emits 8-bit
RGB with raw (uncompressed) channels; tools/verify_paintover.py reads it back.
"""
import os
import struct
import zipfile
import bpy
import numpy as np
from .verify import load_rgba
from .scene import log

BLEND = {"normal": b"norm", "multiply": b"mul ", "screen": b"scrn", "overlay": b"over", "add": b"lddg"}
ORA_OP = {"normal": "svg:src-over", "multiply": "svg:multiply", "screen": "svg:screen", "overlay": "svg:overlay",
          "add": "svg:plus"}
MASK_COLORS = [(0.95, 0.3, 0.3), (0.3, 0.85, 0.4), (0.3, 0.55, 0.95), (0.95, 0.8, 0.25), (0.8, 0.4, 0.9),
               (0.3, 0.85, 0.85), (0.95, 0.55, 0.25), (0.6, 0.6, 0.6)]


def _to8(a):
    return np.clip(np.round(a * 255.0), 0, 255).astype(np.uint8)


def _pascal(name, pad=4):
    b = name.encode("latin-1", "replace")[:255]
    s = bytes([len(b)]) + b
    return s + b"\x00" * ((-len(s)) % pad)


def write_psd(path, layers, merged):
    """layers: list (top -> bottom) of dict(name, rgba uint8 (H,W,4), blend, opacity 0..1, visible).
    merged: uint8 (H,W,3) composite shown by readers that ignore layers."""
    H, W = merged.shape[:2]
    recs, chans = b"", b""
    for L in reversed(layers):                       # PSD stores bottom -> top
        rgba = L["rgba"]
        planes = [rgba[..., 0], rgba[..., 1], rgba[..., 2], rgba[..., 3]]
        ids = (0, 1, 2, -1)
        info = b""
        for cid, pl in zip(ids, planes):
            info += struct.pack(">hI", cid, 2 + pl.size)
            chans += struct.pack(">H", 0) + pl.tobytes()
        flags = 0 if L.get("visible", True) else 2
        extra = struct.pack(">I", 0) + struct.pack(">I", 0) + _pascal(L["name"])
        recs += struct.pack(">iiii", 0, 0, H, W) + struct.pack(">H", 4) + info
        recs += b"8BIM" + BLEND[L.get("blend", "normal")]
        recs += struct.pack(">BBBB", int(round(255 * L.get("opacity", 1.0))), 0, flags, 0)
        recs += struct.pack(">I", len(extra)) + extra
    layer_info = struct.pack(">h", len(layers)) + recs + chans
    if len(layer_info) % 2:
        layer_info += b"\x00"
    lmi = struct.pack(">I", len(layer_info)) + layer_info + struct.pack(">I", 0)
    with open(path, "wb") as f:
        f.write(b"8BPS" + struct.pack(">H", 1) + b"\x00" * 6 + struct.pack(">HIIHH", 3, H, W, 8, 3))
        f.write(struct.pack(">I", 0))                # colour mode data
        f.write(struct.pack(">I", 0))                # image resources
        f.write(struct.pack(">I", len(lmi)) + lmi)   # layer and mask information
        f.write(struct.pack(">H", 0))                # merged image: raw
        for c in range(3):
            f.write(merged[..., c].tobytes())
    return path


def _save_png(path, rgba8):
    H, W = rgba8.shape[:2]
    img = bpy.data.images.new(os.path.basename(path), W, H, alpha=True)
    img.colorspace_settings.name = 'Non-Color'          # write values untouched
    img.pixels.foreach_set((rgba8[::-1].astype(np.float32) / 255.0).ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return path


def _thumb(rgb8, max_dim=256):
    H, W = rgb8.shape[:2]
    k = max(1, int(np.ceil(max(H, W) / max_dim)))
    h, w = H // k, W // k
    t = rgb8[:h * k, :w * k].reshape(h, k, w, k, -1).mean(axis=(1, 3))
    return t.astype(np.uint8)


def write_ora(path, layers, merged, tmp_dir):
    H, W = merged.shape[:2]
    files = []
    for i, L in enumerate(layers):
        fn = f"data/{i:02d}_{''.join(ch if ch.isalnum() else '_' for ch in L['name'])}.png"
        _save_png(os.path.join(tmp_dir, f"ora_{i:02d}.png"), L["rgba"])
        files.append((fn, os.path.join(tmp_dir, f"ora_{i:02d}.png"), L))
    m4 = np.concatenate([merged, np.full((H, W, 1), 255, np.uint8)], axis=2)
    _save_png(os.path.join(tmp_dir, "ora_merged.png"), m4)
    t = _thumb(merged)
    _save_png(os.path.join(tmp_dir, "ora_thumb.png"), np.concatenate([t, np.full(t.shape[:2] + (1,), 255, np.uint8)], 2))
    stack = [f'<?xml version="1.0" encoding="UTF-8"?>', f'<image version="0.0.3" w="{W}" h="{H}">', ' <stack>']
    for fn, _, L in files:
        stack.append(f'  <layer name="{L["name"]}" src="{fn}" x="0" y="0" opacity="{L.get("opacity", 1.0):.3f}" '
                     f'visibility="{"visible" if L.get("visible", True) else "hidden"}" '
                     f'composite-op="{ORA_OP[L.get("blend", "normal")]}"/>')
    stack += [' </stack>', '</image>']
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "image/openraster", compress_type=zipfile.ZIP_STORED)
        z.writestr("stack.xml", "\n".join(stack), compress_type=zipfile.ZIP_DEFLATED)
        for fn, src, _ in files:
            z.write(src, fn, compress_type=zipfile.ZIP_DEFLATED)
        z.write(os.path.join(tmp_dir, "ora_merged.png"), "mergedimage.png")
        z.write(os.path.join(tmp_dir, "ora_thumb.png"), "Thumbnails/thumbnail.png")
    for f in os.listdir(tmp_dir):
        if f.startswith("ora_"):
            os.remove(os.path.join(tmp_dir, f))
    return path


def build_kit(scene_name, cam_name, passes_dir, out_dir, haze_color=(0.8, 0.82, 0.85)):
    """Assemble the layered paintover kit for one camera from passes.setup() outputs."""
    os.makedirs(os.path.join(out_dir, "layers"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "masks"), exist_ok=True)
    have = {f[:-4] for f in os.listdir(passes_dir) if f.endswith(".png")}
    base = load_rgba(os.path.join(passes_dir, "beauty.png"))
    H, W = base.shape[:2]
    layers = []
    if "final" in have:
        layers.append(dict(name="ref: final render", rgba=_to8(load_rgba(os.path.join(passes_dir, "final.png"))),
                           visible=False))
    masks = sorted(k for k in have if k.startswith("mask_"))
    for i, k in enumerate(masks):
        m = load_rgba(os.path.join(passes_dir, k + ".png"))[..., 0]
        cfill = np.zeros((H, W, 4), np.float32)
        cfill[..., :3] = MASK_COLORS[i % len(MASK_COLORS)]; cfill[..., 3] = m
        layers.append(dict(name=f"mask: {k[5:]}", rgba=_to8(cfill), visible=False))
        g = _to8(np.repeat(m[..., None], 3, axis=2))
        _save_png(os.path.join(out_dir, "masks", f"{k[5:]}.png"), np.concatenate([g, np.full((H, W, 1), 255, np.uint8)], 2))
    if "emission" in have:
        e = load_rgba(os.path.join(passes_dir, "emission.png")); e[..., 3] = 1.0
        layers.append(dict(name="emission", rgba=_to8(e), blend="screen", visible=False))
    if "ao" in have:
        a = load_rgba(os.path.join(passes_dir, "ao.png")); a[..., 3] = 1.0
        layers.append(dict(name="ambient occlusion", rgba=_to8(a), blend="multiply", opacity=0.6, visible=False))
    haze_a = None
    if "haze" in have:
        haze_a = load_rgba(os.path.join(passes_dir, "haze.png"))[..., 0]
        hz = np.zeros((H, W, 4), np.float32); hz[..., :3] = haze_color; hz[..., 3] = haze_a
        layers.append(dict(name="haze", rgba=_to8(hz)))
    b = base.copy(); b[..., 3] = 1.0
    layers.append(dict(name="base", rgba=_to8(b)))
    # composite of the visible stack (base + haze) for the merged image / thumbnail
    comp = base[..., :3].copy()
    if haze_a is not None:
        comp = comp * (1 - haze_a[..., None]) + np.array(haze_color, np.float32) * haze_a[..., None]
    merged = _to8(comp)
    stem = f"{scene_name}_{cam_name}"
    for L in layers:
        safe = "".join(ch if ch.isalnum() else "_" for ch in L["name"]).strip("_")
        _save_png(os.path.join(out_dir, "layers", f"{safe}.png"), L["rgba"])
    psd = write_psd(os.path.join(out_dir, stem + ".psd"), layers, merged)
    ora = write_ora(os.path.join(out_dir, stem + ".ora"), layers, merged, out_dir)
    with open(os.path.join(out_dir, "LAYERS.md"), "w", encoding="utf-8") as f:
        f.write(f"# Paintover kit — {scene_name} / {cam_name}\n\n{W}x{H}. Layers top to bottom:\n\n")
        f.write("| Layer | Visible | Blend | Use |\n|---|---|---|---|\n")
        use = {"ref: final render": "flip on to compare with the finished render (lens look applied)",
               "emission": "boost windows, lamps, signs (screen)", "ambient occlusion": "deepen contacts (multiply)",
               "haze": "atmospheric depth — change opacity, or paint into its alpha", "base": "the beauty render: paint on layers above"}
        for L in layers:
            u = use.get(L["name"], "selection mask: Ctrl/Cmd-click the layer thumbnail to select")
            f.write(f"| {L['name']} | {'yes' if L.get('visible', True) else 'no'} | {L.get('blend', 'normal')}"
                    f"{'' if L.get('opacity', 1.0) == 1.0 else ' ' + str(int(L.get('opacity') * 100)) + '%'} | {u} |\n")
        f.write("\nSuggested order of work: large shapes, then edges (sharpen near the focal area), "
                "materials, lighting, then story details. Check the result at thumbnail size.\n")
    log("paintover kit:", out_dir, f"({len(layers)} layers)")
    return dict(psd=psd, ora=ora, layers=[L["name"] for L in layers], size=(W, H))
