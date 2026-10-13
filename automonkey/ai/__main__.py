"""Command line for agents that only have a shell (one command = act + screenshot).

    python -m automonkey.ai shot [--grid 100]
    python -m automonkey.ai do "launch firefox; maximize; url google.ro"
    python -m automonkey.ai zoom X Y W H
    python -m automonkey.ai windows
    python -m automonkey.ai find "Accept all"
    python -m automonkey.ai read [X Y W H]

Screenshots are written to --out (default: $AUTOMONKEY_AI_OUT or
/tmp/automonkey_ai/screen.png) and the path is printed; open it to look.
Coordinates are pixels of that screenshot.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile

from . import act, observe, ocr, screen, window_list

DEFAULT_OUT = os.environ.get("AUTOMONKEY_AI_OUT",
                             os.path.join(tempfile.gettempdir(), "automonkey_ai", "screen.png"))


def _save(img, out: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    img.save(out, compress_level=1)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m automonkey.ai", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default=DEFAULT_OUT, help="where to save the screenshot")
    p.add_argument("--grid", type=int, default=0, help="overlay a labelled grid every N pixels")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("shot", help="take a screenshot")
    d = sub.add_parser("do", help="run an action script, then take a screenshot")
    d.add_argument("script", help="steps separated by ';' or newlines ('-' reads stdin)")
    d.add_argument("--no-shot", action="store_true", help="don't take a screenshot")
    z = sub.add_parser("zoom", help="enlarged view of a region")
    z.add_argument("box", type=int, nargs=4, metavar=("X", "Y", "W", "H"))
    sub.add_parser("windows", help="list windows")
    f = sub.add_parser("find", help="find text on screen (OCR)")
    f.add_argument("text")
    r = sub.add_parser("read", help="read text on screen (OCR)")
    r.add_argument("box", type=int, nargs="*", metavar="X Y W H")
    a = p.parse_args(argv)

    if a.cmd == "shot":
        text, img = observe(grid=a.grid)
        print(text)
        print("screenshot:", _save(img, a.out))
    elif a.cmd == "do":
        script = sys.stdin.read() if a.script == "-" else a.script
        text, img = act(script, screenshot=not a.no_shot, grid=a.grid)
        print(text)
        if img is not None:
            print("screenshot:", _save(img, a.out))
        return 0 if not text.startswith("STOPPED") else 1
    elif a.cmd == "zoom":
        print("zoom:", _save(screen.zoom(*a.box, grid=a.grid), a.out.replace(".png", "_zoom.png")))
    elif a.cmd == "windows":
        print(window_list())
    elif a.cmd == "find":
        hits = ocr.find_text(a.text)
        print("\n".join(f"{h['text']!r} click at {h['cx']},{h['cy']}" for h in hits) or "not found")
    elif a.cmd == "read":
        print(ocr.read_text(*(a.box or [0, 0, 0, 0])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
