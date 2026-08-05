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


def detect_yellow_ad_control(bgr):
    """Detect the wide yellow Google Play pill or the yellow circular close X."""
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
            candidates.append((area, "google_play", cx, cy, control_width, control_height))
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
                    candidates.append((area + contrast, "close", refined_x, refined_y, control_width, control_height))

    if not candidates:
        return {"found": False}

    # Closing the ad always has priority if a Play pill and an X coexist.
    close_controls = [candidate for candidate in candidates if candidate[1] == "close"]
    google_play = [candidate for candidate in candidates if candidate[1] == "google_play"]
    selected = max(close_controls or google_play or candidates, key=lambda item: item[0])
    _, kind, cx, cy, control_width, control_height = selected
    return {
        "found": True,
        "kind": kind,
        "x": float(cx / width),
        "y": float(cy / height),
        "width": int(control_width),
        "height": int(control_height),
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
    if header_white_ratio < 0.90 or body_white_ratio < 0.985:
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
            if request.get("mode") == "top_resource_cards":
                result = detect_top_resource_cards(image)
            elif request.get("mode") == "yellow_ad_control":
                result = detect_yellow_ad_control(image)
            elif request.get("mode") == "play_destination":
                result = detect_play_destination(image)
            else:
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
