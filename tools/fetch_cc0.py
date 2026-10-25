#!/usr/bin/env python3
"""fetch_cc0.py — optional CC0 assets from Poly Haven, checksum-verified (stdlib only).

    python tools/fetch_cc0.py hdri kloofendal_48d_partly_cloudy_puresky --res 2k
    python tools/fetch_cc0.py texture concrete_wall_008 --res 1k

Files land in assets/polyhaven/<id>/ with the MD5 Poly Haven publishes for each file.
Poly Haven assets are CC0 (https://polyhaven.com/license). Use them from a scene with
ia.lighting.hdri(path) or ia.materials.image_pbr(name, maps). Builds never depend on
this: every scene must also work without network access.
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.environ.get("IA_ASSETS", os.path.join(REPO, "assets"))
API = "https://api.polyhaven.com/files/{}"
UA = {"User-Agent": "3d-assisted-illustration/0.1 (+https://github.com/starryark/3d-assisted-illustration)"}
MAPS = {"base": ["Diffuse", "diff", "Color"], "roughness": ["Rough", "rough"], "normal": ["nor_gl", "Normal"],
        "height": ["Displacement", "disp"], "ao": ["AO", "ao"], "metallic": ["Metal", "metal"]}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def save(entry, dst):
    data = get(entry["url"])
    md5 = hashlib.md5(data).hexdigest()
    if entry.get("md5") and md5 != entry["md5"]:
        sys.exit(f"md5 mismatch for {entry['url']}")
    with open(dst, "wb") as f:
        f.write(data)
    print(f"  {os.path.basename(dst)}  md5 {md5} OK")
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=("hdri", "texture"))
    ap.add_argument("asset_id")
    ap.add_argument("--res", default="1k", help="1k, 2k, 4k ...")
    a = ap.parse_args()
    files = json.loads(get(API.format(a.asset_id)))
    out = os.path.join(ASSETS, "polyhaven", a.asset_id)
    os.makedirs(out, exist_ok=True)
    got = {}
    if a.kind == "hdri":
        e = files["hdri"][a.res]["hdr"]
        got["hdri"] = save(e, os.path.join(out, os.path.basename(e["url"])))
    else:
        for role, keys in MAPS.items():
            k = next((k for k in keys if k in files), None)
            if not k or a.res not in files[k]:
                continue
            fmt = "png" if "png" in files[k][a.res] else next(iter(files[k][a.res]))
            e = files[k][a.res][fmt]
            got[role] = save(e, os.path.join(out, os.path.basename(e["url"])))
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(dict(source="polyhaven", id=a.asset_id, license="CC0", res=a.res,
                       files={k: os.path.relpath(v, REPO).replace("\\", "/") for k, v in got.items()}), f, indent=1)
    print(f"saved to {out} (manifest.json lists the files)")


if __name__ == "__main__":
    main()
