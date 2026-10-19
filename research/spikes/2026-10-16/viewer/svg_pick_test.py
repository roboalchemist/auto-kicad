"""Click known board coordinates on the SVG+overlay page and report what was picked."""
import json

from playwright.sync_api import sync_playwright

from kc_test import BASE, SHOTS

TARGETS = {
    "U1_pad1": (7.095, 12.57),
    "U1_body_center": (9.0, 10.0),
    "THRESHOLD_track_mid": (9.0, 9.535),
    "0.35mm_off_track_inside_U1": (9.25, 9.785),
    "via_VCC": (5.0, 6.0),
    "empty_board": (20.0, 3.0),
}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1000, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{BASE}/svg_pick.html")
    page.wait_for_function("() => window.__ready === true", timeout=10000)
    for label, (x, y) in TARGETS.items():
        cx, cy = page.evaluate("([x, y]) => window.boardToClient(x, y)", [x, y])
        page.mouse.click(cx, cy)
        page.wait_for_timeout(100)
        pick = page.evaluate("() => window.__picks[window.__picks.length - 1]")
        top = pick["hits"][0] if pick["hits"] else None
        print(f"{label:28s} board=({x},{y}) client=({cx:.0f},{cy:.0f}) -> mm={pick['board_mm']} "
              f"top={json.dumps(top)} all={[h.get('ref') or h.get('net') for h in pick['hits']]}")
        if label == "U1_pad1":
            page.screenshot(path=str(SHOTS / "svg_pick_U1_pad1.png"))
    print("errors:", errors)
    browser.close()
