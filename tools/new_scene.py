#!/usr/bin/env python3
"""new_scene.py — start a new scene from the template.

    python tools/new_scene.py harbor_dawn "Harbor at Dawn"
    python tools/run.py scenes/harbor_dawn --until blockout
"""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    name = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else name.replace("_", " ").title()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        sys.exit("scene name: lowercase letters, digits and underscores, starting with a letter")
    dst = os.path.join(REPO, "scenes", name)
    if os.path.exists(dst):
        sys.exit(f"{dst} already exists")
    os.makedirs(dst)
    src = open(os.path.join(REPO, "scenes", "_template", "scene.py"), encoding="utf-8").read()
    open(os.path.join(dst, "scene.py"), "w", encoding="utf-8").write(src.replace("__NAME__", name).replace("__TITLE__", title))
    open(os.path.join(dst, "BRIEF.md"), "w", encoding="utf-8").write(
        f"# {title}\n\n## What should the image express?\n\n## References\n\n## Composition sketch\n"
        "(aspect, where the subject sits, the largest light and dark masses)\n\n## Stage notes\n")
    print(f"created scenes/{name}/scene.py and BRIEF.md\nnext:  python tools/run.py scenes/{name} --until blockout")


if __name__ == "__main__":
    main()
