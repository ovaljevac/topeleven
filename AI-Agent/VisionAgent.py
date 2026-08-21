#!/usr/bin/env python3
"""Guarded vision agent for Top Eleven ad navigation.

The process accepts one JSON request per stdin line and emits one JSON result.
It never controls the mouse. It only proposes an action that PowerShell validates.
"""

from __future__ import annotations

import argparse
import base64
import copy
import io
import json
import math
import os
import re
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
for dependency_dir in (ROOT / "pydeps", ROOT.parent / "pydeps"):
    if dependency_dir.is_dir():
        sys.path.insert(0, str(dependency_dir))

from PIL import Image, ImageDraw, ImageGrab


CAMPUS_REFERENCE_PATH = ROOT / "Kampus" / "4.png"
CAMPUS_SAFE_POINTS: dict[str, dict[str, Any]] = {
    # Points are deliberately inside a solid roof/field in the canonical
    # maintenance screenshot.  A homography moves them with the live camera;
    # they are never used as fixed screen coordinates.
    "omladinski_centar": {
        "aliases": ("omladinski centar", "youth academy", "youth centre", "youth center"),
        "point": (0.535, 0.455),
    },
    "odsek_za_tretmane": {
        "aliases": (
            "odsek za tretmane", "odsjek za tretmane", "treatment centre", "treatment center",
        ),
        "point": (0.770, 0.505),
    },
    "trening_centar": {
        "aliases": ("trening centar", "training centre", "training center"),
        "point": (0.650, 0.585),
    },
    "stadion": {
        "aliases": ("stadion", "stadium"),
        "point": (0.485, 0.635),
    },
    "parking": {
        "aliases": ("parking", "car park"),
        "point": (0.185, 0.690),
    },
    "prodaja_hrane": {
        "aliases": ("prodaja hrane", "food sales", "food stall"),
        "point": (0.275, 0.745),
    },
}


SCREEN_TYPES = {"top_eleven", "ad", "google_play_store", "play_google_chrome", "unknown"}
CONTROL_TYPES = {
    "close_x", "skip", "google_play", "back", "mourinho_warning",
    "campus_building", "campus_tool", "connection_confirm", "incidental_popup_close", "training_player", "training_condition_plus", "training_player_close", "none"
}
ACTIONS = {
    "click_close", "click_skip", "click_google_play", "click_target",
    "click_campus_building", "click_campus_tool", "click_connection_confirm", "click_incidental_popup_close", "click_training_player", "click_training_condition_plus",
    "click_training_player_close", "send_back", "none"
}
ACTION_CONTROL = {
    "click_close": "close_x",
    "click_skip": "skip",
    "click_google_play": "google_play",
    "click_target": "mourinho_warning",
    "click_campus_building": "campus_building",
    "click_campus_tool": "campus_tool",
    "click_connection_confirm": "connection_confirm",
    "click_incidental_popup_close": "incidental_popup_close",
    "click_training_player": "training_player",
    "click_training_condition_plus": "training_condition_plus",
    "click_training_player_close": "training_player_close",
    "send_back": "back",
    "none": "none",
}

RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "screenType": {"type": "string", "enum": sorted(SCREEN_TYPES)},
        "topElevenReturned": {"type": "boolean"},
        "control": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "type": {"type": "string", "enum": sorted(CONTROL_TYPES)},
                "x": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
                "y": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["type", "x", "y", "confidence"],
        },
        "recommendedAction": {"type": "string", "enum": sorted(ACTIONS)},
        "reason": {"type": "string"},
        "visibleText": {"type": "string"},
    },
    "required": [
        "screenType",
        "topElevenReturned",
        "control",
        "recommendedAction",
        "reason",
        "visibleText",
    ],
}

SYSTEM_PROMPT = """You are the visual decision engine for a Top Eleven ad automation.
Analyze only the supplied BlueStacks screenshot. Return data matching the JSON schema.
The supplied diagnostic image has the full BlueStacks screenshot on top, then
two magnified panels at the bottom labelled ORIGINAL TOP-LEFT and ORIGINAL
TOP-RIGHT. The lower panels duplicate the corresponding edges of the full
screenshot. Always report x/y normalized to the original full screenshot,
never to a magnified panel. The original coordinate origin is top-left.

Safety is more important than closing an ad:
- Never recommend clicking Install, Get, Buy, Subscribe, payment, consent, purchase, or an unknown button.
- Merely seeing Install/Get or another unsafe CTA does not hide a separate genuine X/skip,
  and does not prevent send_back on an external Store/Chrome screen. Mention the unsafe CTA
  in visibleText, ignore it, and still choose a clearly visible permitted control. Return
  recommendedAction=none only when no permitted control is visible.
- Use click_close only for a genuine X close control.
- Use click_skip only for a genuine skip or >> control.
- Use click_google_play only for the ad's Google Play, Play Store, or Visit Google Play
  badge/pill, never an Install/Get/Open/Buy button inside a store page.
- Control priority on an ad is: genuine close X first, then genuine >>/Skip,
  then an ad Google Play/Play Store badge only when no close or skip control is visible.
- Use send_back only on Google Play Store or play.google.com/Chrome destination screens.
- Use click_target only when expected state is exactly mourinho_warning. In that
  state it means the small square !/information button immediately to the right
  of the Nivo spremnosti/readiness progress bar and left of PREGLED UTAKMICE.
- Use click_campus_building only when expected state starts with
  campus_incomplete_building. Return a point well inside the solid clickable
  footprint of the BUILDING whose displayed maintenance percentage is below
  100%, never the percentage label itself.
- The action/control mapping is exact: click_close=close_x, click_skip=skip,
  click_google_play=google_play, click_target=mourinho_warning,
  click_campus_building=campus_building, send_back=back, and none=none.
- If no permitted control is visibly present, return control type none, x=null,
  y=null, confidence=0, and recommendedAction=none.
- Play Now, Continue, Interested and game-board graphics are not close/skip controls.
- Before returning none, carefully inspect the outer 14% of both the top-left
  and top-right edges. A genuine close control may be a very small gray or
  white X on a dark translucent circle. Ignore the BlueStacks title-bar and
  right-side emulator toolbar icons.
- If uncertain, return unknown/none with a low confidence.
- topElevenReturned is true only when the Top Eleven resource cards/header are visibly back.
Do not infer controls outside the screenshot and do not invent coordinates."""

AI_ONLY_SYSTEM_PROMPT = SYSTEM_PROMPT.replace(
    "The supplied diagnostic image has the full BlueStacks screenshot on top, then\n"
    "two magnified panels at the bottom labelled ORIGINAL TOP-LEFT and ORIGINAL\n"
    "TOP-RIGHT. The lower panels duplicate the corresponding edges of the full\n"
    "screenshot. Always report x/y normalized to the original full screenshot,\n"
    "never to a magnified panel. The original coordinate origin is top-left.",
    "The supplied image is the original full BlueStacks screenshot with no duplicate panels.\n"
    "Always report x/y normalized to this image. The coordinate origin is top-left.",
)


def load_config(path: Path) -> dict[str, Any]:
    defaults = {
        "enabled": True,
        "provider": "ollama",
        "endpoint": "http://127.0.0.1:11434/api/chat",
        "model": "qwen3-vl:4b",
        "apiKeyEnvironmentVariable": "GEMINI_API_KEY",
        "timeoutSeconds": 45,
        "minimumConfidence": 0.85,
        "requiredAgreementCount": 2,
        "coordinateTolerance": 0.035,
        "campusCoordinateTolerance": 0.06,
        "debugDirectory": "debug",
        "saveUnknownScreenshots": True,
    }
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            supplied = json.load(handle)
        defaults.update(supplied)
    return defaults


def capture_rect(rect: list[Any]) -> Image.Image:
    if len(rect) != 4:
        raise ValueError("rect must contain left, top, right, bottom")
    left, top, right, bottom = (int(value) for value in rect)
    if right <= left or bottom <= top:
        raise ValueError("invalid capture rectangle")
    return ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True).convert("RGB")


def encode_image(image: Image.Image) -> str:
    # Limit payload and inference cost while retaining small ad controls.
    max_width = 1600
    if image.width > max_width:
        height = round(image.height * max_width / image.width)
        image = image.resize((max_width, height), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=92, optimize=True)
    return base64.b64encode(output.getvalue()).decode("ascii")


def _fold_campus_text(value: str) -> str:
    folded = unicodedata.normalize("NFKD", str(value))
    folded = folded.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


def resolve_campus_target(visible_text: str) -> tuple[str, tuple[float, float]] | None:
    """Map the AI's visible facility name to one canonical safe map point."""
    match = re.search(
        r"\bTARGET\b\s*:?\s*(.+?)\s*(?:[;|,\n]\s*)?\bPERCENT\b\s*:?\s*(\d{1,3})\s*%",
        str(visible_text),
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    target = _fold_campus_text(match.group(1).strip(" \t;,:|-"))
    if not target:
        return None
    for key, specification in CAMPUS_SAFE_POINTS.items():
        aliases = (_fold_campus_text(alias) for alias in specification["aliases"])
        if any(target == alias or alias in target for alias in aliases):
            x, y = specification["point"]
            return key, (float(x), float(y))
    return None


def _campus_scene_mask(width: int, height: int):
    import numpy as np

    mask = np.zeros((height, width), dtype=np.uint8)
    mask[
        int(round(height * 0.20)):int(round(height * 0.95)),
        int(round(width * 0.06)):int(round(width * 0.94)),
    ] = 255
    return mask


def ground_campus_click_on_fresh_frame(
    fresh_image: Image.Image,
    decision: dict[str, Any],
) -> dict[str, Any]:
    """Ground an AI-selected Campus facility on the camera's current frame.

    The provider can take minutes to answer while the Campus camera keeps
    moving.  AI is therefore used for the semantic choice (facility and
    percentage), while a scene-only projective registration moves a known
    safe point inside that facility onto a capture taken after the answer.
    Nothing is clicked when registration quality is insufficient.
    """
    target = resolve_campus_target(str(decision.get("visibleText", "")))
    if target is None:
        return {"ok": False, "error": "unknown Campus facility name"}
    target_key, safe_point = target
    if not CAMPUS_REFERENCE_PATH.is_file():
        return {"ok": False, "error": "Campus reference image is missing", "target": target_key}

    try:
        import cv2
        import numpy as np
        import XDetector

        with Image.open(CAMPUS_REFERENCE_PATH) as reference_handle:
            reference_rgb = np.asarray(reference_handle.convert("RGB"))
        fresh_rgb = np.asarray(fresh_image.convert("RGB"))
        reference_bgr = cv2.cvtColor(reference_rgb, cv2.COLOR_RGB2BGR)
        fresh_bgr = cv2.cvtColor(fresh_rgb, cv2.COLOR_RGB2BGR)
        reference_height, reference_width = reference_bgr.shape[:2]
        fresh_height, fresh_width = fresh_bgr.shape[:2]
        if min(reference_width, fresh_width) < 600 or min(reference_height, fresh_height) < 400:
            return {"ok": False, "error": "Campus frame is too small", "target": target_key}

        fresh_state = XDetector.detect_campus_flow(fresh_bgr)
        if (
            fresh_state.get("state") != "campus_maintenance"
            or int(fresh_state.get("maintenanceBadgeCount", 0)) < 3
        ):
            return {
                "ok": False,
                "error": "fresh frame is not a confirmed Campus maintenance screen",
                "target": target_key,
                "freshState": str(fresh_state.get("state", "unknown")),
                "maintenanceBadgeCount": int(fresh_state.get("maintenanceBadgeCount", 0)),
            }

        reference_gray = cv2.cvtColor(reference_bgr, cv2.COLOR_BGR2GRAY)
        fresh_gray = cv2.cvtColor(fresh_bgr, cv2.COLOR_BGR2GRAY)
        detector = cv2.ORB_create(
            nfeatures=5000,
            scaleFactor=1.15,
            nlevels=10,
            edgeThreshold=12,
            fastThreshold=7,
        )
        reference_points, reference_descriptors = detector.detectAndCompute(
            reference_gray, _campus_scene_mask(reference_width, reference_height)
        )
        fresh_points, fresh_descriptors = detector.detectAndCompute(
            fresh_gray, _campus_scene_mask(fresh_width, fresh_height)
        )
        if reference_descriptors is None or fresh_descriptors is None:
            return {"ok": False, "error": "Campus scene has no usable features", "target": target_key}

        pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(
            reference_descriptors, fresh_descriptors, k=2
        )
        good_matches = [
            pair[0] for pair in pairs
            if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance
        ]
        if len(good_matches) < 40:
            return {
                "ok": False,
                "error": "too few Campus scene matches",
                "target": target_key,
                "goodMatches": len(good_matches),
            }

        source = np.float32([
            reference_points[match.queryIdx].pt for match in good_matches
        ])
        destination = np.float32([
            fresh_points[match.trainIdx].pt for match in good_matches
        ])
        homography, inlier_mask = cv2.findHomography(
            source,
            destination,
            cv2.RANSAC,
            5.0,
            maxIters=10000,
            confidence=0.999,
        )
        if homography is None or inlier_mask is None:
            return {"ok": False, "error": "Campus homography was not found", "target": target_key}

        inliers = inlier_mask.reshape(-1).astype(bool)
        inlier_count = int(np.sum(inliers))
        inlier_ratio = inlier_count / float(max(1, len(good_matches)))
        projected_matches = cv2.perspectiveTransform(source[:, None, :], homography)[:, 0, :]
        errors = np.linalg.norm(projected_matches - destination, axis=1)
        inlier_errors = errors[inliers]
        median_error = float(np.median(inlier_errors)) if inlier_count else float("inf")
        p90_error = float(np.percentile(inlier_errors, 90)) if inlier_count else float("inf")
        inlier_source = source[inliers]
        coverage_x = (
            float(np.ptp(inlier_source[:, 0])) / float(reference_width)
            if inlier_count else 0.0
        )
        coverage_y = (
            float(np.ptp(inlier_source[:, 1])) / float(reference_height)
            if inlier_count else 0.0
        )
        quadrants = {
            (
                int(point[0] >= reference_width * 0.50),
                int(point[1] >= reference_height * 0.575),
            )
            for point in inlier_source
        }
        if (
            inlier_count < 25
            or inlier_ratio < 0.35
            or median_error > 3.5
            or p90_error > 7.0
            or coverage_x < 0.45
            or coverage_y < 0.35
            or len(quadrants) < 3
        ):
            return {
                "ok": False,
                "error": "Campus scene registration quality is insufficient",
                "target": target_key,
                "goodMatches": len(good_matches),
                "inliers": inlier_count,
                "inlierRatio": round(inlier_ratio, 3),
                "medianError": round(median_error, 3),
                "p90Error": round(p90_error, 3),
                "coverageX": round(coverage_x, 3),
                "coverageY": round(coverage_y, 3),
                "quadrants": len(quadrants),
            }

        canonical = np.array([[[
            safe_point[0] * reference_width,
            safe_point[1] * reference_height,
        ]]], dtype=np.float32)
        grounded = cv2.perspectiveTransform(canonical, homography)[0, 0]
        grounded_x = float(grounded[0] / fresh_width)
        grounded_y = float(grounded[1] / fresh_height)
        if (
            not math.isfinite(grounded_x)
            or not math.isfinite(grounded_y)
            or not (0.05 <= grounded_x <= 0.88 and 0.25 <= grounded_y <= 0.92)
        ):
            return {
                "ok": False,
                "error": "grounded Campus point is outside the clickable map",
                "target": target_key,
            }

        ai_control = decision.get("control") or {}
        return {
            "ok": True,
            "method": "canonical-safe-point-homography",
            "target": target_key,
            "aiX": ai_control.get("x"),
            "aiY": ai_control.get("y"),
            "canonicalX": safe_point[0],
            "canonicalY": safe_point[1],
            "x": grounded_x,
            "y": grounded_y,
            "goodMatches": len(good_matches),
            "inliers": inlier_count,
            "inlierRatio": round(inlier_ratio, 3),
            "medianError": round(median_error, 3),
            "p90Error": round(p90_error, 3),
            "coverageX": round(coverage_x, 3),
            "coverageY": round(coverage_y, 3),
            "quadrants": len(quadrants),
            "maintenanceBadgeCount": int(fresh_state.get("maintenanceBadgeCount", 0)),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Campus grounding failed: {type(exc).__name__}: {exc}",
            "target": target_key,
        }


def detect_guarded_candidate(image: Image.Image) -> dict[str, Any] | None:
    """Use geometry only to point the AI at a possible edge control."""
    try:
        import cv2
        import numpy as np
        import XDetector

        rgb = np.asarray(image.convert("RGB"))
        result = XDetector.run_detector(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), live=True)
        if result.get("found"):
            return result
        result = XDetector.detect_yellow_ad_control(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        if result.get("found"):
            return result
    except Exception:
        return None
    return None


def _mark_candidate(draw: ImageDraw.ImageDraw, x: float, y: float, radius: int) -> None:
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline="yellow", width=5)


def build_diagnostic_image(
    image: Image.Image, candidate: dict[str, Any] | None = None
) -> Image.Image:
    """Keep full context while magnifying tiny ad controls at both top edges."""
    image = image.convert("RGB")
    width, height = image.size
    if width < 200 or height < 120:
        return image

    target_width = 800 if height > width * 1.25 else 1400
    full_height = max(1, round(height * target_width / width))
    full = image.resize((target_width, full_height), Image.Resampling.LANCZOS)

    crop_width = max(1, round(width * 0.20))
    crop_height = max(1, round(height * 0.24))
    focus_height = 360
    half_width = target_width // 2
    top_left = image.crop((0, 0, crop_width, crop_height)).resize(
        (half_width, focus_height), Image.Resampling.LANCZOS
    )
    top_right = image.crop((width - crop_width, 0, width, crop_height)).resize(
        (target_width - half_width, focus_height), Image.Resampling.LANCZOS
    )

    label_height = 28
    canvas = Image.new("RGB", (target_width, full_height + label_height + focus_height), "black")
    canvas.paste(full, (0, 0))
    canvas.paste(top_left, (0, full_height + label_height))
    canvas.paste(top_right, (half_width, full_height + label_height))
    labels = ImageDraw.Draw(canvas)
    labels.text((8, full_height + 7), "ORIGINAL TOP-LEFT (MAGNIFIED)", fill="white")
    labels.text((half_width + 8, full_height + 7), "ORIGINAL TOP-RIGHT (MAGNIFIED)", fill="white")
    if candidate:
        x = float(candidate["x"])
        y = float(candidate["y"])
        _mark_candidate(labels, x * target_width, y * full_height, 24)
        if x <= 0.20 and y <= 0.24:
            _mark_candidate(
                labels,
                (x / 0.20) * half_width,
                full_height + label_height + (y / 0.24) * focus_height,
                36,
            )
        elif x >= 0.80 and y <= 0.24:
            _mark_candidate(
                labels,
                half_width + ((x - 0.80) / 0.20) * (target_width - half_width),
                full_height + label_height + (y / 0.24) * focus_height,
                36,
            )
        labels.text(
            (8, full_height - 22),
            f"YELLOW CIRCLE = UNTRUSTED {candidate.get('kind', 'control')} CANDIDATE",
            fill="yellow",
        )
    return canvas


def request_ollama(image: Image.Image, expected_state: str, config: dict[str, Any]) -> dict[str, Any]:
    candidate = detect_guarded_candidate(image)
    candidate_prompt = ""
    if candidate:
        candidate_description = (
            " A geometric sensor marked one UNTRUSTED candidate with a yellow circle: "
            f"kind={candidate.get('kind', 'close')}, original x={float(candidate['x']):.4f}, "
            f"original y={float(candidate['y']):.4f}. Visually verify the pixels inside the circle."
        )
        if expected_state == "external_navigation":
            candidate_prompt = candidate_description + (
                " If the full screen is Google Play Store or a play.google.com/Chrome destination, "
                "return send_back with control type back; otherwise return none."
            )
        else:
            candidate_prompt = candidate_description + (
                " If and only if it is a genuine close/skip/Google Play ad control, use the matching "
                "action and these exact original coordinates; otherwise return none."
            )
    prompt = (
        f"Expected state from the deterministic state machine: {expected_state}. "
        "Inspect the screenshot and propose exactly one safe next action. "
        "Return only the schema-conforming object."
        + candidate_prompt
    )
    payload = {
        "model": config["model"],
        "stream": False,
        "think": bool(config.get("thinking", False)),
        "format": RESULT_SCHEMA,
        "options": {
            "temperature": 0,
            "num_ctx": int(config.get("contextLength", 2048)),
            "num_predict": int(config.get("maximumOutputTokens", 256)),
        },
        "keep_alive": str(config.get("keepAlive", "30m")),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": prompt,
                "images": [encode_image(build_diagnostic_image(image, candidate))],
            },
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        str(config["endpoint"]),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=float(config["timeoutSeconds"])) as response:
            envelope = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(response_text).get("error", response_text)
        except json.JSONDecodeError:
            detail = response_text
        raise RuntimeError(f"Ollama HTTP {exc.code}: {detail or exc.reason}") from exc
    message = envelope.get("message", {})
    content = message.get("content")
    # Ollama's qwen3-vl thinking parser can place schema-conforming final JSON
    # in message.thinking even when think=false. Accept that field only as raw
    # JSON; the normal safety validator still rejects contradictory actions,
    # unsafe text and out-of-zone coordinates.
    if not isinstance(content, str) or not content.strip():
        thinking_content = message.get("thinking")
        if isinstance(thinking_content, str) and thinking_content.lstrip().startswith("{"):
            content = thinking_content
    if not isinstance(content, str) or not content.strip():
        raise ValueError(
            "Ollama response has no final message.content "
            f"(done_reason={envelope.get('done_reason', 'unknown')})"
        )
    return json.loads(content)


def build_user_prompt(
    image: Image.Image, expected_state: str
) -> tuple[str, Image.Image]:
    ai_only = "ai_only" in expected_state
    external_navigation = expected_state.startswith("external_navigation")
    mourinho_warning = expected_state == "mourinho_warning"
    campus_building = expected_state.startswith("campus_incomplete_building")
    campus_tool = expected_state.startswith("campus_tool_icon")
    connection_popup = expected_state.startswith("connection_interrupted_popup")
    incidental_popup = expected_state.startswith("incidental_top_eleven_popup")
    training_setup = expected_state.startswith("training_setup_condition")
    training_profile = expected_state.startswith("training_profile_condition")
    campus_avoid_points = (
        [
            (int(match.group(1)) / 1000, int(match.group(2)) / 1000)
            for match in re.finditer(r"_avoid_(\d{1,4})_(\d{1,4})(?=_|$)", expected_state)
        ]
        if campus_building
        else []
    )
    candidate = (
        None if ai_only or external_navigation or mourinho_warning or campus_building or campus_tool or connection_popup or incidental_popup or training_setup or training_profile
        else detect_guarded_candidate(image)
    )
    candidate_prompt = ""
    if candidate:
        candidate_description = (
            " A geometric sensor marked one UNTRUSTED candidate with a yellow circle: "
            f"kind={candidate.get('kind', 'close')}, original x={float(candidate['x']):.4f}, "
            f"original y={float(candidate['y']):.4f}. Visually verify the pixels inside the circle."
        )
        if expected_state == "external_navigation":
            candidate_prompt = candidate_description + (
                " If the full screen is Google Play Store or a play.google.com/Chrome destination, "
                "return send_back with control type back; otherwise return none."
            )
        else:
            candidate_prompt = candidate_description + (
                " If and only if it is a genuine close/skip/Google Play ad control, use the matching "
                "action and these exact original coordinates; otherwise return none."
            )
    if mourinho_warning:
        prompt = (
            "The screenshot is expected to show the Top Eleven home screen. Locate exactly "
            "one small square information/warning button immediately to the RIGHT of the "
            "horizontal readiness progress bar labelled 'Nivo spremnosti' and to the LEFT of "
            "the large 'PREGLED UTAKMICE' button. The target may be red with a white !, yellow "
            "with a dark ! or i, and its position may move with the window layout. Return the "
            "CENTER of that small square in coordinates normalized to the full supplied image. "
            "If clearly visible return screenType=top_eleven, control.type=mourinho_warning, "
            "recommendedAction=click_target and confidence. Do not select the TV icon, chat "
            "button, progress bar, PREGLED UTAKMICE, an ad, or any other square. If the exact "
            "target is not visible return control.type=none and recommendedAction=none. "
            "Return only the schema-conforming object."
        )
        return prompt, image

    if campus_building:
        retry_instruction = ""
        tie_instruction = (
            "Choose the lowest percentage. If several facilities share that same lowest value, "
            "always choose the facility whose PERCENTAGE BADGE center is farthest LEFT; if still "
            "tied, choose the highest badge. "
        )
        if campus_avoid_points:
            image = image.copy()
            draw = ImageDraw.Draw(image)
            marker_radius = max(10, round(min(image.size) * 0.022))
            for avoid_x, avoid_y in campus_avoid_points:
                marker_x = round(avoid_x * image.width)
                marker_y = round(avoid_y * image.height)
                box = (
                    marker_x - marker_radius,
                    marker_y - marker_radius,
                    marker_x + marker_radius,
                    marker_y + marker_radius,
                )
                draw.ellipse(box, outline=(255, 30, 30), width=max(3, marker_radius // 4))
                draw.line(
                    (box[0], box[1], box[2], box[3]),
                    fill=(255, 30, 30),
                    width=max(3, marker_radius // 4),
                )
                draw.line(
                    (box[0], box[3], box[2], box[1]),
                    fill=(255, 30, 30),
                    width=max(3, marker_radius // 4),
                )
            avoided = ", ".join(f"({x:.3f}, {y:.3f})" for x, y in campus_avoid_points)
            retry_instruction = (
                f" Previous clicks at {avoided} did not open a facility detail. Those failed "
                "points are marked by RED CROSSED CIRCLES on the supplied image. Re-inspect the "
                "facility independently and choose a different solid interior point outside all "
                "red markers; never repeat or click close to any marked point."
            )
            tie_instruction = (
                "Choose the lowest percentage. On this retry, if several facilities share that "
                "value, prefer a DIFFERENT valid facility whose solid footprint contains no red "
                "marker. Only reuse the same facility when it has a clearly separate solid interior "
                "area far from every marker. Then use leftmost badge, followed by highest badge, "
                "as the remaining tie-break. "
            )
        prompt = (
            "The screenshot is expected to show the Top Eleven Campus maintenance overview. "
            "Several campus buildings have percentage labels such as 60%, 90% or 100%. Find "
            "one building whose OWN displayed maintenance percentage is strictly below 100%. "
            + tie_instruction
            + "First associate the selected "
            "percentage with its facility, then return a point WELL INSIDE the broad, opaque, "
            "clickable footprint of that facility: its roof, walls, playing field or paved facility "
            "area. Keep the point away from every edge. Do NOT return the percentage badge, the "
            "facility name, a progress bar, a road, generic grass, a tree, a shadow, the city "
            "background or empty space. If found return screenType=top_eleven, "
            "control.type=campus_building and recommendedAction=click_campus_building with "
            "coordinates normalized to the full supplied image. Set visibleText exactly in the "
            "form 'TARGET: <facility name>; PERCENT: <NN%>' so the caller can validate that the "
            "selected facility is actually below 100%. "
            + retry_instruction
            + " "
            "If every visible building is 100%, return control.type=none, "
            "recommendedAction=none and null coordinates. Return only the schema-conforming object."
        )
        return prompt, image

    if campus_tool:
        prompt = (
            "The screenshot is expected to show the main Top Eleven CAMPUS screen. Locate exactly "
            "the white square tool button on the LEFT side of the Campus view containing the black "
            "crossed wrench/screwdriver tools icon. Return the CENTER of that white square in "
            "coordinates normalized to the full supplied image, with screenType=top_eleven, "
            "control.type=campus_tool and recommendedAction=click_campus_tool. Do not select the "
            "Campus header icon, side-menu chevron, percentage badge, building, resource plus, "
            "BlueStacks toolbar icon, or any other button. If the exact crossed-tools square is not "
            "clearly visible, return control.type=none, recommendedAction=none and null coordinates. "
            "Return only the schema-conforming object."
        )
        return prompt, image

    if connection_popup:
        prompt = (
            "Inspect the full Top Eleven screenshot for the modal titled 'VEZA JE PREKINUTA' with "
            "the message 'Greska pri povezivanju. Pokusaj kasnije!' (text may contain Serbian "
            "diacritics). If and only if that connection-interrupted modal is clearly visible, "
            "locate the CENTER of its large GREEN confirmation button containing a white checkmark. "
            "Return screenType=top_eleven, control.type=connection_confirm, "
            "recommendedAction=click_connection_confirm and normalized full-image coordinates. "
            "Do not select a green game action, resource plus, ad button, player-condition plus, or "
            "any X. If this exact connection modal is absent, return control.type=none, "
            "recommendedAction=none and null coordinates. Return only the schema-conforming object."
        )
        return prompt, image

    if incidental_popup:
        prompt = (
            "The automation is blocked by an unexpected in-game Top Eleven modal. Determine whether "
            "a foreground modal/promotion panel clearly overlays and blocks the underlying game "
            "screen. Examples include an offer such as EKSPERTSKA KONDICIJA. If a blocking modal is "
            "visible and has its own explicit X or Close control in the modal header, locate the "
            "CENTER of that modal-local close control and return screenType=top_eleven, "
            "control.type=incidental_popup_close and recommendedAction=click_incidental_popup_close. "
            "Never select the BlueStacks title-bar X, an advertisement X, a player-profile X, a "
            "purchase/price button, green action button, resource plus, side menu, or background "
            "control. If no clearly separate blocking modal with its own close control exists, return "
            "control.type=none, recommendedAction=none and null coordinates. Return only the "
            "schema-conforming object."
        )
        return prompt, image

    if training_setup:
        prompt = (
            "The screenshot is the Top Eleven training setup screen after PONOVI. Read the literal "
            "FIT percentage printed on every selected player row; decide from the NUMBER text, not "
            "from bar color or bar width. Find the smallest visible FIT percentage. If it is below "
            "30%, return screenType=top_eleven, control.type=training_player, "
            "recommendedAction=click_training_player and the center of that player's full row. Set "
            "visibleText exactly to 'CONDITION: NN%'. If every selected player is at least 30%, "
            "return control.type=none, recommendedAction=none, null coordinates, and visibleText "
            "exactly 'LOWEST_CONDITION: NN%' using the smallest number you read. Never select "
            "ZAPOCNI TRENING, a drill card, FIT header, progress bar, or a guessed coordinate. If "
            "the percentage text is unreadable, return screenType=unknown and visibleText empty. "
            "Return only the schema-conforming object."
        )
        return prompt, image

    if training_profile:
        prompt = (
            "The screenshot is expected to show one Top Eleven player profile or its condition "
            "recovery modal. Read the literal percentage number next to KONDICIJA. Do not estimate "
            "from the colored bar. If the number is below 85%, locate the CENTER of the GREEN + "
            "button in the KONDICIJA panel immediately to the right of that percentage and return "
            "screenType=top_eleven, control.type=training_condition_plus, "
            "recommendedAction=click_training_condition_plus, and its coordinates normalized to "
            "the full supplied image. Do not select the + under POVREDE or MORAL. If the number is "
            "85% through 100%, locate the CENTER of the white X inside the gray PLAYER PROFILE "
            "header at the upper-right of the profile panel and return "
            "control.type=training_player_close and recommendedAction=click_training_player_close. "
            "Do not select the BlueStacks title-bar X above the game, any advertisement X, or an X "
            "from another modal. "
            "In both cases set visibleText exactly to 'CONDITION: NN%'. "
            "If the literal condition percentage is not readable, return screenType=unknown and "
            "visibleText empty. Return only the schema-conforming object."
        )
        return prompt, image

    if external_navigation:
        prompt = (
            "Inspect the original full screenshot and decide only whether Google Play Store or "
            "a play.google.com/Chrome destination is CURRENTLY visible. If it is visible, return "
            "screenType=google_play_store for the Store or screenType=play_google_chrome for "
            "a Chrome destination, control.type=back, recommendedAction=send_back, "
            "x=null and y=null. If the ad or Top Eleven is visible instead, return control.type=none "
            "and recommendedAction=none. Do not use a remembered previous screen and do not return "
            "coordinates for Back. Return only the schema-conforming object."
        )
        return prompt, image

    prompt = (
        f"Expected state from the deterministic state machine: {expected_state}. "
        "Inspect the screenshot and propose exactly one safe next action. "
        "Return only the schema-conforming object."
        + candidate_prompt
    )
    if ai_only:
        prompt += (
            " The deterministic automation is requesting an independent AI-only control check. "
            "Independently inspect the full screenshot. "
            "If the ad is gone and the current screen is Top Eleven, set screenType=top_eleven and "
            "topElevenReturned=true only when the real Top Eleven header is visible with several "
            "resource counters/cards across the top (tokens, green rests, blue morale, red health "
            "and/or cash). In that case return control.type=none and recommendedAction=none. A "
            "single ad counter, coin badge, store header, emulator title bar, or ad graphic is not "
            "the Top Eleven resource header. If Top Eleven has returned to a player profile, its "
            "profile X and green condition + are GAME controls, not ad controls: still return none. "
            "Look especially for a small X attached to a Reward granted label, a close X, "
            "or a genuine >>/skip control. If no close or skip control is visible, also look "
            "for the ad's Google Play, Play Store, or Visit Google Play badge, including a "
            "very small Google Play disclosure badge at the ad's TOP-LEFT edge, and return "
            "click_google_play. Never choose Install, Get, Open, Buy, Learn More, or a store-page "
            "button. Do not require or expect a yellow marker."
        )
    return prompt, image if ai_only else build_diagnostic_image(image, candidate)


def get_secret_environment_variable(name: str) -> str | None:
    """Read a secret without ever copying it into config or logs.

    User environment changes are stored in the registry immediately, while an
    already-running Explorer/Codex process can retain an older environment.
    """
    value = os.environ.get(name)
    if value:
        return value.strip()

    env_path = ROOT / ".env"
    if env_path.is_file():
        try:
            for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, supplied_value = line.split("=", 1)
                if key.strip() != name:
                    continue
                supplied_value = supplied_value.strip()
                if (
                    len(supplied_value) >= 2
                    and supplied_value[0] == supplied_value[-1]
                    and supplied_value[0] in {"'", '"'}
                ):
                    supplied_value = supplied_value[1:-1]
                if supplied_value:
                    return supplied_value
        except OSError:
            pass

    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                registry_value, _ = winreg.QueryValueEx(key, name)
            if isinstance(registry_value, str) and registry_value.strip():
                return registry_value.strip()
        except (FileNotFoundError, OSError):
            pass
    return None


def gemini_response_schema() -> dict[str, Any]:
    """OpenAPI-style schema accepted by generateContent responseSchema."""
    return {
        "type": "OBJECT",
        "properties": {
            "screenType": {"type": "STRING", "enum": sorted(SCREEN_TYPES)},
            "topElevenReturned": {"type": "BOOLEAN"},
            "control": {
                "type": "OBJECT",
                "properties": {
                    "type": {"type": "STRING", "enum": sorted(CONTROL_TYPES)},
                    "x": {"type": "NUMBER", "nullable": True},
                    "y": {"type": "NUMBER", "nullable": True},
                    "confidence": {"type": "NUMBER"},
                },
                "required": ["type", "x", "y", "confidence"],
            },
            "recommendedAction": {"type": "STRING", "enum": sorted(ACTIONS)},
            "reason": {"type": "STRING"},
            "visibleText": {"type": "STRING"},
        },
        "required": [
            "screenType",
            "topElevenReturned",
            "control",
            "recommendedAction",
            "reason",
            "visibleText",
        ],
    }


def request_gemini(image: Image.Image, expected_state: str, config: dict[str, Any]) -> dict[str, Any]:
    key_name = str(config.get("apiKeyEnvironmentVariable", "GEMINI_API_KEY"))
    api_key = get_secret_environment_variable(key_name)
    if not api_key:
        raise RuntimeError(
            f"Gemini API key is missing. Add {key_name}=... to AI-Agent/.env."
        )

    prompt, diagnostic_image = build_user_prompt(image, expected_state)
    endpoint_template = str(
        config.get(
            "endpoint",
            "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        )
    )
    endpoint = endpoint_template.replace("{model}", str(config["model"]))
    generation_config: dict[str, Any] = {
        "maxOutputTokens": int(config.get("maximumOutputTokens", 256)),
        "responseMimeType": "application/json",
        "responseSchema": gemini_response_schema(),
    }
    model_name = str(config["model"])
    if model_name.startswith("gemini-3"):
        generation_config["thinkingConfig"] = {
            "thinkingLevel": str(config.get("thinkingLevel", "minimal"))
        }
    else:
        generation_config["temperature"] = 0
        generation_config["thinkingConfig"] = {
            "thinkingBudget": int(config.get("thinkingBudget", 0))
        }
    payload = {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        AI_ONLY_SYSTEM_PROMPT
                        if "ai_only" in expected_state
                        or expected_state.startswith("external_navigation")
                        or expected_state == "mourinho_warning"
                        or expected_state.startswith("campus_incomplete_building")
                        else SYSTEM_PROMPT
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"inlineData": {"mimeType": "image/jpeg", "data": encode_image(diagnostic_image)}},
                    {"text": prompt},
                ],
            }
        ],
        "generationConfig": generation_config,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=float(config["timeoutSeconds"])) as response:
            envelope = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        try:
            error = json.loads(response_text).get("error", {})
            detail = error.get("message", error) if isinstance(error, dict) else error
        except json.JSONDecodeError:
            detail = response_text
        raise RuntimeError(f"Gemini HTTP {exc.code}: {detail or exc.reason}") from exc

    candidates = envelope.get("candidates") or []
    if not candidates:
        block_reason = (envelope.get("promptFeedback") or {}).get("blockReason", "unknown")
        raise ValueError(f"Gemini response has no candidate (blockReason={block_reason})")
    parts = ((candidates[0].get("content") or {}).get("parts") or [])
    content = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    if not content.strip():
        raise ValueError(
            "Gemini response has no text "
            f"(finishReason={candidates[0].get('finishReason', 'unknown')})"
        )
    return json.loads(content)


def request_vision_model(
    image: Image.Image, expected_state: str, config: dict[str, Any]
) -> dict[str, Any]:
    provider = str(config.get("provider", "ollama")).strip().lower()
    if provider == "ollama":
        return request_ollama(image, expected_state, config)
    if provider == "gemini":
        return request_gemini(image, expected_state, config)
    raise ValueError(f"Unsupported vision provider: {provider}")


def validate_decision(
    raw: Any,
    config: dict[str, Any],
    expected_state: str = "",
    image_size: tuple[int, int] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    ai_only = "ai_only" in expected_state
    mourinho_warning = expected_state == "mourinho_warning"
    campus_building = expected_state.startswith("campus_incomplete_building")
    campus_tool = expected_state.startswith("campus_tool_icon")
    connection_popup = expected_state.startswith("connection_interrupted_popup")
    incidental_popup = expected_state.startswith("incidental_top_eleven_popup")
    training_setup = expected_state.startswith("training_setup_condition")
    training_profile = expected_state.startswith("training_profile_condition")
    campus_avoid_points = (
        [
            (int(match.group(1)) / 1000, int(match.group(2)) / 1000)
            for match in re.finditer(r"_avoid_(\d{1,4})_(\d{1,4})(?=_|$)", expected_state)
        ]
        if campus_building
        else []
    )
    if not isinstance(raw, dict):
        return {}, ["response is not an object"]

    screen_type = raw.get("screenType")
    action = raw.get("recommendedAction")
    control = raw.get("control")
    # In an ad-only check, a positively identified Top Eleven return always wins.
    # Profile/game controls must never be clicked by the ad watcher. Some models
    # correctly identify the resource header but still suggest the visible profile X;
    # normalize that suggestion to the only safe ad-watcher result: no click/returned.
    if ai_only and screen_type == "top_eleven" and bool(raw.get("topElevenReturned", False)):
        action = "none"
        control = {"type": "none", "x": None, "y": None, "confidence": 0.0}
    if screen_type not in SCREEN_TYPES:
        errors.append("invalid screenType")
    if action not in ACTIONS:
        errors.append("invalid recommendedAction")
    if not isinstance(control, dict):
        errors.append("control is not an object")
        control = {}

    control_type = control.get("type")
    if control_type not in CONTROL_TYPES:
        errors.append("invalid control type")
    if action in ACTION_CONTROL and control_type != ACTION_CONTROL[action]:
        errors.append("action and control do not match")
    if action == "click_target" and not mourinho_warning:
        errors.append("click_target is only allowed for mourinho_warning")
    if action == "click_campus_building" and not campus_building:
        errors.append("click_campus_building is only allowed for campus_incomplete_building")
    if action == "click_campus_tool" and not campus_tool:
        errors.append("click_campus_tool is only allowed for campus_tool_icon")
    if action == "click_connection_confirm" and not connection_popup:
        errors.append("click_connection_confirm is only allowed for connection_interrupted_popup")
    if action == "click_incidental_popup_close" and not incidental_popup:
        errors.append("click_incidental_popup_close is only allowed for incidental_top_eleven_popup")
    if action == "click_training_player" and not training_setup:
        errors.append("click_training_player is only allowed for training_setup_condition")
    if action == "click_training_condition_plus" and not training_profile:
        errors.append("click_training_condition_plus is only allowed for training_profile_condition")
    if action == "click_training_player_close" and not training_profile:
        errors.append("click_training_player_close is only allowed for training_profile_condition")

    try:
        confidence = float(control.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
        errors.append("invalid confidence")
    if not 0 <= confidence <= 1:
        errors.append("confidence outside 0..1")

    x, y = control.get("x"), control.get("y")
    if action.startswith("click_"):
        try:
            x, y = float(x), float(y)
        except (TypeError, ValueError):
            errors.append("click action has no numeric coordinates")
            x = y = None
        if (
            (ai_only or mourinho_warning or campus_building or campus_tool or connection_popup or incidental_popup or training_setup or training_profile)
            and x is not None
            and (x > 1 or y > 1)
        ):
            if 0 <= x <= 1000 and 0 <= y <= 1000:
                # Gemini spatial grounding commonly uses a normalized 0..1000
                # coordinate scale even when the response schema requests 0..1.
                x = x / 1000
                y = y / 1000
            elif image_size is not None:
                image_width, image_height = image_size
                if 0 <= x <= image_width and 0 <= y <= image_height:
                    # Also accept literal pixel coordinates as a fallback.
                    x = x / image_width
                    y = y / image_height
        if x is not None and not (0 <= x <= 1 and 0 <= y <= 1):
            errors.append("coordinates outside 0..1")
        if x is not None and not ai_only and action in {"click_close", "click_skip"}:
            if y > 0.35 or not (x <= 0.40 or x >= 0.60):
                errors.append("close/skip coordinate outside guarded edge zone")
        if x is not None and not ai_only and action == "click_google_play" and (x < 0.55 or y > 0.35):
            errors.append("Google Play coordinate outside guarded top-right zone")
        if x is not None and mourinho_warning and action == "click_target":
            if not (0.42 <= x <= 0.65 and 0.70 <= y <= 1.0):
                errors.append("Mourinho warning coordinate outside readiness-bar zone")
        if x is not None and campus_building and action == "click_campus_building":
            if not (0.05 <= x <= 0.88 and 0.25 <= y <= 0.92):
                errors.append("Campus building coordinate outside campus object zone")
            for avoid_x, avoid_y in campus_avoid_points:
                if math.hypot(x - avoid_x, y - avoid_y) < 0.02:
                    errors.append("Campus retry repeated a previously failed coordinate")
                    break
        if x is not None and campus_tool and action == "click_campus_tool":
            if not (0.01 <= x <= 0.20 and 0.15 <= y <= 0.48):
                errors.append("Campus tool coordinate outside left Campus tool zone")
        if x is not None and connection_popup and action == "click_connection_confirm":
            if not (0.25 <= x <= 0.75 and 0.45 <= y <= 0.85):
                errors.append("connection confirmation coordinate outside modal button zone")
        if x is not None and incidental_popup and action == "click_incidental_popup_close":
            if not (0.15 <= x <= 0.95 and 0.08 <= y <= 0.48):
                errors.append("incidental popup close coordinate outside modal header zone")
        if x is not None and training_setup and action == "click_training_player":
            if not (0.02 <= x <= 0.95 and 0.42 <= y <= 0.95):
                errors.append("training player coordinate outside selected-player row zone")
        if x is not None and training_profile and action == "click_training_condition_plus":
            if not (0.72 <= x <= 0.95 and 0.45 <= y <= 0.82):
                errors.append("training condition plus coordinate outside KONDICIJA panel zone")
        if x is not None and training_profile and action == "click_training_player_close":
            if not (0.72 <= x <= 0.96 and 0.05 <= y <= 0.24):
                errors.append("training player X coordinate outside profile header zone")
    elif action == "send_back":
        # Gemini sometimes grounds the Android Back action to a visible arrow.
        # Back is a key action, so coordinates are intentionally discarded.
        x = y = None
    elif x is not None or y is not None:
        errors.append("non-click action must have null coordinates")

    visible_text = str(raw.get("visibleText", ""))[:500]
    if campus_building and action == "click_campus_building":
        campus_target = re.search(
            r"\bTARGET\b\s*:?\s*(.+?)\s*(?:[;|,\n]\s*)?\bPERCENT\b\s*:?\s*(\d{1,3})\s*%",
            visible_text,
            flags=re.IGNORECASE,
        )
        target_name = (
            campus_target.group(1).strip(" \t;,:|-")
            if campus_target is not None
            else ""
        )
        if campus_target is None or not target_name:
            errors.append("Campus click has no parsable TARGET/PERCENT text")
        elif int(campus_target.group(2)) >= 100:
            errors.append("Campus click target is not below 100%")
    if training_setup:
        if action == "click_training_player":
            condition_match = re.fullmatch(
                r"\s*CONDITION\s*:\s*(\d{1,3})\s*%\s*", visible_text, flags=re.IGNORECASE
            )
            if condition_match is None:
                errors.append("training player click has no exact CONDITION percentage")
            elif int(condition_match.group(1)) >= 30:
                errors.append("training player click condition is not below 30%")
        elif action == "none":
            lowest_match = re.fullmatch(
                r"\s*LOWEST_CONDITION\s*:\s*(\d{1,3})\s*%\s*", visible_text, flags=re.IGNORECASE
            )
            if lowest_match is None:
                errors.append("training setup none decision has no LOWEST_CONDITION percentage")
            elif not 30 <= int(lowest_match.group(1)) <= 100:
                errors.append("training setup none decision is not safely at least 30%")
    if training_profile:
        profile_match = re.fullmatch(
            r"\s*CONDITION\s*:\s*(\d{1,3})\s*%\s*", visible_text, flags=re.IGNORECASE
        )
        if action not in {"click_training_condition_plus", "click_training_player_close"} or profile_match is None:
            errors.append("training profile decision must contain exact CONDITION percentage")
        else:
            profile_condition = int(profile_match.group(1))
            if not 0 <= profile_condition <= 100:
                errors.append("training profile condition outside 0..100")
            elif profile_condition < 85 and action != "click_training_condition_plus":
                errors.append("training profile below 85% must target KONDICIJA plus")
            elif profile_condition >= 85 and action != "click_training_player_close":
                errors.append("training profile at 85% or more must target profile X")
    dangerous_pattern = r"\b(install|get|buy|purchase|subscribe|payment|placanje|kupi)\b"
    ai_only_close = ai_only and action in {"click_close", "click_skip"}
    safe_recovery_control = (
        connection_popup and action == "click_connection_confirm"
    ) or (
        incidental_popup and action == "click_incidental_popup_close"
    )
    if action not in {"none", "send_back"} and not ai_only_close and not safe_recovery_control and re.search(dangerous_pattern, visible_text, flags=re.IGNORECASE):
        errors.append("dangerous commerce/install text is visible")

    normalized = {
        "screenType": screen_type if screen_type in SCREEN_TYPES else "unknown",
        "topElevenReturned": bool(raw.get("topElevenReturned", False)),
        "control": {
            "type": control_type if control_type in CONTROL_TYPES else "none",
            "x": x,
            "y": y,
            "confidence": confidence,
        },
        "recommendedAction": action if action in ACTIONS else "none",
        "reason": str(raw.get("reason", ""))[:500],
        "visibleText": visible_text,
    }
    if not ai_only and confidence < float(config["minimumConfidence"]) and action != "none":
        errors.append("confidence below configured minimum")
    return normalized, errors


def same_decision(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    tolerance: float,
    expected_state: str = "",
) -> bool:
    if not previous:
        return False
    if previous["recommendedAction"] != current["recommendedAction"]:
        return False
    if previous["screenType"] != current["screenType"]:
        return False
    old_control, new_control = previous["control"], current["control"]
    if old_control["type"] != new_control["type"]:
        return False
    if (
        expected_state.startswith("campus_incomplete_building")
        and current["recommendedAction"] == "click_campus_building"
    ):
        old_target = re.sub(r"\s+", " ", str(previous.get("visibleText", ""))).strip().casefold()
        new_target = re.sub(r"\s+", " ", str(current.get("visibleText", ""))).strip().casefold()
        if not old_target or old_target != new_target:
            return False
    if current["recommendedAction"].startswith("click_"):
        return (
            abs(float(old_control["x"]) - float(new_control["x"])) <= tolerance
            and abs(float(old_control["y"]) - float(new_control["y"])) <= tolerance
        )
    return True


def select_pixel_control_candidate(
    decision: dict[str, Any], candidates: list[dict[str, Any]], maximum_distance: float = 0.08
) -> dict[str, Any] | None:
    """Match an AI-selected control to its exact pixel center without offsets."""
    expected_kind = {
        "click_close": "close",
        "click_skip": "skip",
        "click_google_play": "google_play",
    }.get(decision.get("recommendedAction"))
    if expected_kind is None:
        return None

    control = decision.get("control") or {}
    try:
        ai_x, ai_y = float(control["x"]), float(control["y"])
    except (KeyError, TypeError, ValueError):
        return None

    matching: list[tuple[float, dict[str, Any]]] = []
    for candidate in candidates:
        if not candidate or not candidate.get("found") or candidate.get("kind") != expected_kind:
            continue
        try:
            pixel_x, pixel_y = float(candidate["x"]), float(candidate["y"])
        except (KeyError, TypeError, ValueError):
            continue
        distance = math.hypot(pixel_x - ai_x, pixel_y - ai_y)
        if distance <= maximum_distance:
            matching.append((distance, candidate))
    return min(matching, key=lambda item: item[0])[1] if matching else None


def refine_decision_control_center(
    image: Image.Image, decision: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Use AI for meaning and the same screenshot's pixels for the exact center."""
    action = decision.get("recommendedAction")
    if action not in {"click_close", "click_skip", "click_google_play"}:
        return decision, None


def refine_ai_close_on_fresh_frame(
    image: Image.Image, decision: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Locally center a close X without allowing pixels to choose the action."""
    if decision.get("recommendedAction") != "click_close":
        return decision, {"ok": True, "applied": False, "reason": "not-close"}
    try:
        import cv2
        import numpy as np
        import XDetector

        ai_x = float(decision["control"]["x"])
        ai_y = float(decision["control"]["y"])
        rgb = np.asarray(image.convert("RGB"))
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        candidate = XDetector.refine_close_x_near_point(bgr, ai_x, ai_y)
        if not candidate.get("found"):
            return decision, {
                "ok": False,
                "applied": False,
                "reason": str(candidate.get("reason", "local X not verified")),
                "aiX": ai_x,
                "aiY": ai_y,
            }
        refined = copy.deepcopy(decision)
        refined["control"]["x"] = float(candidate["x"])
        refined["control"]["y"] = float(candidate["y"])
        return refined, {
            "ok": True,
            "applied": True,
            "aiX": ai_x,
            "aiY": ai_y,
            "pixelX": float(candidate["x"]),
            "pixelY": float(candidate["y"]),
            "distancePixels": float(candidate.get("distancePixels", 0)),
            "method": str(candidate.get("method", "ai-local-x-center")),
        }
    except Exception as exc:
        return decision, {
            "ok": False,
            "applied": False,
            "reason": f"local X refinement failed: {type(exc).__name__}: {exc}",
        }

    try:
        import cv2
        import numpy as np
        import XDetector

        rgb = np.asarray(image.convert("RGB"))
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        candidates = [
            XDetector.run_detector(bgr, live=True),
            XDetector.detect_yellow_ad_control(bgr),
            XDetector.detect_top_edge_google_play_badge(bgr),
        ]
        candidate = select_pixel_control_candidate(decision, candidates)
        if candidate is None:
            return decision, None

        ai_x = float(decision["control"]["x"])
        ai_y = float(decision["control"]["y"])
        pixel_x = float(candidate["x"])
        pixel_y = float(candidate["y"])
        decision["control"]["x"] = pixel_x
        decision["control"]["y"] = pixel_y
        refinement = {
            "kind": str(candidate["kind"]),
            "aiX": ai_x,
            "aiY": ai_y,
            "pixelX": pixel_x,
            "pixelY": pixel_y,
            "method": str(candidate.get("method", "pixel-center")),
        }
        return decision, refinement
    except Exception:
        # AI coordinate remains untouched when exact pixel matching is unavailable.
        return decision, None


def save_debug(image: Image.Image, result: dict[str, Any], config: dict[str, Any], reason: str) -> None:
    debug_dir = ROOT / str(config["debugDirectory"])
    debug_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    image.save(debug_dir / f"{stamp}-{reason}.jpg", quality=92)
    with (debug_dir / f"{stamp}-{reason}.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)


class VisionServer:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.state_by_expected: dict[str, dict[str, Any]] = {}

    def analyze(self, image: Image.Image, expected_state: str) -> dict[str, Any]:
        started = time.monotonic()
        raw = request_vision_model(image, expected_state, self.config)
        decision, errors = validate_decision(
            raw, self.config, expected_state, image.size
        )
        agreement_tolerance = (
            float(self.config.get("campusCoordinateTolerance", 0.06))
            if expected_state.startswith("campus_incomplete_building")
            else float(self.config["coordinateTolerance"])
        )
        state = self.state_by_expected.get(expected_state, {"previous": None, "stable_count": 0})
        if errors:
            state = {"previous": None, "stable_count": 0}
        elif same_decision(
            state["previous"],
            decision,
            agreement_tolerance,
            expected_state,
        ):
            state["stable_count"] += 1
        else:
            state = {"previous": decision, "stable_count": 1}
        self.state_by_expected[expected_state] = state

        # A Campus click is immediately followed by deterministic verification
        # that the facility detail opened, and a failed click gets a fresh AI
        # retry with its old coordinates forbidden. Requiring two identical
        # choices here caused valid tied facilities (for example three at 90%)
        # to alternate forever. A single validated click is therefore enough.
        # The irreversible-looking "nothing remains" decision still needs two
        # independent confirmations so the Campus flow cannot finish early.
        if expected_state.startswith("campus_incomplete_building"):
            required = (
                1
                if decision.get("recommendedAction") == "click_campus_building"
                else max(2, int(self.config["requiredAgreementCount"]))
            )
        else:
            required = int(self.config["requiredAgreementCount"])
        accepted = not errors and state["stable_count"] >= required
        result = {
            "ok": True,
            "accepted": accepted,
            "stableCount": state["stable_count"],
            "requiredStableCount": required,
            "latencyMs": round((time.monotonic() - started) * 1000),
            "decision": decision,
            "errors": errors,
        }
        if errors or (config_bool(self.config, "saveUnknownScreenshots") and decision.get("screenType") == "unknown"):
            save_debug(image, result, self.config, "rejected" if errors else "unknown")
        return result


def config_bool(config: dict[str, Any], key: str) -> bool:
    return bool(config.get(key, False))


def preload_ollama(config: dict[str, Any]) -> None:
    """Load model weights in the background before the first ad candidate."""
    try:
        endpoint = str(config["endpoint"])
        generate_endpoint = endpoint.rsplit("/", 1)[0] + "/generate"
        payload = {
            "model": config["model"],
            "prompt": "",
            "stream": False,
            "keep_alive": str(config.get("keepAlive", "30m")),
        }
        request = urllib.request.Request(
            generate_endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=float(config["timeoutSeconds"])):
            pass
    except Exception:
        # The first real analysis reports a detailed error if Ollama is down.
        pass


def serve(config: dict[str, Any]) -> int:
    server = VisionServer(config)
    if str(config.get("provider", "ollama")).strip().lower() == "ollama":
        threading.Thread(target=preload_ollama, args=(config,), daemon=True).start()
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if request.get("quit"):
                return 0
            if request.get("health"):
                provider = str(config.get("provider", "ollama")).strip().lower()
                result = {
                    "ok": True,
                    "enabled": config_bool(config, "enabled"),
                    "provider": provider,
                    "model": config["model"],
                    "credentialsAvailable": (
                        True
                        if provider == "ollama"
                        else bool(
                            get_secret_environment_variable(
                                str(config.get("apiKeyEnvironmentVariable", "GEMINI_API_KEY"))
                            )
                        )
                    ),
                }
            elif not config_bool(config, "enabled"):
                result = {"ok": False, "error": "vision agent is disabled"}
            else:
                expected_state = str(request.get("expectedState", "ad"))
                image = capture_rect(request["rect"])
                result = server.analyze(image, expected_state)
                if (
                    "ai_only" in expected_state
                    and result.get("accepted")
                    and (result.get("decision") or {}).get("recommendedAction")
                    == "click_close"
                ):
                    # The model decides that this is the close control. Capture
                    # once more after the API response and use pixels only to
                    # center that same nearby X. A failed local verification
                    # requests a new AI cycle; it never falls back to an offset.
                    fresh_image = capture_rect(request["rect"])
                    refined, refinement = refine_ai_close_on_fresh_frame(
                        fresh_image, result["decision"]
                    )
                    result["closeRefinement"] = refinement
                    if refinement.get("ok") and refinement.get("applied"):
                        result["decision"] = refined
                    else:
                        # The local detector recognizes only some X glyph styles.
                        # It may improve centering, but it must not veto two fresh
                        # AI-grounded close decisions. Keep the exact AI coordinate
                        # unchanged when the optional pixel refinement cannot match.
                        result["closeRefinement"]["fallbackToAiCoordinate"] = True
                if (
                    expected_state.startswith("campus_incomplete_building")
                    and result.get("accepted")
                    and (result.get("decision") or {}).get("recommendedAction")
                    == "click_campus_building"
                ):
                    # Capture again only after the provider has answered.  This
                    # removes API latency from the click coordinate even while
                    # the Campus camera keeps moving.
                    # The server's stability cache owns the original decision;
                    # mutate only a response copy with live-frame coordinates.
                    result["decision"] = copy.deepcopy(result["decision"])
                    grounding_started = time.monotonic()
                    fresh_image = capture_rect(request["rect"])
                    grounding = ground_campus_click_on_fresh_frame(
                        fresh_image, result["decision"]
                    )
                    grounding["latencyMs"] = round(
                        (time.monotonic() - grounding_started) * 1000
                    )
                    grounding["sourceCaptureAgeMs"] = int(result.get("latencyMs", 0))
                    result["coordinateGrounding"] = grounding
                    if grounding.get("ok"):
                        result["decision"]["control"]["x"] = float(grounding["x"])
                        result["decision"]["control"]["y"] = float(grounding["y"])
                    else:
                        result["accepted"] = False
                        result.setdefault("errors", []).append(
                            f"Campus coordinate was not grounded: {grounding.get('error', 'unknown error')}"
                        )
                        save_debug(fresh_image, result, config, "campus-grounding-rejected")
        except Exception as exc:
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(result, separators=(",", ":"), ensure_ascii=True), flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Guarded vision agent for Top Eleven")
    parser.add_argument("--config", default=str(ROOT / "ai_config.json"))
    parser.add_argument("--server", action="store_true")
    parser.add_argument("--image")
    parser.add_argument("--expected-state", default="ad")
    args = parser.parse_args()
    config = load_config(Path(args.config))
    if args.server:
        return serve(config)
    if args.image:
        image = Image.open(args.image).convert("RGB")
        print(json.dumps(VisionServer(config).analyze(image, args.expected_state), indent=2))
        return 0
    parser.error("--server or --image is required")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
