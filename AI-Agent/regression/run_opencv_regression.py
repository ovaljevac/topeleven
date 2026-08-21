import argparse
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pydeps"))
sys.path.insert(0, str(ROOT.parent / "pydeps"))

import cv2
import numpy as np

import XDetector


def load_from_zip(archive, name):
    encoded = np.frombuffer(archive.read(name), dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Cannot decode {name}")
    return image


def main():
    parser = argparse.ArgumentParser(description="Replay XDetector against ss.zip screenshots")
    parser.add_argument("--manifest", default=str(Path(__file__).with_name("manifest.json")))
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    zip_path = (manifest_path.parent / manifest["zip"]).resolve()
    failures = []

    with zipfile.ZipFile(zip_path) as archive:
        for case in manifest["cases"]:
            image = load_from_zip(archive, case["image"])
            left, top, right, bottom = case["crop"]
            crop = image[top:bottom, left:right]
            mode = None if case["mode"] == "x" else case["mode"]
            result = XDetector.run_detector(crop, mode)
            found = bool(result.get("found", False))
            passed = found == bool(case["expectedFound"])
            if passed and found and "expectedKind" in case:
                passed = result.get("kind") == case["expectedKind"]
            marker = "PASS" if passed else "FAIL"
            print(f"{marker}: {case['name']} -> {json.dumps(result, ensure_ascii=False)}")
            if not passed:
                failures.append(case["name"])

    print(f"\n{len(manifest['cases']) - len(failures)}/{len(manifest['cases'])} cases passed")
    if failures:
        print("Failures: " + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
