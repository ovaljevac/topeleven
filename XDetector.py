import argparse
import json
import math
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_DIR, "pydeps"))

import cv2
import numpy as np
from PIL import ImageGrab


def _intersection(a, b):
    x1, y1, x2, y2 = a
    x3, y3, x4, y4 = b
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-6:
        return None
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / den
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / den
    return px, py


def _local_stat(gray, x, y, mode):
    h, w = gray.shape
    x0, x1 = max(0, x - 1), min(w, x + 2)
    y0, y1 = max(0, y - 1), min(h, y + 2)
    patch = gray[y0:y1, x0:x1]
    if patch.size == 0:
        return 127.0
    if mode == "max":
        return float(np.max(patch))
    if mode == "min":
        return float(np.min(patch))
    return float(np.median(patch))


def _x_contrast_score(gray, cx, cy):
    best_score = 0.0
    best_polarity = None

    # Very small close icons (roughly 16 px wide) use one-pixel antialiased
    # strokes.  Their arm brightness is lower after blurring, so evaluate a
    # compact scale separately while still requiring all four arms.
    for radius in range(3, 6):
        distances = range(2, radius + 1)
        bright_arms = [[], [], [], []]
        dark_arms = [[], [], [], []]
        axes = []

        for distance in distances:
            for arm, (sx, sy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
                x = int(round(cx + sx * distance))
                y = int(round(cy + sy * distance))
                bright_arms[arm].append(_local_stat(gray, x, y, "max"))
                dark_arms[arm].append(_local_stat(gray, x, y, "min"))
            for dx, dy in ((-distance, 0), (distance, 0), (0, -distance), (0, distance)):
                axes.append(_local_stat(gray, int(round(cx + dx)), int(round(cy + dy)), "median"))

        bright_value = min(float(np.mean(arm)) for arm in bright_arms)
        dark_value = max(float(np.mean(arm)) for arm in dark_arms)
        axis_value = float(np.mean(axes))
        center_bright = _local_stat(gray, int(round(cx)), int(round(cy)), "max")
        center_dark = _local_stat(gray, int(round(cx)), int(round(cy)), "min")

        bright_score = bright_value - axis_value
        if center_bright >= 135 and bright_value >= 105 and axis_value <= 145 and bright_score >= 35:
            best_score = max(best_score, bright_score * 3.1)
            if best_score == bright_score * 3.1:
                best_polarity = "bright-on-dark"

        dark_score = axis_value - dark_value
        if center_dark <= 120 and dark_value <= 135 and axis_value >= 145 and dark_score >= 35:
            scaled_score = dark_score * 3.1
            if scaled_score > best_score:
                best_score = scaled_score
                best_polarity = "dark-on-light"

    for radius in range(6, 19, 2):
        distances = range(max(3, radius // 3), radius + 1, 2)
        bright_arms = [[], [], [], []]
        dark_arms = [[], [], [], []]
        axes = []

        for distance in distances:
            for arm, (sx, sy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
                x = int(round(cx + sx * distance))
                y = int(round(cy + sy * distance))
                bright_arms[arm].append(_local_stat(gray, x, y, "max"))
                dark_arms[arm].append(_local_stat(gray, x, y, "min"))

            for dx, dy in ((-distance, 0), (distance, 0), (0, -distance), (0, distance)):
                axes.append(_local_stat(gray, int(round(cx + dx)), int(round(cy + dy)), "median"))

        if not axes:
            continue

        bright_arm_values = [float(np.mean(arm)) for arm in bright_arms]
        dark_arm_values = [float(np.mean(arm)) for arm in dark_arms]
        bright_value = min(bright_arm_values)
        dark_value = max(dark_arm_values)
        axis_value = float(np.mean(axes))
        center_bright = _local_stat(gray, int(round(cx)), int(round(cy)), "max")
        center_dark = _local_stat(gray, int(round(cx)), int(round(cy)), "min")

        bright_score = bright_value - axis_value
        if center_bright >= 185 and bright_value >= 175 and axis_value <= 175 and bright_score >= 38 and bright_score > best_score:
            best_score = bright_score
            best_polarity = "bright-on-dark"

        dark_score = axis_value - dark_value
        if center_dark <= 90 and dark_value <= 105 and axis_value >= 155 and dark_score >= 55 and dark_score > best_score:
            best_score = dark_score
            best_polarity = "dark-on-light"

    return best_score, best_polarity


def _x_shape_quality(gray, cx, cy, polarity):
    """Return 0..100 according to four balanced, continuous diagonal arms."""
    h, w = gray.shape
    best = 0.0

    def foreground_value(x, y):
        x0, x1 = max(0, int(round(x)) - 1), min(w, int(round(x)) + 2)
        y0, y1 = max(0, int(round(y)) - 1), min(h, int(round(y)) + 2)
        patch = gray[y0:y1, x0:x1]
        if patch.size == 0:
            return 127.0
        percentile = 70 if polarity == "bright-on-dark" else 30
        return float(np.percentile(patch, percentile))

    for radius in range(4, 22, 2):
        distances = list(range(max(2, radius // 3), radius + 1, 2))
        if len(distances) < 3:
            continue
        offset = max(2.0, radius * 0.24)
        arm_coverages = []
        arm_strengths = []

        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            hits = 0
            signals = []
            # Unit vector perpendicular to this diagonal arm.
            px, py = -sy / math.sqrt(2.0), sx / math.sqrt(2.0)
            for distance in distances:
                scale = distance / math.sqrt(2.0)
                x = cx + sx * scale
                y = cy + sy * scale
                fg = foreground_value(x, y)
                bg1 = _local_stat(gray, int(round(x + px * offset)), int(round(y + py * offset)), "median")
                bg2 = _local_stat(gray, int(round(x - px * offset)), int(round(y - py * offset)), "median")
                bg = (bg1 + bg2) / 2.0
                signal = fg - bg if polarity == "bright-on-dark" else bg - fg
                signals.append(signal)
                minimum_signal = 16.0 if radius < 8 else 22.0
                if signal >= minimum_signal:
                    hits += 1

            arm_coverages.append(hits / float(len(distances)))
            arm_strengths.append(float(np.mean(signals)))

        minimum_coverage = min(arm_coverages)
        average_coverage = float(np.mean(arm_coverages))
        coverage_balance = max(0.0, 1.0 - (max(arm_coverages) - minimum_coverage))
        minimum_strength = min(arm_strengths)
        strength_score = max(0.0, min(1.0, minimum_strength / 55.0))
        quality = 100.0 * (
            0.48 * minimum_coverage
            + 0.24 * average_coverage
            + 0.14 * coverage_balance
            + 0.14 * strength_score
        )
        best = max(best, quality)

    return best


def _response_centers(gray):
    source = gray.astype(np.float32)
    centers = []

    for radius in range(7, 22, 2):
        size = radius * 2 + 1
        diagonal = np.zeros((size, size), dtype=np.uint8)
        axes = np.zeros((size, size), dtype=np.uint8)
        thickness = max(1, radius // 5)

        cv2.line(diagonal, (2, 2), (size - 3, size - 3), 1, thickness)
        cv2.line(diagonal, (size - 3, 2), (2, size - 3), 1, thickness)
        cv2.line(axes, (3, radius), (size - 4, radius), 1, thickness)
        cv2.line(axes, (radius, 3), (radius, size - 4), 1, thickness)

        # The intersection belongs to both masks and carries no contrast data.
        cv2.circle(diagonal, (radius, radius), max(1, thickness), 0, -1)
        cv2.circle(axes, (radius, radius), max(1, thickness), 0, -1)
        kernel = diagonal.astype(np.float32) / max(1.0, float(np.sum(diagonal)))
        kernel -= axes.astype(np.float32) / max(1.0, float(np.sum(axes)))

        response = cv2.filter2D(source, cv2.CV_32F, kernel)
        response[:radius, :] = 0
        response[-radius:, :] = 0
        response[:, :radius] = 0
        response[:, -radius:] = 0

        for polarity in (1.0, -1.0):
            work = response * polarity
            for _ in range(3):
                _, maximum, _, location = cv2.minMaxLoc(work)
                if maximum < 24:
                    break
                centers.append((float(location[0]), float(location[1]), float(maximum)))
                cv2.circle(work, location, radius, 0, -1)

    return centers


def _detect_right_corner_x(bgr, live=False):
    height, width = bgr.shape[:2]
    if width < 200 or height < 120:
        return None

    # Some ad networks place the close pill slightly farther inward (around
    # 94.8% of the window width).  Leave enough pixels on both sides of the X
    # for the convolution kernels instead of putting its center on the ROI edge.
    # In portrait mode BlueStacks may keep a wide sidebar, so the app's own
    # top-right corner can sit much farther inward than the window corner.
    corner_start = 0.82 if height > width * 1.25 else 0.915
    left = int(width * corner_start)
    # The BlueStacks sidebar is not always visible (notably after returning
    # from Play Store in portrait ads).  Scan to the window edge; the titlebar
    # is excluded vertically and the final 14 px remain guarded below.
    right = width
    top = 42 if live else 24
    bottom = min(height, max(100, int(height * 0.12)))
    roi = bgr[top:bottom, left:right]
    if roi.size == 0:
        return None

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(gray, 45, 135)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180.0, threshold=8,
                            minLineLength=7, maxLineGap=4)
    positive = []
    negative = []
    raw_lines = [] if lines is None else np.asarray(lines).reshape(-1, 4)
    for raw in raw_lines:
        x1, y1, x2, y2 = map(float, raw)
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 7 or length > 75 or abs(dx) < 2:
            continue
        angle = math.degrees(math.atan2(dy, dx))
        normalized = ((angle + 90) % 180) - 90
        if 24 <= normalized <= 66:
            positive.append((x1, y1, x2, y2, length, normalized))
        elif -66 <= normalized <= -24:
            negative.append((x1, y1, x2, y2, length, normalized))

    candidates = []
    for pos in positive:
        for neg in negative:
            crossing = _intersection(pos[:4], neg[:4])
            if crossing is None:
                continue
            cx, cy = crossing
            if cx < 0 or cy < 0 or cx >= roi.shape[1] or cy >= roi.shape[0]:
                continue
            if cx + left > width - 14:
                continue

            p_mid = ((pos[0] + pos[2]) / 2.0, (pos[1] + pos[3]) / 2.0)
            n_mid = ((neg[0] + neg[2]) / 2.0, (neg[1] + neg[3]) / 2.0)
            midpoint_gap = math.hypot(p_mid[0] - n_mid[0], p_mid[1] - n_mid[1])
            average_length = (pos[4] + neg[4]) / 2.0
            if midpoint_gap > max(7.0, average_length * 0.55):
                continue
            if max(pos[4], neg[4]) / max(1.0, min(pos[4], neg[4])) > 2.7:
                continue

            contrast, polarity = _x_contrast_score(gray, cx, cy)
            if polarity is None:
                continue
            angle_score = 30.0 - abs(abs(pos[5]) - 45.0) - abs(abs(neg[5]) - 45.0)
            score = contrast + max(0.0, angle_score) - midpoint_gap
            if score < 210:
                continue
            shape_quality = _x_shape_quality(gray, cx, cy, polarity)
            candidates.append((score, cx + left, cy + top, polarity, "hough", shape_quality))

    response_candidates = sorted(
        _response_centers(gray), key=lambda candidate: candidate[2], reverse=True
    )
    for response_rank, (cx, cy, response_strength) in enumerate(response_candidates):
        if cx + left > width - 14:
            continue
        contrast, polarity = _x_contrast_score(gray, cx, cy)
        # Small thin X icons can shift the convolution peak by 2-3 pixels.
        # Refine only strong unresolved responses in a tiny neighborhood.
        if (
            polarity is None
            and response_strength >= 35
            and height > width * 1.25
            and response_rank < 4
        ):
            refined = None
            for offset_y in range(-3, 4):
                for offset_x in range(-3, 4):
                    refined_contrast, refined_polarity = _x_contrast_score(
                        gray, cx + offset_x, cy + offset_y
                    )
                    if refined_polarity is None:
                        continue
                    if refined is None or refined_contrast > refined[0]:
                        refined = (
                            refined_contrast,
                            refined_polarity,
                            cx + offset_x,
                            cy + offset_y,
                        )
            if refined is not None:
                contrast, polarity, cx, cy = refined
        if polarity is None:
            continue
        score = contrast + response_strength
        if score < 210:
            continue
        shape_quality = _x_shape_quality(gray, cx, cy, polarity)
        candidates.append((score, cx + left, cy + top, polarity, "response", shape_quality))

    if not candidates:
        return None

    # A real close icon must contain all four balanced diagonal arms.  This
    # rejects Play/next arrows and small ad-provider badges that can produce a
    # strong diagonal filter response but are not an X.
    candidates = [candidate for candidate in candidates if candidate[5] >= 82.0]
    if not candidates:
        return None

    score, cx, cy, polarity, method, shape_quality = max(candidates, key=lambda item: item[0])
    if score < 210:
        return None
    return {
        "found": True,
        "x": float(cx / width),
        "y": float(cy / height),
        "score": round(float(score), 2),
        "polarity": polarity,
        "method": method,
        "shape": round(float(shape_quality), 2),
    }


def detect_x(bgr, live=False):
    candidates = []

    right_result = _detect_right_corner_x(bgr, live=live)
    if right_result:
        candidates.append(right_result)

    flipped = cv2.flip(bgr, 1)
    left_result = _detect_right_corner_x(flipped, live=live)
    if left_result:
        left_result = dict(left_result)
        left_result["x"] = 1.0 - float(left_result["x"])
        left_result["side"] = "left"
        candidates.append(left_result)

    if not candidates:
        return None
    return max(candidates, key=lambda result: float(result.get("score", 0.0)))


def load_image(path):
    image = cv2.imread(path, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Cannot read image: {path}")
    return image


def capture_rect(rect):
    left, top, right, bottom = map(int, rect)
    rgb = np.asarray(ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def server_loop():
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if request.get("quit"):
                print(json.dumps({"ok": True}), flush=True)
                return
            if "rect" in request:
                image = capture_rect(request["rect"])
            else:
                image = load_image(request["image"])
            result = detect_x(image, live=("rect" in request)) or {"found": False}
            print(json.dumps(result), flush=True)
        except Exception as exc:
            print(json.dumps({"found": False, "error": str(exc)}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image")
    parser.add_argument("--server", action="store_true")
    args = parser.parse_args()

    if args.server:
        server_loop()
        return
    if not args.image:
        parser.error("--image or --server is required")
    print(json.dumps(detect_x(load_image(args.image)) or {"found": False}))


if __name__ == "__main__":
    main()
