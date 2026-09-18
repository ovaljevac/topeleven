import argparse
import json
import math
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for dependency_dir in (
    os.path.join(PROJECT_DIR, "pydeps"),
    os.path.join(os.path.dirname(PROJECT_DIR), "pydeps"),
):
    if os.path.isdir(dependency_dir):
        sys.path.insert(0, dependency_dir)

import cv2
import numpy as np
from PIL import ImageGrab


TV_REFERENCE_DIR = os.path.join(PROJECT_DIR, "za TV skriptu")
MOURINHO_REFERENCE_DIR = os.path.join(PROJECT_DIR, "Mourinho")
CAMPUS_REFERENCE_DIR = os.path.join(PROJECT_DIR, "Kampus")
ALLIANCE_REFERENCE_DIR = os.path.join(PROJECT_DIR, "Put saveza")
TRAINING_PLAYER_REFERENCE_DIR = os.path.join(PROJECT_DIR, "Trening igraca")
_TV_REFERENCE_FEATURES = None
_TV_WATCH_TEXT_TEMPLATES = None
_TV_CONTINUE_TEXT_TEMPLATE = None
_MOURINHO_REFERENCE_FEATURES = None
_CAMPUS_REFERENCE_FEATURES = None
_TRAINING_PLAYER_REFERENCE_FEATURES = None
_CAMPUS_100_TEXT_TEMPLATES = None
_ALLIANCE_ANCHOR_TEMPLATES = None
_ALLIANCE_GO_GLYPH_TEMPLATE = None
_ALLIANCE_IDI_TEXT_TEMPLATE = None


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

        # Some ad networks draw a white X directly on a bright yellow/green
        # panel.  The absolute background is bright, but the four white arms
        # still have clear local contrast.  Shape validation below keeps text
        # and provider logos from being accepted.
        if center_bright >= 235 and bright_value >= 225 and axis_value <= 235 and bright_score >= 22:
            color_background_score = 120.0 + (bright_score * 4.0)
            if color_background_score > best_score:
                best_score = color_background_score
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


def _looks_like_double_chevron(gray, cx, cy, polarity):
    """Recognize a bright >> control so it is not treated as a close X."""
    if polarity != "bright-on-dark":
        return False

    height, width = gray.shape
    x0, x1 = max(0, int(cx) - 32), min(width, int(cx) + 33)
    y0, y1 = max(0, int(cy) - 20), min(height, int(cy) + 21)
    patch = gray[y0:y1, x0:x1]
    if patch.size == 0:
        return False

    _, binary = cv2.threshold(patch, 200, 255, cv2.THRESH_BINARY)
    component_count, _, stats, centers = cv2.connectedComponentsWithStats(binary)
    chevrons = []
    for index in range(1, component_count):
        component_width = int(stats[index, cv2.CC_STAT_WIDTH])
        component_height = int(stats[index, cv2.CC_STAT_HEIGHT])
        area = int(stats[index, cv2.CC_STAT_AREA])
        if (
            4 <= component_width <= 14
            and 9 <= component_height <= 25
            and 20 <= area <= 150
            and component_width <= component_height
        ):
            chevrons.append((float(centers[index][0]), float(centers[index][1])))

    for first_index, first in enumerate(chevrons):
        for second in chevrons[first_index + 1:]:
            horizontal_gap = abs(first[0] - second[0])
            vertical_gap = abs(first[1] - second[1])
            if 5 <= horizontal_gap <= 18 and vertical_gap <= 5:
                return True
    return False


def _detect_double_chevron_control(bgr):
    """Detect a dedicated top-right >> control without mistaking Play pills."""
    height, width = bgr.shape[:2]
    if width < 200 or height < 120:
        return None

    left = int(width * (0.82 if height > width * 1.25 else 0.88))
    top = 24
    bottom = min(height, max(125, int(height * 0.20)))
    roi = bgr[top:bottom, left:width]
    if roi.size == 0:
        return None

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 195, 255, cv2.THRESH_BINARY)
    component_count, _, stats, centers = cv2.connectedComponentsWithStats(binary)
    chevrons = []
    combined_chevrons = []
    for index in range(1, component_count):
        component_width = int(stats[index, cv2.CC_STAT_WIDTH])
        component_height = int(stats[index, cv2.CC_STAT_HEIGHT])
        area = int(stats[index, cv2.CC_STAT_AREA])
        if (
            3 <= component_width <= 18
            and 7 <= component_height <= 30
            and 14 <= area <= 190
            and component_width <= component_height * 1.15
        ):
            chevrons.append((float(centers[index][0]), float(centers[index][1])))
        elif (
            14 <= component_width <= 32
            and 7 <= component_height <= 18
            and 40 <= area <= 220
            and 1.2 <= component_width / max(1.0, component_height) <= 3.2
        ):
            combined_chevrons.append((float(centers[index][0]), float(centers[index][1])))

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    def build_result(cx, cy):
        x0, x1 = max(0, int(cx) - 28), min(roi.shape[1], int(cx) + 29)
        y0, y1 = max(0, int(cy) - 20), min(roi.shape[0], int(cy) + 21)
        saturation = float(np.median(hsv[y0:y1, x0:x1, 1]))
        # Google Play pills also contain >> but have a saturated yellow
        # background. Only accept a neutral black/gray skip control.
        if saturation > 80:
            return None
        screen_x = cx + left
        screen_y = cy + top
        return {
            "found": True,
            "x": float(screen_x / width),
            "y": float(screen_y / height),
            "score": 500.0,
            "polarity": "bright-on-dark",
            "method": "double-chevron",
            "shape": 100.0,
            "kind": "skip",
        }

    for cx, cy in combined_chevrons:
        result = build_result(cx, cy)
        if result:
            return result

    for first_index, first in enumerate(chevrons):
        for second in chevrons[first_index + 1:]:
            horizontal_gap = abs(first[0] - second[0])
            vertical_gap = abs(first[1] - second[1])
            if not (4 <= horizontal_gap <= 22 and vertical_gap <= 7):
                continue
            cx = (first[0] + second[0]) / 2.0
            cy = (first[1] + second[1]) / 2.0
            result = build_result(cx, cy)
            if result:
                return result
    return None


def _matches_tiny_x_component(gray, cx, cy):
    """Validate a 4-10 px X without weakening the normal close detector."""
    height, width = gray.shape
    radius = 8
    x0, x1 = max(0, int(round(cx)) - radius), min(width, int(round(cx)) + radius + 1)
    y0, y1 = max(0, int(round(cy)) - radius), min(height, int(round(cy)) + radius + 1)
    patch = gray[y0:y1, x0:x1]
    if patch.size == 0:
        return False

    threshold = max(90.0, float(np.median(patch)) + 55.0)
    binary = np.where(patch >= threshold, 255, 0).astype(np.uint8)
    component_count, labels, stats, centers = cv2.connectedComponentsWithStats(binary)

    for index in range(1, component_count):
        component_width = int(stats[index, cv2.CC_STAT_WIDTH])
        component_height = int(stats[index, cv2.CC_STAT_HEIGHT])
        area = int(stats[index, cv2.CC_STAT_AREA])
        aspect = component_width / float(max(1, component_height))
        component_x = x0 + float(centers[index][0])
        component_y = y0 + float(centers[index][1])
        if not (
            4 <= component_width <= 10
            and 4 <= component_height <= 10
            and 10 <= area <= 45
            and 0.65 <= aspect <= 1.50
            and math.hypot(component_x - cx, component_y - cy) <= 3.0
        ):
            continue

        points_y, points_x = np.where(labels == index)
        relative_x = (points_x + x0) - cx
        relative_y = (points_y + y0) - cy
        quadrants = (
            np.any((relative_x <= -1) & (relative_y <= -1)),
            np.any((relative_x >= 1) & (relative_y <= -1)),
            np.any((relative_x <= -1) & (relative_y >= 1)),
            np.any((relative_x >= 1) & (relative_y >= 1)),
        )
        if all(quadrants):
            return True

    return False


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
    raw_gray = gray.copy()
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

    # Some portrait-ad overlays use a 6x6 px white X inside a roughly 20 px
    # dark circle. Blurring removes its one-pixel arms, so validate this very
    # specific top-right control on the raw grayscale image instead.
    if height > width * 1.25:
        game_right = max(1, width - 42)
        tiny_responses = sorted(
            _response_centers(raw_gray), key=lambda candidate: candidate[2], reverse=True
        )
        for cx, cy, response_strength in tiny_responses:
            screen_x = cx + left
            screen_y = cy + top
            if response_strength < 45:
                continue
            if not (game_right - 60 <= screen_x <= game_right - 6):
                continue
            if not (44 <= screen_y <= 86):
                continue
            contrast, polarity = _x_contrast_score(raw_gray, cx, cy)
            if polarity != "bright-on-dark" or contrast < 300:
                continue
            if not _matches_tiny_x_component(raw_gray, cx, cy):
                continue
            candidates.append((
                contrast + response_strength,
                screen_x,
                screen_y,
                polarity,
                "tiny-overlay",
                100.0,
            ))
            break

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
    kind = "skip" if _looks_like_double_chevron(gray, cx - left, cy - top, polarity) else "close"
    return {
        "found": True,
        "x": float(cx / width),
        "y": float(cy / height),
        "score": round(float(score), 2),
        "polarity": polarity,
        "method": method,
        "shape": round(float(shape_quality), 2),
        "kind": kind,
    }


def refine_close_x_near_point(bgr, normalized_x, normalized_y):
    """Find the geometric center of an X only near an AI-selected point."""
    height, width = bgr.shape[:2]
    if width < 80 or height < 80:
        return {"found": False, "reason": "image-too-small"}
    try:
        ai_x = float(normalized_x) * width
        ai_y = float(normalized_y) * height
    except (TypeError, ValueError):
        return {"found": False, "reason": "invalid-ai-point"}

    radius = int(max(24, min(64, round(min(width, height) * 0.075))))
    left = max(0, int(round(ai_x)) - radius)
    right = min(width, int(round(ai_x)) + radius + 1)
    top = max(0, int(round(ai_y)) - radius)
    bottom = min(height, int(round(ai_y)) + radius + 1)
    roi = bgr[top:bottom, left:right]
    if roi.size == 0:
        return {"found": False, "reason": "empty-roi"}

    raw_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(raw_gray, (3, 3), 0)
    candidates = []
    for gray, source in ((raw_gray, "raw-response"), (blurred, "blurred-response")):
        for cx, cy, response_strength in sorted(
            _response_centers(gray), key=lambda item: item[2], reverse=True
        )[:16]:
            contrast, polarity = _x_contrast_score(gray, cx, cy)
            if polarity is None:
                continue
            shape = _x_shape_quality(gray, cx, cy, polarity)
            if shape < 82.0:
                continue
            screen_x, screen_y = cx + left, cy + top
            distance = math.hypot(screen_x - ai_x, screen_y - ai_y)
            if distance > radius:
                continue
            score = float(contrast) + float(response_strength)
            if score < 190:
                continue
            rank = score + shape * 1.5 - distance * 1.2
            candidates.append((rank, screen_x, screen_y, score, shape, polarity, source, distance))

    if not candidates:
        return {
            "found": False,
            "reason": "no-balanced-x-near-ai-point",
            "radiusPixels": radius,
        }
    _, center_x, center_y, score, shape, polarity, method, distance = max(
        candidates, key=lambda item: item[0]
    )
    return {
        "found": True,
        "kind": "close",
        "x": float(center_x / width),
        "y": float(center_y / height),
        "score": round(score, 2),
        "shape": round(shape, 2),
        "polarity": polarity,
        "method": f"ai-local-{method}",
        "distancePixels": round(distance, 2),
        "radiusPixels": radius,
    }


def detect_x(bgr, live=False):
    candidates = []

    skip_result = _detect_double_chevron_control(bgr)

    right_result = _detect_right_corner_x(bgr, live=live)
    # Close/skip controls are only trusted in the guarded outer edge. This
    # rejects game artwork (for example the Kingshot logo around x=0.159)
    # even when its diagonals resemble an X for several consecutive frames.
    if right_result and float(right_result["x"]) >= 0.86:
        candidates.append(right_result)

    flipped = cv2.flip(bgr, 1)
    left_result = _detect_right_corner_x(flipped, live=live)
    if left_result:
        left_result = dict(left_result)
        left_result["x"] = 1.0 - float(left_result["x"])
        left_result["side"] = "left"
        if float(left_result["x"]) <= 0.14:
            candidates.append(left_result)

    # A geometrically verified X has priority over a skip/chevron candidate.
    # Reward-granted text can otherwise create a false double-chevron inside
    # the gray pill while the real circular X sits at its far-right edge.
    if candidates:
        return max(candidates, key=lambda result: float(result.get("score", 0.0)))
    return skip_result


def detect_top_resource_cards(bgr):
    """Detect Top Eleven's green, blue and red resource cards from pixels."""
    height, width = bgr.shape[:2]
    if width < 400 or height < 140:
        return {"found": False, "green": 0, "blue": 0, "red": 0}

    # Exclude the fixed BlueStacks toolbar on the right. The resource cards
    # occupy the upper-right part of the first ~50 px of the game viewport.
    game_width = max(1, width - 42)
    left = int(game_width * 0.42)
    right = min(width, int(game_width * 0.99))
    best = {"found": False, "green": 0, "blue": 0, "red": 0}

    # Small vertical search tolerates window borders and DPI/titlebar offsets.
    for top in range(38, 55, 4):
        bottom = min(height, top + 50)
        bar = bgr[top:bottom, left:right]
        if bar.size == 0:
            continue
        blue_channel, green_channel, red_channel = cv2.split(bar)
        green_count = int(np.count_nonzero(
            (green_channel > 125)
            & (green_channel > red_channel.astype(np.float32) * 1.18)
            & (green_channel > blue_channel.astype(np.float32) * 1.08)
        ))
        blue_count = int(np.count_nonzero(
            (blue_channel > 145)
            & (blue_channel > red_channel.astype(np.float32) * 1.20)
            & (blue_channel > green_channel.astype(np.float32) * 1.03)
        ))
        red_count = int(np.count_nonzero(
            (red_channel > 165)
            & (red_channel > green_channel.astype(np.float32) * 1.25)
            & (red_channel > blue_channel.astype(np.float32) * 1.18)
        ))
        candidate = {
            "found": green_count >= 100 and blue_count >= 70 and red_count >= 70,
            "green": green_count,
            "blue": blue_count,
            "red": red_count,
        }
        if min(green_count / 100.0, blue_count / 70.0, red_count / 70.0) > min(
            best["green"] / 100.0, best["blue"] / 70.0, best["red"] / 70.0
        ):
            best = candidate

    return best


def detect_top_edge_google_play_badge(bgr):
    """Locate the tiny Google Play disclosure badge at the ad's top-left edge."""
    height, width = bgr.shape[:2]
    if width < 260 or height < 180:
        return {"found": False}

    # Exclude the BlueStacks title bar (roughly the first 35-40 px) and the ad
    # artwork below. The badge is a compact group of pale text/icon pixels.
    top = max(34, int(height * 0.052))
    bottom = min(height, max(top + 22, int(height * 0.112)))
    right = min(width, max(100, int(width * 0.35)))
    roi = bgr[top:bottom, 0:right]
    if roi.size == 0:
        return {"found": False}

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    pale = cv2.inRange(hsv, np.array([0, 0, 145]), np.array([180, 115, 255]))
    # Join the Google triangle and the short "Google Play" text into one box.
    pale = cv2.morphologyEx(pale, cv2.MORPH_CLOSE, np.ones((3, 9), np.uint8))
    pale = cv2.dilate(pale, np.ones((3, 5), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(pale)
    candidates = []
    for index in range(1, count):
        x, y, badge_width, badge_height, area = map(int, stats[index])
        if not (
            30 <= badge_width <= 105
            and 7 <= badge_height <= 24
            and area >= 110
            and y <= max(20, int((bottom - top) * 0.58))
            and x <= int(right * 0.55)
        ):
            continue
        center_x = x + badge_width / 2.0
        center_y = top + y + badge_height / 2.0
        candidates.append((area, center_x, center_y, badge_width, badge_height))

    if not candidates:
        return {"found": False}
    _, center_x, center_y, badge_width, badge_height = max(candidates)
    return {
        "found": True,
        "kind": "google_play",
        "x": float(center_x / width),
        "y": float(center_y / height),
        "width": int(badge_width),
        "height": int(badge_height),
        "method": "top-left-google-play-badge",
    }


def detect_yellow_ad_control(bgr):
    """Detect yellow controls and the neutral Google Play counter badge."""
    height, width = bgr.shape[:2]
    if width < 300 or height < 140:
        return {"found": False}

    game_right = max(1, width - 42)
    left = int(game_right * 0.72)
    top = 38
    bottom = min(height, max(145, int(height * 0.22)))
    roi = bgr[top:bottom, left:game_right]
    if roi.size == 0:
        return {"found": False}
    roi_height, roi_width = roi.shape[:2]

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    # Keep the orange-yellow control separate from lime/green gameplay
    # backgrounds. Lower saturation includes the pale button fill; the narrow
    # hue band prevents it from merging with the whole ad scene.
    yellow = cv2.inRange(hsv, np.array([14, 35, 170]), np.array([32, 255, 255]))
    yellow = cv2.morphologyEx(yellow, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(yellow, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    candidates = []

    for contour in contours:
        x, y, control_width, control_height = cv2.boundingRect(contour)
        area = float(cv2.contourArea(contour))
        if control_width < 18 or control_height < 16 or area < 220:
            continue
        cx = float(left + x + control_width / 2.0)
        cy = float(top + y + control_height / 2.0)
        aspect = control_width / float(max(1, control_height))

        # A full yellow ad background used to look like one very wide Play
        # pill. A real badge is a bounded component with margins, white text or
        # chevrons, and occupies only a small part of this corner ROI.
        box_area = float(control_width * control_height)
        roi_fraction = box_area / float(max(1, roi_width * roi_height))
        touches_edge = (
            x <= 2
            or y <= 2
            or x + control_width >= roi_width - 2
            or y + control_height >= roi_height - 2
        )
        control_hsv = hsv[y:y + control_height, x:x + control_width]
        white_ratio = 0.0
        if control_hsv.size:
            white_pixels = np.count_nonzero(
                (control_hsv[:, :, 1] < 75) & (control_hsv[:, :, 2] > 205)
            )
            white_ratio = white_pixels / box_area

        if (
            2.4 <= aspect <= 8.0
            and 85 <= control_width <= 240
            and 20 <= control_height <= 65
            and roi_fraction <= 0.25
            and not touches_edge
            and area >= box_area * 0.45
            and white_ratio >= 0.025
            and 0.80 <= cx / float(width) <= 0.97
            and 0.05 <= cy / float(height) <= 0.18
        ):
            candidates.append((area, "google_play", cx, cy, control_width, control_height, "yellow-pill"))
            continue

        if 0.72 <= aspect <= 1.38 and 20 <= control_width <= 70 and 20 <= control_height <= 70:
            refined = None
            for offset_y in range(-3, 4):
                for offset_x in range(-3, 4):
                    test_x, test_y = cx + offset_x, cy + offset_y
                    contrast, polarity = _x_contrast_score(gray, test_x, test_y)
                    if polarity is None:
                        continue
                    shape = _x_shape_quality(gray, test_x, test_y, polarity)
                    quality = shape + min(contrast, 300.0) * 0.05
                    if refined is None or quality > refined[0]:
                        refined = (quality, contrast, shape, test_x, test_y)
            if refined is not None:
                _, contrast, shape, refined_x, refined_y = refined
                if contrast >= 150 and shape >= 78:
                    candidates.append((
                        area + contrast,
                        "close",
                        refined_x,
                        refined_y,
                        control_width,
                        control_height,
                        "yellow-close",
                    ))

    # Some playable ads use a gray Google Play counter rather than a yellow
    # pill. Its stable signature is a wide dark rounded panel with a white
    # border and a circular orange/yellow coin in the right half. Requiring
    # the coin distinguishes it from a normal >> skip control.
    neutral_border = cv2.inRange(
        hsv, np.array([0, 0, 170]), np.array([180, 85, 255])
    )
    neutral_border = cv2.morphologyEx(
        neutral_border, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)
    )
    neutral_border = cv2.dilate(neutral_border, np.ones((3, 3), np.uint8))
    neutral_contours, _ = cv2.findContours(
        neutral_border, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    for contour in neutral_contours:
        x, y, control_width, control_height = cv2.boundingRect(contour)
        area = float(cv2.contourArea(contour))
        aspect = control_width / float(max(1, control_height))
        cx = float(left + x + control_width / 2.0)
        cy = float(top + y + control_height / 2.0)
        if not (
            2.15 <= aspect <= 4.5
            and 90 <= control_width <= 190
            and 34 <= control_height <= 75
            and area >= control_width * control_height * 0.35
            and 0.82 <= cx / float(width) <= 0.97
            and 0.05 <= cy / float(height) <= 0.19
        ):
            continue

        panel_hsv = hsv[y:y + control_height, x:x + control_width]
        orange = cv2.inRange(
            panel_hsv, np.array([8, 100, 150]), np.array([35, 255, 255])
        )
        component_count, _, stats, centers = cv2.connectedComponentsWithStats(orange)
        coin_found = False
        for index in range(1, component_count):
            coin_width = int(stats[index, cv2.CC_STAT_WIDTH])
            coin_height = int(stats[index, cv2.CC_STAT_HEIGHT])
            coin_area = int(stats[index, cv2.CC_STAT_AREA])
            coin_aspect = coin_width / float(max(1, coin_height))
            coin_center_x = float(centers[index][0])
            if (
                12 <= coin_width <= 45
                and 12 <= coin_height <= 45
                and coin_area >= 90
                and 0.65 <= coin_aspect <= 1.50
                and coin_center_x >= control_width * 0.55
            ):
                coin_found = True
                break
        if coin_found:
            candidates.append((area, "google_play", cx, cy, control_width, control_height, "neutral-counter"))

    if not candidates:
        return detect_top_edge_google_play_badge(bgr)

    # Closing the ad always has priority if a Play pill and an X coexist.
    close_controls = [candidate for candidate in candidates if candidate[1] == "close"]
    google_play = [candidate for candidate in candidates if candidate[1] == "google_play"]
    selected = max(close_controls or google_play or candidates, key=lambda item: item[0])
    _, kind, cx, cy, control_width, control_height, method = selected
    return {
        "found": True,
        "kind": kind,
        "x": float(cx / width),
        "y": float(cy / height),
        "width": int(control_width),
        "height": int(control_height),
        "method": method,
    }


def detect_play_destination(bgr):
    """Detect a blank play.google.com Chrome Custom Tab and its close X."""
    height, width = bgr.shape[:2]
    if width < 400 or height < 300:
        return {"found": False}

    game_right = max(1, width - 42)
    header_top = 40
    header_bottom = min(height, max(145, int(height * 0.20)))
    body_top = header_bottom
    header = bgr[header_top:header_bottom, 0:game_right]
    body = bgr[body_top:max(body_top + 1, height - 8), 8:max(9, game_right - 8)]
    if header.size == 0 or body.size == 0:
        return {"found": False}

    header_white_ratio = float(np.mean(np.all(header >= 235, axis=2)))
    body_white_ratio = float(np.mean(np.all(body >= 235, axis=2)))
    if header_white_ratio < 0.90 or body_white_ratio < 0.95:
        return {
            "found": False,
            "header_white": round(header_white_ratio, 4),
            "body_white": round(body_white_ratio, 4),
        }

    full_gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    def dark_ratio(x0, y0, x1, y1):
        zone = full_gray[
            max(0, int(height * y0)):min(height, int(height * y1)),
            max(0, int(game_right * x0)):min(game_right, int(game_right * x1)),
        ]
        if zone.size == 0:
            return 0.0
        return float(np.mean(zone < 80))

    chevron_dark = dark_ratio(0.045, 0.115, 0.085, 0.170)
    address_dark = dark_ratio(0.095, 0.115, 0.250, 0.170)
    right_controls_dark = dark_ratio(0.885, 0.110, 0.975, 0.175)
    if chevron_dark < 0.008 or address_dark < 0.012 or right_controls_dark < 0.008:
        return {
            "found": False,
            "header_white": round(header_white_ratio, 4),
            "body_white": round(body_white_ratio, 4),
            "chevron_dark": round(chevron_dark, 4),
            "address_dark": round(address_dark, 4),
            "right_dark": round(right_controls_dark, 4),
        }

    # Chrome Custom Tabs put a dark X around (29, 104) at this DPI. Require
    # the full X shape as well as the white header/body so white ads cannot
    # trigger this fallback.
    close_left, close_right = 5, min(game_right, 78)
    close_top, close_bottom = 78, min(height, 132)
    close_roi = bgr[close_top:close_bottom, close_left:close_right]
    if close_roi.size == 0:
        return {"found": False}
    close_gray = cv2.cvtColor(close_roi, cv2.COLOR_BGR2GRAY)
    close_gray = cv2.GaussianBlur(close_gray, (3, 3), 0)
    response_candidates = sorted(
        _response_centers(close_gray), key=lambda candidate: candidate[2], reverse=True
    )
    for cx, cy, response_strength in response_candidates:
        screen_x = cx + close_left
        screen_y = cy + close_top
        if response_strength < 50:
            continue
        if not (15 <= screen_x <= 50 and 90 <= screen_y <= 120):
            continue
        contrast, polarity = _x_contrast_score(close_gray, cx, cy)
        if polarity is None or contrast < 200:
            continue
        shape = _x_shape_quality(close_gray, cx, cy, polarity)
        if shape < 80:
            continue
        return {
            "found": True,
            "x": float(screen_x / width),
            "y": float(screen_y / height),
            "score": round(float(contrast + response_strength), 2),
            "shape": round(float(shape), 2),
            "header_white": round(header_white_ratio, 4),
            "body_white": round(body_white_ratio, 4),
            "chevron_dark": round(chevron_dark, 4),
            "address_dark": round(address_dark, 4),
            "right_dark": round(right_controls_dark, 4),
        }

    return {
        "found": False,
        "header_white": round(header_white_ratio, 4),
        "body_white": round(body_white_ratio, 4),
    }


def _tv_feature(bgr):
    height, width = bgr.shape[:2]
    game_right = max(1, width - 42)
    top = min(height - 1, 35)
    return cv2.resize(
        bgr[top:height, 0:game_right], (96, 54), interpolation=cv2.INTER_AREA
    ).astype(np.float32)


def _tv_reference_features():
    global _TV_REFERENCE_FEATURES
    if _TV_REFERENCE_FEATURES is not None:
        return _TV_REFERENCE_FEATURES
    features = {}
    for index in range(1, 6):
        path = os.path.join(TV_REFERENCE_DIR, f"{index}.png")
        reference = cv2.imread(path, cv2.IMREAD_COLOR)
        if reference is not None:
            features[index] = _tv_feature(reference)
    _TV_REFERENCE_FEATURES = features
    return features


def _tv_watch_text_templates():
    global _TV_WATCH_TEXT_TEMPLATES
    if _TV_WATCH_TEXT_TEMPLATES is not None:
        return _TV_WATCH_TEXT_TEMPLATES
    reference = cv2.imread(os.path.join(TV_REFERENCE_DIR, "2.png"), cv2.IMREAD_COLOR)
    templates = []
    if reference is not None:
        for x in (85, 283, 482):
            crop = reference[558:588, x:x + 110]
            if crop.size:
                templates.append(np.all(crop >= 190, axis=2).astype(np.uint8))
    mourinho_reference = cv2.imread(
        os.path.join(MOURINHO_REFERENCE_DIR, "2.png"), cv2.IMREAD_COLOR
    )
    if mourinho_reference is not None:
        crop = mourinho_reference[341:369, 725:842]
        if crop.size:
            templates.append(np.all(crop >= 190, axis=2).astype(np.uint8))
    _TV_WATCH_TEXT_TEMPLATES = templates
    return templates


def _tv_watch_text_score(button_bgr):
    """Match the white play icon and POGLEDAJ glyphs, not only blue color."""
    if button_bgr.size == 0:
        return 0.0
    observed = np.all(button_bgr >= 190, axis=2).astype(np.uint8)
    if int(np.sum(observed)) < 120:
        return 0.0
    scores = []
    for template in _tv_watch_text_templates():
        resized = cv2.resize(
            template, (observed.shape[1], observed.shape[0]), interpolation=cv2.INTER_NEAREST
        )
        score = cv2.matchTemplate(
            observed.astype(np.float32), resized.astype(np.float32), cv2.TM_CCOEFF_NORMED
        )[0, 0]
        if np.isfinite(score):
            scores.append(float(score))
    return max(scores, default=0.0)


def _tight_white_glyph_signature(bgr):
    if bgr.size == 0:
        return None
    white = np.all(bgr >= 190, axis=2).astype(np.uint8)
    ys, xs = np.where(white > 0)
    if len(xs) < 55:
        return None
    x1, x2 = int(xs.min()), int(xs.max()) + 1
    y1, y2 = int(ys.min()), int(ys.max()) + 1
    glyph = white[y1:y2, x1:x2]
    if glyph.shape[0] < 6 or glyph.shape[1] < 20:
        return None
    return cv2.resize(glyph, (120, 24), interpolation=cv2.INTER_NEAREST)


def _tv_continue_text_template():
    global _TV_CONTINUE_TEXT_TEMPLATE
    if _TV_CONTINUE_TEXT_TEMPLATE is not None:
        return _TV_CONTINUE_TEXT_TEMPLATE
    reference = cv2.imread(os.path.join(TV_REFERENCE_DIR, "5.png"), cv2.IMREAD_COLOR)
    _TV_CONTINUE_TEXT_TEMPLATE = (
        _tight_white_glyph_signature(reference[573:608, 301:539])
        if reference is not None else None
    )
    return _TV_CONTINUE_TEXT_TEMPLATE


def _tv_continue_text_score(button_bgr):
    observed = _tight_white_glyph_signature(button_bgr)
    template = _tv_continue_text_template()
    if observed is None or template is None:
        return 0.0
    score = cv2.matchTemplate(
        observed.astype(np.float32), template.astype(np.float32), cv2.TM_CCOEFF_NORMED
    )[0, 0]
    return float(score) if np.isfinite(score) else 0.0


def detect_tv_flow(bgr):
    """Classify the five documented TV screens and locate active POGLEDAJ buttons."""
    height, width = bgr.shape[:2]
    if width < 600 or height < 400:
        return {
            "found": False,
            "state": "unknown",
            "buttons": [],
            "tvButton": None,
            "continueButton": None,
        }

    feature = _tv_feature(bgr)
    distances = {
        index: float(np.mean(np.abs(feature - reference)))
        for index, reference in _tv_reference_features().items()
    }
    nearest = min(distances, key=distances.get) if distances else None
    nearest_distance = distances.get(nearest, 999.0)

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    # The top resource widths change with account values, shifting the TV,
    # friends and chat buttons horizontally. Detect the white monitor/play
    # glyph and use its actual center instead of a fixed X coordinate.
    tv_button = None
    white = cv2.inRange(hsv, np.array([0, 0, 175]), np.array([179, 85, 255]))
    white_count, _, white_stats, white_centers = cv2.connectedComponentsWithStats(white)
    tv_candidates = []
    for stat, center in zip(white_stats[1:white_count], white_centers[1:white_count]):
        _, _, component_width, component_height, area = map(int, stat)
        aspect = component_width / float(max(1, component_height))
        normalized_x = float(center[0] / width)
        normalized_y = float(center[1] / height)
        if not (0.70 <= normalized_x <= 0.90 and 0.11 <= normalized_y <= 0.20):
            continue
        if not (width * 0.018 <= component_width <= width * 0.040):
            continue
        if not (height * 0.025 <= component_height <= height * 0.055):
            continue
        if not (1.05 <= aspect <= 1.60) or area < 120:
            continue
        tv_candidates.append((normalized_x, normalized_y, area))
    if tv_candidates:
        tv_x, tv_y, _ = min(tv_candidates)
        tv_button = {"x": tv_x, "y": tv_y}

    cyan = cv2.inRange(hsv, np.array([85, 70, 100]), np.array([115, 255, 255]))
    count, _, stats, centers = cv2.connectedComponentsWithStats(cyan)
    buttons = []
    for stat, center in zip(stats[1:count], centers[1:count]):
        x, y, component_width, component_height, area = map(int, stat)
        if not (height * 0.78 <= y <= height * 0.95):
            continue
        if not (width * 0.07 <= component_width <= width * 0.16):
            continue
        if not (height * 0.025 <= component_height <= height * 0.09):
            continue
        if area < 700:
            continue
        button_roi = bgr[y:y + component_height, x:x + component_width]
        text_score = _tv_watch_text_score(button_roi)
        if text_score < 0.55:
            continue
        cx, cy = map(float, center)
        normalized_x = cx / width
        buttons.append(
            {
                "x": normalized_x,
                "y": cy / height,
                "manual": 0.39 <= normalized_x <= 0.58,
                "textScore": round(text_score, 3),
            }
        )
    buttons.sort(key=lambda button: button["x"])

    # NASTAVI is sometimes a normal left button and sometimes spans almost
    # the full bottom width. Match the tight white glyphs independently of
    # the green component width so both layouts share one dynamic locator.
    continue_button = None
    green = cv2.inRange(hsv, np.array([35, 70, 90]), np.array([90, 255, 255]))
    green_count, _, green_stats, green_centers = cv2.connectedComponentsWithStats(green)
    for stat, center in zip(green_stats[1:green_count], green_centers[1:green_count]):
        x, y, component_width, component_height, area = map(int, stat)
        normalized_x = float(center[0] / width)
        normalized_y = float(center[1] / height)
        if not (0.02 <= normalized_x <= 0.98 and 0.86 <= normalized_y <= 0.99):
            continue
        if not (width * 0.18 <= component_width <= width * 0.96):
            continue
        if not (height * 0.035 <= component_height <= height * 0.10):
            continue
        if area < 2500:
            continue
        text_score = _tv_continue_text_score(
            bgr[y:y + component_height, x:x + component_width]
        )
        if text_score < 0.65:
            continue
        continue_button = {
            "x": normalized_x,
            "y": normalized_y,
            "textScore": round(text_score, 3),
        }
        break

    state = "unknown"
    if buttons or (nearest == 2 and nearest_distance <= 55):
        state = "tv"
    elif continue_button is not None:
        state = "manual_5"
    elif nearest in (3, 4, 5) and nearest_distance <= 38:
        state = f"manual_{nearest}"
    elif (
        tv_button is not None and detect_top_resource_cards(bgr)["found"]
    ) or (nearest == 1 and nearest_distance <= 45):
        state = "home"

    return {
        "found": state != "unknown",
        "state": state,
        "buttons": buttons if state == "tv" else [],
        "tvButton": tv_button if state == "home" else None,
        "continueButton": continue_button if state == "manual_5" else None,
        "referenceDistance": round(nearest_distance, 2),
    }


def _mourinho_reference_features():
    global _MOURINHO_REFERENCE_FEATURES
    if _MOURINHO_REFERENCE_FEATURES is not None:
        return _MOURINHO_REFERENCE_FEATURES
    features = {}
    for index in (1, 2):
        reference = cv2.imread(
            os.path.join(MOURINHO_REFERENCE_DIR, f"{index}.png"), cv2.IMREAD_COLOR
        )
        if reference is not None:
            features[index] = _tv_feature(reference)
    _MOURINHO_REFERENCE_FEATURES = features
    return features


def detect_mourinho_flow(bgr):
    """Recognize the readiness warning and its verified POGLEDAJ popup."""
    height, width = bgr.shape[:2]
    if width < 600 or height < 400:
        return {"found": False, "state": "unknown", "button": None}

    feature = _tv_feature(bgr)
    distances = {
        index: float(np.mean(np.abs(feature - reference)))
        for index, reference in _mourinho_reference_features().items()
    }
    nearest = min(distances, key=distances.get) if distances else None
    nearest_distance = distances.get(nearest, 999.0)

    button = None
    warning = None
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    cyan = cv2.inRange(hsv, np.array([85, 70, 100]), np.array([115, 255, 255]))
    count, _, stats, centers = cv2.connectedComponentsWithStats(cyan)
    for stat, center in zip(stats[1:count], centers[1:count]):
        x, y, component_width, component_height, area = map(int, stat)
        normalized_x = float(center[0] / width)
        normalized_y = float(center[1] / height)
        if not (0.55 <= normalized_x <= 0.85 and 0.45 <= normalized_y <= 0.68):
            continue
        if not (width * 0.07 <= component_width <= width * 0.16):
            continue
        if not (height * 0.025 <= component_height <= height * 0.09):
            continue
        if area < 700:
            continue
        text_score = _tv_watch_text_score(
            bgr[y:y + component_height, x:x + component_width]
        )
        if text_score < 0.55:
            continue
        button = {
            "x": normalized_x,
            "y": normalized_y,
            "textScore": round(text_score, 3),
        }
        break

    # The readiness row can move in both axes and its warning can be red with
    # a white glyph or yellow with a dark glyph. Prefer the small saturated
    # square immediately to the right of the readiness bar and click its
    # center. Choosing the rightmost square avoids the segmented green bar.
    warning_region_left = int(width * 0.44)
    warning_region_right = int(width * 0.63)
    warning_region_top = int(height * 0.75)
    warning_region = bgr[
        warning_region_top:height, warning_region_left:warning_region_right
    ]
    if warning_region.size:
        warning_hsv = cv2.cvtColor(warning_region, cv2.COLOR_BGR2HSV)
        warning_color = cv2.inRange(
            warning_hsv, np.array([0, 65, 80]), np.array([179, 255, 255])
        )
        color_count, _, color_stats, color_centers = cv2.connectedComponentsWithStats(
            warning_color
        )
        color_candidates = []
        for stat, center in zip(color_stats[1:color_count], color_centers[1:color_count]):
            _, _, component_width, component_height, area = map(int, stat)
            aspect = component_width / float(max(1, component_height))
            if not (width * 0.018 <= component_width <= width * 0.043):
                continue
            if not (height * 0.022 <= component_height <= height * 0.070):
                continue
            if not (0.65 <= aspect <= 1.60) or area < 120:
                continue
            screen_x = warning_region_left + float(center[0])
            screen_y = warning_region_top + float(center[1])
            normalized_x = screen_x / width
            normalized_y = screen_y / height
            if not (0.49 <= normalized_x <= 0.59 and 0.78 <= normalized_y <= 0.995):
                continue
            color_candidates.append((normalized_x, area, normalized_y))
        if color_candidates:
            warning_x, _, warning_y = max(color_candidates)
            warning = {"x": warning_x, "y": warning_y}

    # When a short window clips/merges the colored square with the readiness
    # bar, fall back to the visible white vertical stroke of the ! glyph. Its
    # dot is optional because it may be below the visible window.
    warning_left = int(width * 0.47)
    warning_right = int(width * 0.61)
    warning_top = int(height * 0.82)
    warning_roi = bgr[warning_top:height, warning_left:warning_right]
    if warning is None and warning_roi.size:
        warning_white = cv2.inRange(
            warning_roi, np.array([190, 190, 190]), np.array([255, 255, 255])
        )
        warning_count, _, warning_stats, warning_centers = (
            cv2.connectedComponentsWithStats(warning_white)
        )
        warning_candidates = []
        for stat, center in zip(warning_stats[1:warning_count], warning_centers[1:warning_count]):
            x, y, component_width, component_height, area = map(int, stat)
            if not (2 <= component_width <= 6 and 8 <= component_height <= 18):
                continue
            if area < 18:
                continue
            screen_x = warning_left + float(center[0])
            screen_y = warning_top + float(center[1])
            normalized_x = screen_x / width
            normalized_y = screen_y / height
            if not (0.49 <= normalized_x <= 0.59 and 0.84 <= normalized_y <= 0.995):
                continue
            warning_candidates.append((area, normalized_x, normalized_y))
        if warning_candidates:
            _, warning_x, warning_y = max(warning_candidates)
            warning = {"x": warning_x, "y": warning_y}

    state = "unknown"
    if button is not None or (nearest == 2 and nearest_distance <= 45):
        state = "mourinho_popup"
    elif warning is not None or (nearest == 1 and nearest_distance <= 45):
        state = "mourinho_home"

    return {
        "found": state != "unknown",
        "state": state,
        "button": button if state == "mourinho_popup" else None,
        "warning": warning if state == "mourinho_home" else None,
        "referenceDistance": round(nearest_distance, 2),
    }


def _campus_reference_features():
    global _CAMPUS_REFERENCE_FEATURES
    if _CAMPUS_REFERENCE_FEATURES is not None:
        return _CAMPUS_REFERENCE_FEATURES
    features = {}
    for index in (3, 4, 5, 6):
        reference = cv2.imread(
            os.path.join(CAMPUS_REFERENCE_DIR, f"{index}.png"), cv2.IMREAD_COLOR
        )
        if reference is not None:
            features[index] = _tv_feature(reference)
    _CAMPUS_REFERENCE_FEATURES = features
    return features


def _campus_100_text_templates():
    global _CAMPUS_100_TEXT_TEMPLATES
    if _CAMPUS_100_TEXT_TEMPLATES is not None:
        return _CAMPUS_100_TEXT_TEMPLATES
    templates = []
    for index, crop_box in (
        (5, (918, 462, 1034, 496)),
        (6, (930, 465, 1045, 500)),
    ):
        reference = cv2.imread(
            os.path.join(CAMPUS_REFERENCE_DIR, f"{index}.png"), cv2.IMREAD_COLOR
        )
        if reference is None:
            continue
        x1, y1, x2, y2 = crop_box
        crop = reference[y1:y2, x1:x2]
        if crop.size:
            templates.append(np.all(crop >= 190, axis=2).astype(np.uint8))
    _CAMPUS_100_TEXT_TEMPLATES = templates
    return templates


def _campus_100_text_score(button_bgr):
    if button_bgr.size == 0:
        return 0.0
    observed = np.all(button_bgr >= 190, axis=2).astype(np.uint8)
    if int(np.sum(observed)) < 80:
        return 0.0
    scores = []
    for template in _campus_100_text_templates():
        resized = cv2.resize(
            template, (observed.shape[1], observed.shape[0]), interpolation=cv2.INTER_NEAREST
        )
        score = cv2.matchTemplate(
            observed.astype(np.float32), resized.astype(np.float32), cv2.TM_CCOEFF_NORMED
        )[0, 0]
        if np.isfinite(score):
            scores.append(float(score))
    return max(scores, default=0.0)


def _campus_maintenance_badges(bgr):
    """Find the repeated green percentage/status badges on the Campus map.

    The Campus camera slowly pans and zooms, so a whole-frame reference can
    alternate between the normal and maintenance views even though the green
    percentage badges make the maintenance view unambiguous.  These filters
    deliberately describe the repeated badge geometry rather than any fixed
    screen coordinate.
    """
    height, width = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(
        hsv,
        np.array([35, 100, 100]),
        np.array([95, 255, 255]),
    )
    green = cv2.morphologyEx(
        green, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)
    )
    count, _, stats, centers = cv2.connectedComponentsWithStats(green)
    badges = []
    frame_area = float(max(1, width * height))
    for stat, center in zip(stats[1:count], centers[1:count]):
        x, y, component_width, component_height, area = map(int, stat)
        normalized_x = float(center[0] / width)
        normalized_y = float(center[1] / height)
        aspect = component_width / float(max(1, component_height))
        fill = area / float(max(1, component_width * component_height))
        if not (0.04 <= normalized_x <= 0.90 and 0.25 <= normalized_y <= 0.90):
            continue
        if not (width * 0.04 <= component_width <= width * 0.11):
            continue
        if not (height * 0.018 <= component_height <= height * 0.060):
            continue
        if not (2.20 <= aspect <= 5.50):
            continue
        if area < frame_area * 0.0009 or fill < 0.68:
            continue
        badges.append({
            "x": normalized_x,
            "y": normalized_y,
            "width": component_width / float(width),
            "height": component_height / float(height),
        })
    return badges


def _campus_object_strip(bgr):
    height, width = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([35, 90, 100]), np.array([85, 255, 255]))
    mask[:int(height * .72)] = 0
    mask[int(height * .86):] = 0
    mask[:, int(width * .50):] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 5), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    cards = []
    for x, y, w, h, area in stats[1:count]:
        x, y, w, h = map(int, (x, y, w, h))
        if not (.060 * width <= w <= .12 * width and .025 * height <= h <= .06 * height):
            continue
        if x < width * .018 or x + w >= width * .48 or area < w * h * .65:
            continue
        tail = 0
        for column in range(x + w, min(int(width * .50), x + w + int(width * .035))):
            pixels = bgr[y + 2:y + h - 2, column]
            if not pixels.size or np.mean(np.all(pixels >= 175, axis=1)) < .65:
                if tail == 0 and column < x + w + 3:
                    continue
                break
            tail += 1
        if x + w + tail >= width * .495:
            continue
        thumbnail = bgr[y+h:min(height, y+h+int(height*.11)), x:x+w+tail]
        identity = cv2.resize(cv2.cvtColor(thumbnail, cv2.COLOR_BGR2GRAY), (16, 8)).flatten().tolist()
        cards.append({"identity": identity, "x": (x + (w + tail) / 2) / width,
                      "y": min(.92, (y + h + height * .055) / height),
                      "incomplete": tail >= width * .004})
    cards.sort(key=lambda card: card["x"])
    panel = hsv[int(height * .26):int(height * .94), int(width * .53):int(width * .94)]
    panel_ready = bool(panel.size and np.mean((panel[:, :, 1] < 65) & (panel[:, :, 2] > 190)) > .60)
    roi = bgr[int(height * .74):int(height * .94), int(width * .02):int(width * .49)]
    fingerprint = cv2.resize(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), (32, 8)).flatten().tolist()
    return {"verified": panel_ready and len(cards) >= 2, "cards": cards, "fingerprint": fingerprint}


def detect_campus_flow(bgr):
    """Classify Campus screens and verify the exact blue 100% ad button."""
    height, width = bgr.shape[:2]
    if width < 600 or height < 400:
        return {
            "found": False,
            "state": "unknown",
            "toolButton": None,
            "hundredButton": None,
            "hundredButtonVisible": None,
            "maintenanceBadgeCount": 0,
        }

    feature = _tv_feature(bgr)
    distances = {
        index: float(np.mean(np.abs(feature - reference)))
        for index, reference in _campus_reference_features().items()
    }
    nearest = min(distances, key=distances.get) if distances else None
    nearest_distance = distances.get(nearest, 999.0)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    maintenance_badges = _campus_maintenance_badges(bgr)

    tool_button = None
    bright = cv2.inRange(hsv, np.array([0, 0, 215]), np.array([179, 55, 255]))
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    count, _, stats, centers = cv2.connectedComponentsWithStats(bright)
    tool_candidates = []
    for stat, center in zip(stats[1:count], centers[1:count]):
        _, _, component_width, component_height, area = map(int, stat)
        normalized_x = float(center[0] / width)
        normalized_y = float(center[1] / height)
        aspect = component_width / float(max(1, component_height))
        if not (0.025 <= normalized_x <= 0.095 and 0.15 <= normalized_y <= 0.35):
            continue
        if not (width * 0.025 <= component_width <= width * 0.09):
            continue
        if not (height * 0.045 <= component_height <= height * 0.14):
            continue
        if not (0.75 <= aspect <= 1.30) or area < 400:
            continue
        tool_candidates.append((area, normalized_x, normalized_y))
    if tool_candidates:
        _, tool_x, tool_y = max(tool_candidates)
        tool_button = {"x": tool_x, "y": tool_y}

    hundred_button = None
    hundred_button_visible = None
    blue = cv2.inRange(hsv, np.array([85, 70, 100]), np.array([115, 255, 255]))
    blue_count, _, blue_stats, blue_centers = cv2.connectedComponentsWithStats(blue)
    for stat, center in zip(blue_stats[1:blue_count], blue_centers[1:blue_count]):
        x, y, component_width, component_height, area = map(int, stat)
        normalized_x = float(center[0] / width)
        normalized_y = float(center[1] / height)
        if not (0.80 <= normalized_x <= 0.97 and 0.68 <= normalized_y <= 0.90):
            continue
        if not (width * 0.08 <= component_width <= width * 0.15):
            continue
        if not (height * 0.035 <= component_height <= height * 0.09):
            continue
        if area < 1200:
            continue
        visible_button = {
            "x": normalized_x,
            "y": normalized_y,
        }
        if hundred_button_visible is None:
            hundred_button_visible = visible_button
        text_score = _campus_100_text_score(
            bgr[y:y + component_height, x:x + component_width]
        )
        if text_score < 0.60:
            continue
        hundred_button = {
            "x": normalized_x,
            "y": normalized_y,
            "textScore": round(text_score, 3),
        }
        break

    strip = _campus_object_strip(bgr)
    state = "unknown"
    if (
        hundred_button is not None
        or hundred_button_visible is not None
        or (nearest in (5, 6) and nearest_distance <= 38)
        or strip["verified"]
    ):
        state = "campus_detail"
    elif len(maintenance_badges) >= 3 and tool_button is not None:
        state = "campus_maintenance"
    elif nearest == 4 and nearest_distance <= 42:
        state = "campus_maintenance"
    elif nearest == 3 and nearest_distance <= 42:
        state = "campus"

    return {
        "found": state != "unknown",
        "state": state,
        "toolButton": tool_button if state in ("campus", "campus_maintenance") else None,
        "hundredButton": hundred_button if state == "campus_detail" else None,
        "hundredButtonVisible": hundred_button_visible if state == "campus_detail" else None,
        "maintenanceBadgeCount": len(maintenance_badges),
        "maintenanceBadges": maintenance_badges if state == "campus_maintenance" else [],
        "referenceDistance": round(nearest_distance, 2),
        "objectStrip": strip,
    }


def _alliance_anchor_mask(bgr, kind):
    """Build a high-contrast mask for one local, reference-backed UI label."""
    if kind == "white":
        return np.all(bgr >= 180, axis=2).astype(np.uint8)

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    if kind == "green":
        return (cv2.inRange(
            hsv, np.array([35, 65, 75]), np.array([95, 255, 255])
        ) > 0).astype(np.uint8)
    if kind == "cyan":
        return (cv2.inRange(
            hsv, np.array([82, 75, 100]), np.array([118, 255, 255])
        ) > 0).astype(np.uint8)
    if kind == "dark":
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        return (gray <= 105).astype(np.uint8)

    # Non-selected sidebar labels are grey rather than white.  Their local
    # background is very dark, so this keeps the glyphs while dropping rows.
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return (gray >= 75).astype(np.uint8)


def _trim_binary_template(mask):
    ys, xs = np.where(mask > 0)
    if len(xs) < 20:
        return None
    x1, x2 = int(xs.min()), int(xs.max()) + 1
    y1, y2 = int(ys.min()), int(ys.max()) + 1
    result = mask[y1:y2, x1:x2]
    if result.shape[0] < 5 or result.shape[1] < 12:
        return None
    return result


def _alliance_anchor_templates():
    global _ALLIANCE_ANCHOR_TEMPLATES
    if _ALLIANCE_ANCHOR_TEMPLATES is not None:
        return _ALLIANCE_ANCHOR_TEMPLATES

    # Each label is searched only inside its own semantic region.  This is
    # deliberately local: reference 3 contains a Snipping Tool overlay and
    # the task cards reflow between references 5 and 6.
    specs = {
        "home": {
            "reference": 2,
            "crop": (43, 38, 139, 76),
            "kind": "white",
            "search": (0.025, 0.190, 0.050, 0.500),
            "threshold": 0.68,
        },
        "home_header": {
            "reference": 1,
            "crop": (90, 37, 218, 82),
            "kind": "green",
            "search": (0.055, 0.250, 0.050, 0.200),
            "threshold": 0.65,
        },
        "campus": {
            "reference": 3,
            "crop": (52, 52, 148, 96),
            "kind": "sidebar",
            "search": (0.030, 0.190, 0.050, 0.960),
            "threshold": 0.72,
        },
        "alliance_row": {
            "reference": 3,
            "crop": (52, 316, 132, 358),
            "kind": "sidebar",
            "search": (0.030, 0.190, 0.050, 0.960),
            "threshold": 0.72,
        },
        "alliance_header": {
            "reference": 4,
            "crop": (91, 37, 205, 75),
            "kind": "green",
            "search": (0.055, 0.230, 0.050, 0.190),
            "threshold": 0.65,
        },
        "path_label": {
            "reference": 4,
            "crop": (83, 516, 216, 557),
            "kind": "white",
            "search": (0.025, 0.270, 0.700, 0.990),
            "threshold": 0.62,
        },
        "modal_title": {
            "reference": 5,
            "crop": (414, 55, 654, 110),
            "kind": "white",
            "search": (0.290, 0.700, 0.070, 0.230),
            "threshold": 0.70,
        },
        "daily_task": {
            "reference": 5,
            "crop": (51, 174, 139, 207),
            "kind": "cyan",
            "search": (0.025, 0.250, 0.220, 0.500),
            "threshold": 0.72,
        },
        "completed_layout": {
            "reference": 6,
            "crop": (48, 164, 208, 208),
            "kind": "dark",
            "search": (0.025, 0.380, 0.220, 0.500),
            "threshold": 0.72,
        },
    }

    templates = {}
    for name, spec in specs.items():
        reference = cv2.imread(
            os.path.join(ALLIANCE_REFERENCE_DIR, f"{spec['reference']}.png"),
            cv2.IMREAD_COLOR,
        )
        if reference is None:
            continue
        x1, y1, x2, y2 = spec["crop"]
        template = _trim_binary_template(
            _alliance_anchor_mask(reference[y1:y2, x1:x2], spec["kind"])
        )
        if template is None:
            continue
        templates[name] = {
            **spec,
            "template": template,
            "referenceSize": (reference.shape[1], reference.shape[0]),
        }

    _ALLIANCE_ANCHOR_TEMPLATES = templates
    return templates


def _match_alliance_anchor(bgr, name):
    spec = _alliance_anchor_templates().get(name)
    if spec is None:
        return {"matched": False, "score": 0.0, "x": None, "y": None}

    reference_width, reference_height = spec["referenceSize"]
    resized = cv2.resize(
        bgr, (reference_width, reference_height), interpolation=cv2.INTER_AREA
    )
    observed = _alliance_anchor_mask(resized, spec["kind"])
    left, right, top, bottom = spec["search"]
    x1, x2 = int(reference_width * left), int(reference_width * right)
    y1, y2 = int(reference_height * top), int(reference_height * bottom)
    search = observed[y1:y2, x1:x2]
    template = spec["template"]
    if (
        search.shape[0] < template.shape[0]
        or search.shape[1] < template.shape[1]
    ):
        return {"matched": False, "score": 0.0, "x": None, "y": None}

    response = cv2.matchTemplate(
        search.astype(np.float32),
        template.astype(np.float32),
        cv2.TM_CCOEFF_NORMED,
    )
    _, score, _, location = cv2.minMaxLoc(response)
    if not np.isfinite(score):
        score = 0.0
    center_x = x1 + location[0] + (template.shape[1] / 2.0)
    center_y = y1 + location[1] + (template.shape[0] / 2.0)
    return {
        "matched": float(score) >= float(spec["threshold"]),
        "score": round(float(score), 3),
        "x": float(center_x / reference_width),
        "y": float(center_y / reference_height),
    }


def _alliance_go_glyph_template():
    global _ALLIANCE_GO_GLYPH_TEMPLATE
    if _ALLIANCE_GO_GLYPH_TEMPLATE is not None:
        return _ALLIANCE_GO_GLYPH_TEMPLATE
    reference = cv2.imread(
        os.path.join(ALLIANCE_REFERENCE_DIR, "5.png"), cv2.IMREAD_COLOR
    )
    _ALLIANCE_GO_GLYPH_TEMPLATE = (
        _tight_white_glyph_signature(reference[255:282, 310:384])
        if reference is not None else None
    )
    return _ALLIANCE_GO_GLYPH_TEMPLATE


def _alliance_go_text_score(button_bgr):
    observed = _tight_white_glyph_signature(button_bgr)
    template = _alliance_go_glyph_template()
    if observed is None or template is None:
        return 0.0
    score = cv2.matchTemplate(
        observed.astype(np.float32),
        template.astype(np.float32),
        cv2.TM_CCOEFF_NORMED,
    )[0, 0]
    return float(score) if np.isfinite(score) else 0.0


def _alliance_idi_text_template():
    global _ALLIANCE_IDI_TEXT_TEMPLATE
    if _ALLIANCE_IDI_TEXT_TEMPLATE is not None:
        return _ALLIANCE_IDI_TEXT_TEMPLATE
    reference = cv2.imread(
        os.path.join(ALLIANCE_REFERENCE_DIR, "5.png"), cv2.IMREAD_COLOR
    )
    if reference is None:
        return None
    button = reference[255:282, 310:384]
    right = button[:, int(button.shape[1] * 0.48):]
    _ALLIANCE_IDI_TEXT_TEMPLATE = _tight_white_glyph_signature(right)
    return _ALLIANCE_IDI_TEXT_TEMPLATE


def _alliance_idi_text_score(button_bgr):
    if button_bgr.size == 0:
        return 0.0
    right = button_bgr[:, int(button_bgr.shape[1] * 0.48):]
    observed = _tight_white_glyph_signature(right)
    template = _alliance_idi_text_template()
    if observed is None or template is None:
        return 0.0
    score = cv2.matchTemplate(
        observed.astype(np.float32),
        template.astype(np.float32),
        cv2.TM_CCOEFF_NORMED,
    )[0, 0]
    return float(score) if np.isfinite(score) else 0.0


def _alliance_idi_component_score(button_bgr):
    """Verify the tall narrow-wide-narrow glyph structure of literal IDI.

    A loading control can retain the video icon and draw three dots.  Whole-
    button matching gives too much weight to that unchanged icon, whereas the
    three IDI letters are tall and aligned through roughly half the button.
    """
    if button_bgr.size == 0:
        return 0.0
    height, width = button_bgr.shape[:2]
    white = np.all(button_bgr >= 185, axis=2).astype(np.uint8)
    count, _, stats, centers = cv2.connectedComponentsWithStats(white)
    glyphs = []
    for stat, center in zip(stats[1:count], centers[1:count]):
        x, y, component_width, component_height, area = map(int, stat)
        if float(center[0]) < width * 0.50:
            continue
        if not (height * 0.32 <= component_height <= height * 0.78):
            continue
        if area < max(4, int(height * 0.45)):
            continue
        glyphs.append(
            {
                "x": float(center[0]),
                "y": float(center[1]),
                "width": component_width,
                "height": component_height,
            }
        )
    glyphs.sort(key=lambda glyph: glyph["x"])

    for index in range(max(0, len(glyphs) - 2)):
        first, middle, last = glyphs[index:index + 3]
        heights = [first["height"], middle["height"], last["height"]]
        if min(heights) / float(max(heights)) < 0.68:
            continue
        if max(glyph["y"] for glyph in (first, middle, last)) - min(
            glyph["y"] for glyph in (first, middle, last)
        ) > height * 0.14:
            continue
        if first["width"] > width * 0.09 or last["width"] > width * 0.09:
            continue
        if not (width * 0.055 <= middle["width"] <= width * 0.20):
            continue
        center_span = last["x"] - first["x"]
        if not (width * 0.15 <= center_span <= width * 0.36):
            continue
        return 1.0
    return 0.0


def _detect_alliance_menu_toggle(bgr):
    height, width = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, np.array([35, 80, 70]), np.array([95, 255, 255]))
    # Keep the ROI left of the screen icon; otherwise its green pixels can be
    # mistaken for the narrow navigation chevron.
    roi_right = max(8, int(width * 0.026))
    roi_top, roi_bottom = int(height * 0.050), int(height * 0.190)
    roi = green[roi_top:roi_bottom, 0:roi_right]
    roi = cv2.morphologyEx(roi, cv2.MORPH_CLOSE, np.ones((5, 3), np.uint8))
    count, _, stats, centers = cv2.connectedComponentsWithStats(roi)
    candidates = []
    for stat, center in zip(stats[1:count], centers[1:count]):
        _, _, component_width, component_height, area = map(int, stat)
        if not (width * 0.002 <= component_width <= width * 0.018):
            continue
        if not (height * 0.020 <= component_height <= height * 0.085):
            continue
        if area < 18:
            continue
        screen_x = float(center[0])
        screen_y = roi_top + float(center[1])
        candidates.append((area, screen_x / width, screen_y / height))
    if not candidates:
        return None
    _, x, y = max(candidates)
    return {"x": x, "y": y}


def _detect_alliance_modal_x(bgr):
    """Find only the Put saveza modal X, never the BlueStacks title-bar X."""
    height, width = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    left, right = int(width * 0.835), int(width * 0.965)
    top, bottom = int(height * 0.070), int(height * 0.210)
    roi = gray[top:bottom, left:right]
    candidates = []
    for local_x, local_y, response_strength in _response_centers(roi):
        screen_x, screen_y = left + local_x, top + local_y
        contrast, polarity = _x_contrast_score(gray, screen_x, screen_y)
        if response_strength < 55 or contrast < 200 or polarity != "bright-on-dark":
            continue
        shape = _x_shape_quality(gray, screen_x, screen_y, polarity)
        if shape < 78:
            continue
        candidates.append(
            (contrast + response_strength + shape, screen_x / width, screen_y / height,
             response_strength, contrast, shape)
        )
    if not candidates:
        return None
    _, x, y, response_strength, contrast, shape = max(candidates)
    return {
        "x": float(x),
        "y": float(y),
        "response": round(float(response_strength), 2),
        "contrast": round(float(contrast), 2),
        "shape": round(float(shape), 2),
    }


def detect_alliance_flow(bgr):
    """Recognize the sidebar, Savezi screen and Put saveza reward modal."""
    height, width = bgr.shape[:2]
    if width < 600 or height < 400:
        return {
            "found": False,
            "state": "unknown",
            "menuToggle": None,
            "homeButton": None,
            "campusButton": None,
            "allianceButton": None,
            "pathButton": None,
            "goButton": None,
            "goButtonVisible": None,
            "dailyTaskPresent": False,
            "completedLayout": False,
            "taskGridLoaded": False,
            "closeButton": None,
        }

    anchors = {
        name: _match_alliance_anchor(bgr, name)
        for name in (
            "home", "home_header", "campus", "alliance_row", "alliance_header",
            "path_label", "modal_title", "daily_task", "completed_layout",
        )
    }
    menu_toggle = _detect_alliance_menu_toggle(bgr)
    modal_confirmed = anchors["modal_title"]["matched"]

    go_button = None
    go_button_visible = None
    task_grid_loaded = False
    if modal_confirmed:
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        bright_cards = cv2.inRange(
            hsv, np.array([0, 0, 200]), np.array([179, 65, 255])
        )
        card_count, _, card_stats, card_centers = cv2.connectedComponentsWithStats(
            bright_cards
        )
        task_cards = []
        for stat, center in zip(card_stats[1:card_count], card_centers[1:card_count]):
            _, _, card_width, card_height, card_area = map(int, stat)
            normalized_x = float(center[0] / width)
            normalized_y = float(center[1] / height)
            if not (0.05 <= normalized_x <= 0.68 and 0.25 <= normalized_y <= 0.90):
                continue
            if not (width * 0.24 <= card_width <= width * 0.38):
                continue
            if not (height * 0.12 <= card_height <= height * 0.23):
                continue
            if card_area < width * height * 0.020:
                continue
            task_cards.append((normalized_x, normalized_y))
        # One fully rendered task card is positive evidence that the grid has
        # settled.  This still works late in the day when most tasks vanished.
        task_grid_loaded = len(task_cards) >= 1

        blue = cv2.inRange(hsv, np.array([85, 70, 100]), np.array([118, 255, 255]))
        count, _, stats, centers = cv2.connectedComponentsWithStats(blue)
        visible_candidates = []
        ready_candidates = []
        for stat, center in zip(stats[1:count], centers[1:count]):
            x, y, component_width, component_height, area = map(int, stat)
            normalized_x = float(center[0] / width)
            normalized_y = float(center[1] / height)
            aspect = component_width / float(max(1, component_height))
            fill = area / float(max(1, component_width * component_height))
            if not (0.20 <= normalized_x <= 0.48 and 0.30 <= normalized_y <= 0.55):
                continue
            if not (width * 0.045 <= component_width <= width * 0.12):
                continue
            if not (height * 0.025 <= component_height <= height * 0.075):
                continue
            if not (1.7 <= aspect <= 4.7) or fill < 0.45 or area < 450:
                continue
            visible = {
                "x": normalized_x,
                "y": normalized_y,
                "width": component_width / float(width),
                "height": component_height / float(height),
            }
            visible_candidates.append((area, visible))
            inset = 1 if component_width > 8 and component_height > 8 else 0
            button_crop = bgr[
                y + inset:y + component_height - inset,
                x + inset:x + component_width - inset,
            ]
            text_score = _alliance_go_text_score(button_crop)
            idi_text_score = _alliance_idi_text_score(button_crop)
            idi_component_score = _alliance_idi_component_score(button_crop)
            if text_score >= 0.58 and idi_component_score >= 0.90:
                ready = {
                    **visible,
                    "textScore": round(text_score, 3),
                    "idiTextScore": round(idi_text_score, 3),
                    "idiComponentScore": round(idi_component_score, 3),
                }
                ready_candidates.append((text_score, area, ready))

        if visible_candidates:
            _, go_button_visible = max(visible_candidates, key=lambda item: item[0])
        if ready_candidates:
            _, _, go_button = max(ready_candidates, key=lambda item: (item[0], item[1]))

    close_button = _detect_alliance_modal_x(bgr) if modal_confirmed else None
    alliance_screen = anchors["alliance_header"]["matched"]
    sidebar_open = any(
        anchors[name]["matched"] for name in ("home", "campus", "alliance_row")
    )

    if modal_confirmed:
        state = "path"
    elif alliance_screen:
        state = "alliance"
    elif sidebar_open:
        state = "side_menu"
    elif anchors["home_header"]["matched"] and menu_toggle is not None:
        state = "home"
    elif menu_toggle is not None:
        state = "navigation_closed"
    else:
        state = "unknown"

    def target(name):
        anchor = anchors[name]
        if not anchor["matched"]:
            return None
        return {"x": anchor["x"], "y": anchor["y"], "score": anchor["score"]}

    return {
        "found": state != "unknown",
        "state": state,
        "menuToggle": menu_toggle if state in ("navigation_closed", "home", "alliance") else None,
        "homeButton": target("home") if state == "side_menu" else None,
        "campusButton": target("campus") if state == "side_menu" else None,
        "allianceButton": target("alliance_row") if state == "side_menu" else None,
        "pathButton": target("path_label") if state == "alliance" else None,
        "goButton": go_button if state == "path" else None,
        "goButtonVisible": go_button_visible if state == "path" else None,
        "dailyTaskPresent": bool(anchors["daily_task"]["matched"]) if state == "path" else False,
        "completedLayout": bool(anchors["completed_layout"]["matched"]) if state == "path" else False,
        "taskGridLoaded": bool(task_grid_loaded) if state == "path" else False,
        "closeButton": close_button if state == "path" else None,
        "anchorScores": {name: value["score"] for name, value in anchors.items()},
    }


def detect_team_rest_free_button(bgr):
    """Accept a rest/store ad button only when its full white label is rendered.

    The loading state uses the same blue rectangle but contains only three dots.
    Nine separated, letter-sized bright glyphs spread across the button distinguish
    the actual BESPLATNO label without relying on the blue background alone. Both
    the player-rest modal and the upper-right 25-green Store layout are supported.
    """
    height, width = bgr.shape[:2]
    if width < 600 or height < 400:
        return {
            "found": False,
            "ready": False,
            "buttonVisible": False,
            "topElevenContext": False,
            "glyphCount": 0,
        }

    top_eleven_context = detect_top_resource_cards(bgr)["found"]
    store_roi = bgr[
        int(height * 0.30):int(height * 0.54),
        int(width * 0.02):int(width * 0.22),
    ]
    store_light = np.all(store_roi >= 185, axis=2) if store_roi.size else np.zeros((1, 1), dtype=bool)
    store_loaded = bool(top_eleven_context and float(np.mean(store_light)) >= 0.18)
    if not top_eleven_context:
        return {
            "found": False,
            "ready": False,
            "buttonVisible": False,
            "topElevenContext": False,
            "storeLoaded": False,
            "glyphCount": 0,
        }

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    blue = cv2.inRange(hsv, np.array([85, 70, 100]), np.array([115, 255, 255]))
    count, _, stats, centers = cv2.connectedComponentsWithStats(blue)
    visible_candidates = []

    # U Prodavnici je dugme ponekad istog plavog tona kao cijela pozadina.
    # Tada HSV komponenta postane ogroman spojeni oblik i nema zaseban okvir.
    # Tekst sam po sebi nije dovoljan: POGLEDAJ i kartica BESPLATNI imaju isti
    # broj bijelih slova. Stvarno reward dugme ima video-kameru lijevo i obojenu
    # ikonu resursa desno, sa punom rijeci (ne tri loading tacke) izmedju njih.
    store_text_candidate = None
    store_x1, store_x2 = int(width * 0.78), int(width * 0.99)
    store_y1, store_y2 = int(height * 0.18), int(height * 0.70)
    store_text_roi = bgr[store_y1:store_y2, store_x1:store_x2]
    if store_loaded and store_text_roi.size:
        bright_text = np.all(store_text_roi >= 185, axis=2).astype(np.uint8)
        text_count, text_labels, text_stats, text_centers = cv2.connectedComponentsWithStats(bright_text)
        glyphs = []
        for label_index, (glyph, center) in enumerate(
            zip(text_stats[1:text_count], text_centers[1:text_count]), start=1
        ):
            glyph_x, glyph_y, glyph_width, glyph_height, glyph_area = map(int, glyph)
            # The camera glyph is one connected, landscape component and is
            # wider than an individual letter (29 px on a 1024 px capture).
            if not (2 <= glyph_width <= max(40, int(width * 0.040))):
                continue
            if not (height * 0.012 <= glyph_height <= height * 0.040):
                continue
            if glyph_area < max(10, int(width * height * 0.000015)):
                continue
            component = (
                text_labels[
                    glyph_y:glyph_y + glyph_height,
                    glyph_x:glyph_x + glyph_width,
                ] == label_index
            ).astype(np.uint8)
            contours, hierarchy = cv2.findContours(
                component, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
            )
            holes = (
                sum(1 for index in range(len(contours)) if hierarchy[0][index][3] >= 0)
                if hierarchy is not None else 0
            )
            glyphs.append({
                "x": float(center[0]),
                "y": float(center[1]),
                "width": glyph_width,
                "height": glyph_height,
                "area": glyph_area,
                "holes": holes,
            })

        # Svako slovo predlaze red; najbolji red mora imati raspon cijele
        # rijeci BESPLATNO, ne samo nekoliko susjednih ikona ili cifara.
        checked_rows = set()
        store_hsv = cv2.cvtColor(store_text_roi, cv2.COLOR_BGR2HSV)
        for seed in glyphs:
            row_y, row_height = seed["y"], seed["height"]
            tolerance = max(4.0, row_height * 0.55)
            row = sorted(
                (glyph for glyph in glyphs if abs(glyph["y"] - row_y) <= tolerance),
                key=lambda glyph: glyph["x"],
            )
            row_key = tuple(round(glyph["x"]) for glyph in row)
            if row_key in checked_rows:
                continue
            checked_rows.add(row_key)
            if not (9 <= len(row) <= 14):
                continue
            # Na stvarnom Top Eleven fontu anti-aliasing ponekad razdvoji
            # jedan znak na dvije bijele komponente, a uz lijevi rub reda moze
            # ostati mali bijeli komadic prethodne kartice. Red zato prvo
            # pocinje od stvarne landscape video-kamere, ne od row[0].
            camera_index = next(
                (
                    index for index, glyph in enumerate(row)
                    if glyph["width"] >= 12.0
                    and glyph["width"] >= glyph["height"] * 1.25
                ),
                None,
            )
            if camera_index is None:
                continue
            row = row[camera_index:]
            if not (9 <= len(row) <= 14):
                continue
            widths = [glyph["width"] for glyph in row]
            median_width = float(np.median(widths))
            left_icon = row[0]
            right_icon = row[-1]
            if not (
                left_icon["width"] >= max(12.0, median_width * 1.65)
                and left_icon["width"] >= left_icon["height"] * 1.25
            ):
                continue
            # The colored green/blue resource tile surrounds the rightmost
            # white glyph. A plain word or BESPLATNI navigation tab has no
            # video/resource pair and therefore cannot pass this check.
            icon_radius = max(12, round(right_icon["height"] * 1.35))
            icon_x1 = max(0, round(right_icon["x"] - icon_radius))
            icon_x2 = min(store_hsv.shape[1], round(right_icon["x"] + icon_radius + 1))
            icon_y1 = max(0, round(right_icon["y"] - icon_radius))
            icon_y2 = min(store_hsv.shape[0], round(right_icon["y"] + icon_radius + 1))
            icon_patch = store_hsv[icon_y1:icon_y2, icon_x1:icon_x2]
            colored_ratio = (
                float(np.mean((icon_patch[:, :, 1] >= 90) & (icon_patch[:, :, 2] >= 90)))
                if icon_patch.size else 0.0
            )
            if colored_ratio < 0.08:
                continue
            # Ovaj detector pripada iskljucivo fazi "Uzmi 25 zelenih".
            # Donji red Prodavnice ima isto BESPLATNO dugme, ali plavu ikonu
            # morala; njega se nikada ne smije kliknuti. Zahtijevaj stvarne
            # zelene pixele oko desne ikone odmora, ne samo bilo koju boju.
            green_resource_ratio = (
                float(np.mean(
                    (icon_patch[:, :, 0] >= 35)
                    & (icon_patch[:, :, 0] <= 85)
                    & (icon_patch[:, :, 1] >= 90)
                    & (icon_patch[:, :, 2] >= 90)
                ))
                if icon_patch.size else 0.0
            )
            if green_resource_ratio < 0.05:
                continue
            text_components = row[1:-1]
            # Spoji komponente koje pripadaju istom slovu i imaju gotovo isti
            # horizontalni centar. Na prilozenom stvarnom BESPLATNO redu S, P
            # i O mogu biti podijeljeni pragom svjetline; bez ovog grupiranja
            # ispravna rijec izgleda kao 10-11 umjesto 8 komponenti.
            text_glyphs = []
            merge_tolerance = max(1.5, width * 0.002)
            for component in text_components:
                if text_glyphs and abs(component["x"] - text_glyphs[-1]["x"]) <= merge_tolerance:
                    group = text_glyphs[-1]
                    group["x"] = (group["x"] * group["parts"] + component["x"]) / (group["parts"] + 1)
                    group["width"] = max(group["width"], component["width"])
                    group["height"] = max(group["height"], component["height"])
                    group["area"] += component["area"]
                    group["holes"] += component["holes"]
                    group["parts"] += 1
                else:
                    text_glyphs.append({**component, "parts": 1})
            # Exact lightweight word signature for BESPLATNO. At the sizes used
            # by Top Eleven, L+A can touch, so the nine letters form eight
            # components. B has two counters, P has one and the final O has
            # one. This rejects POGLEDAJ/BESPLATNI/random text even if another
            # blue row happens to be flanked by similar icons.
            if len(text_glyphs) != 8:
                continue
            hole_pattern = [int(glyph["holes"]) for glyph in text_glyphs]
            if not (
                hole_pattern[0] >= 2
                and hole_pattern[3] >= 1
                and hole_pattern[-1] >= 1
            ):
                continue
            row_x = [glyph["x"] for glyph in row]
            span = (max(row_x) - min(row_x)) / float(width)
            if not (0.055 <= span <= 0.16):
                continue
            center_x = (store_x1 + (min(row_x) + max(row_x)) * 0.5) / float(width)
            center_y = (store_y1 + sum(glyph["y"] for glyph in row) / len(row)) / float(height)
            candidate = {
                "found": True,
                "ready": True,
                "buttonVisible": True,
                "topElevenContext": True,
                "storeLoaded": True,
                "layout": "store",
                "x": center_x,
                "y": center_y,
                "glyphCount": len(row),
                "whitePixels": int(sum(glyph["area"] for glyph in row)),
                "textSpan": round(span, 3),
                "occupiedColumns": 0.0,
                "textFirst": True,
                "flankedByRewardIcons": True,
                "resourceColorRatio": round(colored_ratio, 3),
                "greenResourceRatio": round(green_resource_ratio, 3),
                "letterHolePattern": hole_pattern,
            }
            if store_text_candidate is None or candidate["glyphCount"] > store_text_candidate["glyphCount"]:
                store_text_candidate = candidate

    for stat, center in zip(stats[1:count], centers[1:count]):
        x, y, component_width, component_height, area = map(int, stat)
        normalized_x = float(center[0] / width)
        normalized_y = float(center[1] / height)
        team_zone = 0.66 <= normalized_x <= 0.87 and 0.78 <= normalized_y <= 0.96
        # Store kartice se vertikalno pomjeraju zavisno od broja/visine
        # ponuda. U praksi je BESPLATNO vidjeno od gornje petine pa sve do
        # oko 70% prozora; stara uska zona je propustala potpuno ispisano
        # dugme i cekala svih 90 sekundi.
        store_zone = (
            store_loaded
            and 0.78 <= normalized_x <= 0.985
            and 0.18 <= normalized_y <= 0.70
        )
        if not (team_zone or store_zone):
            continue
        if not (width * 0.09 <= component_width <= width * 0.19):
            continue
        if not (height * 0.045 <= component_height <= height * 0.13):
            continue
        if area < width * height * 0.006:
            continue

        button = bgr[y:y + component_height, x:x + component_width]
        if store_zone:
            button_hsv = cv2.cvtColor(button, cv2.COLOR_BGR2HSV)
            right_icon_patch = button_hsv[:, int(component_width * 0.78):]
            green_resource_ratio = (
                float(np.mean(
                    (right_icon_patch[:, :, 0] >= 35)
                    & (right_icon_patch[:, :, 0] <= 85)
                    & (right_icon_patch[:, :, 1] >= 90)
                    & (right_icon_patch[:, :, 2] >= 90)
                ))
                if right_icon_patch.size else 0.0
            )
            if green_resource_ratio < 0.025:
                continue
        bright = np.all(button >= 190, axis=2).astype(np.uint8)
        white_pixels = int(np.sum(bright))
        ys, xs = np.where(bright > 0)
        text_span = float((int(xs.max()) - int(xs.min()) + 1) / component_width) if len(xs) else 0.0
        occupied_columns = float(np.count_nonzero(np.sum(bright, axis=0)) / component_width)

        glyph_count, _, glyph_stats, _ = cv2.connectedComponentsWithStats(bright)
        letter_components = []
        for glyph in glyph_stats[1:glyph_count]:
            _, _, glyph_width, glyph_height, glyph_area = map(int, glyph)
            if glyph_area < max(12, int(component_width * component_height * 0.0025)):
                continue
            if glyph_height < component_height * 0.15:
                continue
            if glyph_width > component_width * 0.16:
                continue
            letter_components.append(glyph)

        letters = len(letter_components)
        ready = (
            8 <= letters <= 13
            and white_pixels >= component_width * component_height * 0.025
            and text_span >= 0.50
            and occupied_columns >= 0.38
        )
        visible_candidates.append(
            {
                "found": ready,
                "ready": ready,
                "buttonVisible": True,
                "topElevenContext": True,
                "storeLoaded": bool(store_loaded or store_zone),
                "layout": "store" if store_zone else "team_rest",
                "x": normalized_x,
                "y": normalized_y,
                "glyphCount": letters,
                "whitePixels": white_pixels,
                "textSpan": round(text_span, 3),
                "occupiedColumns": round(occupied_columns, 3),
            }
        )

    if store_text_candidate is not None:
        return store_text_candidate
    if not visible_candidates:
        return {
            "found": False,
            "ready": False,
            "buttonVisible": False,
            "topElevenContext": True,
            "storeLoaded": store_loaded,
            "glyphCount": 0,
        }
    ready_candidates = [candidate for candidate in visible_candidates if candidate["ready"]]
    if ready_candidates:
        return max(ready_candidates, key=lambda candidate: candidate["whitePixels"])
    return max(visible_candidates, key=lambda candidate: candidate["whitePixels"])


def _training_player_reference_features():
    global _TRAINING_PLAYER_REFERENCE_FEATURES
    if _TRAINING_PLAYER_REFERENCE_FEATURES is not None:
        return _TRAINING_PLAYER_REFERENCE_FEATURES
    features = {}
    for index in range(1, 9):
        reference = cv2.imread(
            os.path.join(TRAINING_PLAYER_REFERENCE_DIR, f"{index}.png"),
            cv2.IMREAD_COLOR,
        )
        if reference is not None:
            features[index] = _tv_feature(reference)
    _TRAINING_PLAYER_REFERENCE_FEATURES = features
    return features


def _training_player_profile_signature(bgr):
    """Verify the three-column player profile independently of reference similarity."""
    height, width = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    y1, y2 = int(height * 0.48), int(height * 0.72)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    hue = hsv[:, :, 0]

    def colored_count(x1, x2, hue_mask):
        region = (
            hue_mask[y1:y2, int(width * x1):int(width * x2)]
            & (saturation[y1:y2, int(width * x1):int(width * x2)] >= 100)
            & (value[y1:y2, int(width * x1):int(width * x2)] >= 100)
        )
        return int(np.sum(region))

    red = colored_count(0.22, 0.36, (hue <= 12) | (hue >= 170))
    blue = colored_count(0.42, 0.58, (hue >= 90) & (hue <= 125))
    green = colored_count(0.64, 0.80, (hue >= 35) & (hue <= 85))
    modal = hsv[
        int(height * 0.12):int(height * 0.94),
        int(width * 0.07):int(width * 0.90),
    ]
    light_modal_ratio = (
        float(np.mean((modal[:, :, 1] <= 55) & (modal[:, :, 2] >= 130)))
        if modal.size else 0.0
    )
    pixels = float(width * height)
    verified = (
        red >= pixels * 0.00035
        and blue >= pixels * 0.00035
        and green >= pixels * 0.00080
        and light_modal_ratio >= 0.58
    )
    return {
        "verified": bool(verified),
        "redPixels": red,
        "bluePixels": blue,
        "greenPixels": green,
        "lightModalRatio": round(light_modal_ratio, 3),
    }


def _training_condition_modal_close(bgr):
    """Ground the recovery panel in its dark body, column markers and red X."""
    h, w = bgr.shape[:2]
    signature = _training_player_profile_signature(bgr)
    if any(signature[key] < w * h * .00035
           for key in ("redPixels", "bluePixels", "greenPixels")):
        return None
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    body = hsv[int(h * .73):int(h * .81), int(w * .30):int(w * .85)]
    # Gold/rare profile layouts leave more colored controls inside this band;
    # the recovery panel is still unambiguous when its red close and the blue
    # BESPLATNO control are grounded below.
    if float(np.mean(body[:, :, 2] < 65)) < .50:
        return None
    red = (((hsv[:, :, 0] <= 12) | (hsv[:, :, 0] >= 170))
           & (hsv[:, :, 1] >= 130) & (hsv[:, :, 2] >= 130)).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(red)
    for x, y, bw, bh, area in stats[1:count]:
        if not (.50 <= (x + bw / 2) / w <= .65 and .80 <= (y + bh / 2) / h <= .96
                and .04 <= bw / w <= .09 and .06 <= bh / h <= .13
                and area >= bw * bh * .65):
            continue
        button = hsv[y:y + bh, x:x + bw]
        pale = (button[:, :, 1] < 130) & (button[:, :, 2] >= 140)
        if float(np.mean(pale)) >= .03:
            return {"x": float((x + bw / 2) / w), "y": float((y + bh / 2) / h)}
    return None


def _training_condition_plus(bgr):
    """Locate the rightmost green KONDICIJA plus on a verified player profile."""
    height, width = bgr.shape[:2]
    signature = _training_player_profile_signature(bgr)
    if not signature["verified"]:
        return None
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    green = (((hsv[:, :, 0] >= 35) & (hsv[:, :, 0] <= 85))
             & (hsv[:, :, 1] >= 90) & (hsv[:, :, 2] >= 100)).astype(np.uint8)
    count, _, stats, centers = cv2.connectedComponentsWithStats(green)
    candidates = []
    for stat, center in zip(stats[1:count], centers[1:count]):
        x, y, component_width, component_height, area = map(int, stat)
        nx, ny = float(center[0] / width), float(center[1] / height)
        if not (.82 <= nx <= .985 and .52 <= ny <= .78):
            continue
        if not (.025 <= component_width / width <= .09 and
                .045 <= component_height / height <= .16 and
                area >= component_width * component_height * .45):
            continue
        patch = hsv[y:y + component_height, x:x + component_width]
        pale_plus = (patch[:, :, 1] <= 95) & (patch[:, :, 2] >= 175)
        if float(np.mean(pale_plus)) < .025:
            continue
        candidates.append({"x": nx, "y": ny, "area": area})
    if not candidates:
        return None
    best = max(candidates, key=lambda candidate: (candidate["x"], candidate["area"]))
    return {"x": best["x"], "y": best["y"]}


def _training_free_button(bgr):
    height, width = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    blue = cv2.inRange(hsv, np.array([85, 70, 100]), np.array([115, 255, 255]))
    count, _, stats, centers = cv2.connectedComponentsWithStats(blue)
    candidates = []
    for stat, center in zip(stats[1:count], centers[1:count]):
        x, y, component_width, component_height, area = map(int, stat)
        nx, ny = float(center[0] / width), float(center[1] / height)
        if not (0.55 <= nx <= 0.84 and 0.78 <= ny <= 0.98):
            continue
        if not (width * 0.10 <= component_width <= width * 0.25):
            continue
        if not (height * 0.055 <= component_height <= height * 0.14):
            continue
        if area < width * height * 0.006:
            continue
        button = bgr[y:y + component_height, x:x + component_width]
        bright = np.all(button >= 190, axis=2).astype(np.uint8)
        glyph_count, _, glyph_stats, _ = cv2.connectedComponentsWithStats(bright)
        glyphs = []
        for glyph in glyph_stats[1:glyph_count]:
            _, _, gw, gh, ga = map(int, glyph)
            if ga >= max(8, int(component_width * component_height * 0.0018)) and gh >= component_height * 0.15 and gw <= component_width * 0.18:
                glyphs.append(glyph)
        ys, xs = np.where(bright > 0)
        span = float((xs.max() - xs.min() + 1) / component_width) if len(xs) else 0.0
        ready = 8 <= len(glyphs) <= 14 and span >= 0.48
        candidates.append({
            "found": ready, "ready": ready, "buttonVisible": True,
            "x": nx, "y": ny, "glyphCount": len(glyphs), "textSpan": round(span, 3),
        })
    if not candidates:
        return {"found": False, "ready": False, "buttonVisible": False}
    ready = [candidate for candidate in candidates if candidate["ready"]]
    return max(ready or candidates, key=lambda candidate: candidate.get("glyphCount", 0))


def _training_control_anchor(bgr, reference_index, center, half_size=(.06, .022)):
    """Locate the reference control locally; never return a blind fixed click."""
    reference = cv2.imread(os.path.join(TRAINING_PLAYER_REFERENCE_DIR, f"{reference_index}.png"))
    if reference is None:
        return None
    h, w = bgr.shape[:2]
    reference = cv2.resize(reference, (w, h))
    cx, cy = int(center[0] * w), int(center[1] * h)
    rx, ry = max(5, int(half_size[0] * w)), max(5, int(half_size[1] * h))
    template = cv2.cvtColor(reference[max(0, cy-ry):cy+ry, max(0, cx-rx):cx+rx], cv2.COLOR_BGR2GRAY)
    x1, y1 = max(0, cx-rx-int(.035*w)), max(0, cy-ry-int(.035*h))
    roi = cv2.cvtColor(bgr[y1:min(h, cy+ry+int(.035*h)), x1:min(w, cx+rx+int(.035*w))], cv2.COLOR_BGR2GRAY)
    if template.std() < 12 or roi.shape[0] < template.shape[0] or roi.shape[1] < template.shape[1]:
        return None
    _, score, _, location = cv2.minMaxLoc(cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED))
    if not np.isfinite(score) or score < .80:
        return None
    return {"x": (x1+location[0]+template.shape[1]/2)/w,
            "y": (y1+location[1]+template.shape[0]/2)/h, "score": round(score, 3)}


def detect_training_player_flow(bgr):
    height, width = bgr.shape[:2]
    if width < 600 or height < 400:
        return {"state": "unknown"}
    # Match the invariant title and close control, excluding names/percentages.
    exhausted_title = _training_control_anchor(bgr, "exhausted", (.184, .298), (.077, .027))
    if exhausted_title is not None:
        exhausted_close = _training_control_anchor(bgr, "exhausted", (.830, .300), (.018, .027))
        if exhausted_close is not None:
            return {"state": "exhausted_players", "closeButton": exhausted_close}
    feature = _tv_feature(bgr)
    distances = {
        index: float(np.mean(np.abs(feature - reference)))
        for index, reference in _training_player_reference_features().items()
    }
    if not distances:
        return {"state": "unknown"}
    nearest = min(distances, key=distances.get)
    distance = distances[nearest]
    # Do not require the whole profile to resemble reference 7. Rare/gold
    # profiles can be visually distant while the modal controls themselves
    # are freshly and independently verified.
    modal_close = _training_condition_modal_close(bgr)
    modal_free = _training_free_button(bgr) if modal_close is not None else None
    if modal_close is not None:
        return {"state": "condition_modal", "reference": nearest,
                "distance": round(distance, 3), "modalClose": modal_close,
                "freeButton": modal_free}
    # Player identity, kit and profile contents vary considerably. When the
    # profile is still the closest reference, its independent three-column
    # signature can confirm it despite a large whole-frame distance.
    profile_signature = _training_player_profile_signature(bgr) if nearest == 6 else None
    if profile_signature is not None and profile_signature["verified"]:
        result = {"state": "player_detail", "reference": nearest,
                  "distance": round(distance, 3), "profileVerified": True,
                  "profileSignature": profile_signature}
        condition_plus = _training_condition_plus(bgr)
        if condition_plus is not None:
            result["conditionPlus"] = condition_plus
        return result
    if distance > 35 or float(np.std(bgr)) < 12:
        return {"state": "unknown", "distance": round(distance, 3)}
    state = {
        1: "home", 2: "training_home", 3: "reports", 4: "setup",
        5: "training_result", 6: "player_detail", 7: "condition_modal",
        8: "training_home",
    }.get(nearest, "unknown")
    result = {"state": state, "reference": nearest, "distance": round(distance, 3)}
    anchors = {"training_home": ("reportsButton", (.490, .915)),
               "reports": ("repeatButton", (.920, .350)),
               "setup": ("startButton", (.862, .360)),
               "training_result": ("closeButton", (.951, .100))}
    if state in anchors:
        key, center = anchors[state]
        anchor = _training_control_anchor(bgr, nearest, center,
                    (.014, .023) if state == "training_result" else (.06, .022))
        if anchor is None:
            return {"state": "unknown", "distance": round(distance, 3), "reason": "control_not_verified"}
        result[key] = anchor
    elif state in {"player_detail", "condition_modal"}:
        if state == "player_detail":
            profile_signature = _training_player_profile_signature(bgr)
            result["profileVerified"] = profile_signature["verified"]
            result["profileSignature"] = profile_signature
            condition_plus = _training_condition_plus(bgr)
            if condition_plus is not None:
                result["conditionPlus"] = condition_plus
        if state == "condition_modal":
            result["freeButton"] = _training_free_button(bgr)
            result["modalClose"] = {"x": 0.596, "y": 0.881}
    return result


def load_image(path):
    image = cv2.imread(path, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Cannot read image: {path}")
    return image


def capture_rect(rect):
    left, top, right, bottom = map(int, rect)
    rgb = np.asarray(ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def run_detector(image, mode=None, live=False):
    if mode == "frame_fingerprint":
        return {"pixels": cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (32, 18)).flatten().tolist()}
    if mode == "top_resource_cards":
        return detect_top_resource_cards(image)
    if mode == "yellow_ad_control":
        return detect_yellow_ad_control(image)
    if mode == "play_destination":
        return detect_play_destination(image)
    if mode == "tv_flow":
        return detect_tv_flow(image)
    if mode == "mourinho_flow":
        return detect_mourinho_flow(image)
    if mode == "campus_flow":
        return detect_campus_flow(image)
    if mode == "alliance_flow":
        return detect_alliance_flow(image)
    if mode == "team_rest_free_button":
        return detect_team_rest_free_button(image)
    if mode == "training_player_flow":
        return detect_training_player_flow(image)
    return detect_x(image, live=live) or {"found": False}


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
            result = run_detector(image, request.get("mode"), live=("rect" in request))
            print(json.dumps(result), flush=True)
        except Exception as exc:
            print(json.dumps({"found": False, "error": str(exc)}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image")
    parser.add_argument("--server", action="store_true")
    parser.add_argument(
        "--mode",
        choices=("x", "top_resource_cards", "yellow_ad_control", "play_destination", "tv_flow", "mourinho_flow", "campus_flow", "alliance_flow", "team_rest_free_button", "training_player_flow"),
        default="x",
    )
    args = parser.parse_args()

    if args.server:
        server_loop()
        return
    if not args.image:
        parser.error("--image or --server is required")
    mode = None if args.mode == "x" else args.mode
    print(json.dumps(run_detector(load_image(args.image), mode)))


if __name__ == "__main__":
    main()
