"""Bind PP-OCR text lines to UIA control nodes."""
from dataclasses import dataclass


@dataclass
class BindingStats:
    total: int = 0
    bound: int = 0
    unbound: int = 0

    def as_dict(self):
        return {"total": self.total, "bound": self.bound, "unbound": self.unbound}


def _flatten_tree(node):
    nodes = [node]
    for child in node.get("children", []):
        nodes.extend(_flatten_tree(child))
    return nodes


def _control_rect(node):
    rect = node.get("rect")
    if not rect or not node.get("visible", False):
        return None
    left = rect.get("left", 0)
    top = rect.get("top", 0)
    right = rect.get("right", 0)
    bottom = rect.get("bottom", 0)
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _intersection_area(rect, other):
    left = max(rect[0], other[0])
    top = max(rect[1], other[1])
    right = min(rect[2], other[2])
    bottom = min(rect[3], other[3])
    if right <= left or bottom <= top:
        return 0.0, 0.0
    area = float((right - left) * (bottom - top))
    line_area = float((other[2] - other[0]) * (other[3] - other[1]))
    return area, area / line_area if line_area else 0.0


def _select_control(nodes, line_rect, min_overlap):
    center_x = (line_rect[0] + line_rect[2]) / 2.0
    center_y = (line_rect[1] + line_rect[3]) / 2.0
    candidates = []
    for node in nodes:
        rect = _control_rect(node)
        if rect is None:
            continue
        overlap, ratio = _intersection_area(rect, line_rect)
        center_inside = rect[0] <= center_x <= rect[2] and rect[1] <= center_y <= rect[3]
        if ratio < min_overlap and not center_inside:
            continue
        area = float((rect[2] - rect[0]) * (rect[3] - rect[1]))
        depth = len(node.get("ref", "").split("."))
        candidates.append((area, -depth, -overlap, node))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return candidates[0][3]


def _apply_node_text(node):
    uia_text = node.get("name") or node.get("value") or ""
    ocr_text = node.get("ocr_text") or ""
    if uia_text and ocr_text:
        source = "uia+ocr"
    elif uia_text:
        source = "uia"
    elif ocr_text:
        source = "ocr"
    else:
        source = "none"
    node["uia_text"] = uia_text
    node["effective_text"] = uia_text or ocr_text
    node["text_source"] = source


def shift_ocr_lines(lines, origin):
    """Translate OCR line boxes from capture-local to screen coordinates."""
    origin_x, origin_y = origin
    shifted = []
    for source in lines:
        line = dict(source)
        bbox = line.get("bbox") or {}
        line["bbox"] = {
            "left": bbox.get("left", 0) + origin_x,
            "top": bbox.get("top", 0) + origin_y,
            "right": bbox.get("right", 0) + origin_x,
            "bottom": bbox.get("bottom", 0) + origin_y,
        }
        if line.get("box"):
            line["box"] = [
                [point[0] + origin_x, point[1] + origin_y]
                for point in line["box"]
            ]
        shifted.append(line)
    return shifted


def bind_ocr_lines(tree, lines, origin, min_overlap=0.35):
    """Attach screen-space OCR lines to the smallest containing UIA node.

    ``tree`` is mutated in place and also returned.  Each node receives
    ``ocr_text``, ``ocr_confidence``, ``ocr_lines``, ``uia_text``,
    ``effective_text`` and ``text_source`` for direct LLM consumption.
    """
    nodes = _flatten_tree(tree)
    for node in nodes:
        node["ocr_lines"] = []
        node["ocr_text"] = ""
        node["ocr_confidence"] = None

    origin_x, origin_y = origin
    stats = BindingStats(total=len(lines))
    unbound = []
    for line in lines:
        line = dict(line)
        bbox = line.get("bbox") or {}
        line_rect = (
            bbox.get("left", 0) + origin_x,
            bbox.get("top", 0) + origin_y,
            bbox.get("right", 0) + origin_x,
            bbox.get("bottom", 0) + origin_y,
        )
        screen_line = dict(line)
        screen_line["bbox"] = {
            "left": line_rect[0],
            "top": line_rect[1],
            "right": line_rect[2],
            "bottom": line_rect[3],
        }
        if screen_line.get("box"):
            screen_line["box"] = [
                [point[0] + origin_x, point[1] + origin_y]
                for point in screen_line["box"]
            ]

        target = _select_control(nodes, line_rect, min_overlap)
        if target is None:
            unbound.append(screen_line)
            continue
        target["ocr_lines"].append(screen_line)
        stats.bound += 1

    stats.unbound = len(unbound)
    for node in nodes:
        if node["ocr_lines"]:
            node["ocr_text"] = "\n".join(line["text"] for line in node["ocr_lines"])
            scores = [line.get("confidence", 0.0) for line in node["ocr_lines"]]
            node["ocr_confidence"] = round(sum(scores) / len(scores), 6)
        _apply_node_text(node)
    return stats, unbound
