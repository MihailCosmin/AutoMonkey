#!/usr/bin/env python3
"""AutoMonkey demo: open Firefox, go to google.ro and type a search (not submitted).

Uses the AI layer (automonkey.ai), which handles Wayland/X11, waits for the
screen to settle after each step and converts screenshot coordinates.

Usage: python3 browser_search.py [search text] [url]
"""
import sys

from automonkey.ai import act, screen


def main(search_text: str = "betano.ro", url: str = "google.ro"):
    text, _ = act(f"launch firefox --new-window about:blank; maximize; url {url}; key escape",
                  screenshot=False)
    print(text)
    # Google's search box is centred, about halfway down the screen in a maximized window.
    v = screen.view()
    x, y = v.image_w // 2, round(v.image_h * 0.5)
    text, img = act(f"click {x} {y}; hotkey ctrl+a; type {search_text}; wait 0.5; key escape")
    print(text)
    img.save("browser_search.png")
    print("screenshot: browser_search.png")


if __name__ == "__main__":
    main(*sys.argv[1:3])
