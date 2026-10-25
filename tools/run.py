#!/usr/bin/env python3
"""run.py — build a scene headless, stage by stage (plain Python 3.9+).

    python tools/run.py scenes/rooftop_city                         # all stages, preview quality
    python tools/run.py scenes/rooftop_city --until blockout        # just the blockout checkpoint
    python tools/run.py scenes/rooftop_city --stages blockout,lighting,render
    python tools/run.py scenes/rooftop_city --quality final --cams Cam_Main
    python tools/run.py scenes/rooftop_city --compare scenes/rooftop_city/reference

Each stage runs in a fresh Blender process (`--background --factory-startup`, never a
window), so every checkpoint is reproducible on its own. Blender is found via --blender,
$BLENDER, `blender` on PATH, or the default install location (5.2+ required).
"""
import argparse
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("IA_OUT", os.path.join(REPO, "out"))
STAGES = ("blockout", "assemble", "materials", "lighting", "render")


def find_blender(explicit=None):
    cands = [explicit, os.environ.get("BLENDER"), shutil.which("blender")]
    if platform.system() == "Windows":
        cands += sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe"), reverse=True)
    elif platform.system() == "Darwin":
        cands += ["/Applications/Blender.app/Contents/MacOS/Blender"]
    else:
        cands += sorted(glob.glob(os.path.expanduser("~/blender*/blender")), reverse=True)
    for c in cands:
        if c and os.path.exists(c):
            return c
    sys.exit("Blender not found: pass --blender PATH or set $BLENDER (Blender 5.2+ required)")


def version(exe):
    out = subprocess.run([exe, "--version"], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    m = re.search(r"Blender (\d+)\.(\d+)\.(\d+)", out)
    return tuple(int(x) for x in m.groups()) if m else None


def scene_name(scene_dir):
    return os.path.basename(os.path.normpath(scene_dir if not scene_dir.endswith(".py") else os.path.dirname(scene_dir)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scene")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--until", choices=STAGES, help="build up to this stage (one checkpoint)")
    g.add_argument("--stages", help="comma-separated stages, each its own checkpoint (default: all five)")
    ap.add_argument("--quality", default="preview", choices=("draft", "preview", "final"))
    ap.add_argument("--cams", default="")
    ap.add_argument("--device", choices=("GPU", "CPU"))
    ap.add_argument("--blender")
    ap.add_argument("--compare", help="directory with reference reports report_<stage>_<quality>.json")
    a = ap.parse_args()
    exe = find_blender(a.blender)
    ver = version(exe)
    print(f"Blender {'.'.join(map(str, ver)) if ver else '?'}: {exe}")
    if ver and ver[:2] < (5, 2):
        sys.exit("Blender 5.2+ required")
    stages = [a.until] if a.until else (a.stages.split(",") if a.stages else list(STAGES))
    name = scene_name(a.scene)
    logs = os.path.join(OUT, name, "logs")
    os.makedirs(logs, exist_ok=True)
    code = 0
    for st in stages:
        cmd = [exe, "--background", "--factory-startup", "--python-exit-code", "1",
               "--python", os.path.join(REPO, "ia", "cli.py"), "--",
               "--scene", os.path.abspath(a.scene), "--until", st, "--quality", a.quality]
        if a.cams:
            cmd += ["--cams", a.cams]
        if a.device:
            cmd += ["--device", a.device]
        log = os.path.join(logs, f"{st}_{a.quality}.log")
        print(f"\n=== {name}: {st} ({a.quality}) -> {log}")
        with open(log, "w", encoding="utf-8", errors="replace") as fh:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                 text=True, encoding="utf-8", errors="replace")
            for line in p.stdout:
                fh.write(line)
                if line.startswith("IA |") and ("FAIL" in line or "COMPLETE" in line or "stage" in line) \
                        or "Traceback" in line or "Error" in line:
                    print(line.rstrip())
            rc = p.wait()
        report = os.path.join(OUT, name, "reports", f"report_{st}_{a.quality}.json")
        chk = [sys.executable, os.path.join(REPO, "tools", "check_report.py"), report]
        if a.compare:
            ref = os.path.join(a.compare, f"report_{st}_{a.quality}.json")
            if os.path.exists(ref):
                chk += ["--compare", ref]
        rc2 = subprocess.call(chk) if os.path.exists(report) else 1
        code = code or rc or rc2
    sys.exit(code)


if __name__ == "__main__":
    main()
