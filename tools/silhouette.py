"""Silhouette of a phone: the body rectangle plus the parts that stick out of it.

`phone.json` -> `layout_mm.parts` lists parts in mm relative to the body's top-left corner
(x right, y down; negative values are above / left of the body):

    {"name": "antenna", "x": 31.0, "y": -21.5, "w": 6.5, "h": 22.0, "radius_mm": 2.0}
    {"name": "flap", "polygon": [[48.0, 88.0], [52.0, 88.0], [61.5, 132.0], [58.5, 133.0]]}

`silhouette(P)` returns how far the parts reach beyond the body on each side and the full
silhouette size in mm. No parts (or an empty list) gives all extents 0 and full = body.
Layout coordinates stay relative to the body's top-left corner.
"""


def part_bounds(part):
    """(x0, y0, x1, y1) of one part, in mm relative to the body origin."""
    if "polygon" in part:
        xs = [float(p[0]) for p in part["polygon"]]
        ys = [float(p[1]) for p in part["polygon"]]
        return min(xs), min(ys), max(xs), max(ys)
    x, y, w, h = (float(part[k]) for k in ("x", "y", "w", "h"))
    return x, y, x + w, y + h


def silhouette(P):
    """Extents and full size of the body + parts, in mm."""
    w, h = float(P["size_mm"]["width"]), float(P["size_mm"]["height"])
    min_x = min_y = 0.0
    max_x, max_y = w, h
    for part in P.get("layout_mm", {}).get("parts") or []:
        x0, y0, x1, y1 = part_bounds(part)
        min_x, min_y = min(min_x, x0), min(min_y, y0)
        max_x, max_y = max(max_x, x1), max(max_y, y1)
    left, top = max(0.0, -min_x), max(0.0, -min_y)
    right, bottom = max(0.0, max_x - w), max(0.0, max_y - h)
    return {"left": left, "top": top, "right": right, "bottom": bottom,
            "full_w": w + left + right, "full_h": h + top + bottom}
