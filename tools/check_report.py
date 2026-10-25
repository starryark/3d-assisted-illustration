#!/usr/bin/env python3
"""check_report.py — summarise a stage report; optionally compare it with a reference.

    python tools/check_report.py out/rooftop_city/reports/report_render_preview.json
    python tools/check_report.py out/rooftop_city/reports/report_render_draft.json            --compare scenes/rooftop_city/reference/report_render_draft.json

Exit code 1 if any assert failed, or (with --compare) if the set of assert outcomes differs
or a camera's exposure statistics drift beyond tolerance. Pixels are never compared: GPU vs
CPU and sampling noise move pixels, while mean / median / crushed / clipped stay stable for
an identical scene.
"""
import argparse
import json
import sys

TOL = dict(mean=0.02, p50=0.02, crush=1.0, clip=0.5)     # luminance units / percentage points


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--compare")
    a = ap.parse_args()
    r = load(a.report)
    asserts = r.get("asserts", [])
    bad = [x for x in asserts if not x["ok"]]
    for x in asserts:
        print(f"  {'PASS' if x['ok'] else 'FAIL'}  {x['label']}" + ("" if x["ok"] else f"   <- {x['detail']}"))
    print(f"{len(asserts) - len(bad)}/{len(asserts)} asserts passed")
    for cam, st in (r.get("exposure") or {}).items():
        print(f"  {cam:14s} mean {st['mean']:.3f}  p50 {st['p50']:.3f}  crush {st['crush']:5.2f}%  "
              f"clip {st['clip']:5.2f}%  ({st.get('secs', '?')} s)")
    code = 1 if bad else 0
    if a.compare:
        ref = load(a.compare)
        mine = {x["label"]: x["ok"] for x in asserts}
        theirs = {x["label"]: x["ok"] for x in ref.get("asserts", [])}
        if mine != theirs:
            code = 1
            for k in sorted(set(mine) | set(theirs)):
                if mine.get(k) != theirs.get(k):
                    print(f"  ASSERT DIFF  {k}: this={mine.get(k)} reference={theirs.get(k)}")
        drift = []
        for cam, st in (ref.get("exposure") or {}).items():
            cur = (r.get("exposure") or {}).get(cam)
            if cur is None:
                continue
            for k, tol in TOL.items():
                if abs(cur[k] - st[k]) > tol:
                    drift.append(f"{cam}.{k}: {cur[k]} vs {st[k]} (tol {tol})")
        for d in drift:
            print("  EXPOSURE DRIFT", d)
        if drift:
            code = 1
        print("reference comparison:", "MATCH" if code == 0 else "DIFFERS")
    sys.exit(code)


if __name__ == "__main__":
    main()
