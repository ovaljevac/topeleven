"""Read only run-owned error artifacts; never upload a path supplied in a log."""
import json
import re
from pathlib import Path


def read_failure_events(log_path: Path, seen: set[str]):
    directory = Path(str(log_path) + '.errors')
    if (not directory.is_dir() or directory.is_symlink()
            or directory.resolve().parent != log_path.parent.resolve()):
        return []
    events = []
    for metadata in sorted(directory.glob('*.json')):
        if not re.fullmatch(r'[0-9a-f]{32}', metadata.stem) or metadata.stem in seen:
            continue
        try:
            if metadata.is_symlink() or metadata.stat().st_size > 32768:
                continue
            data = json.loads(metadata.read_text(encoding='utf-8-sig'))
            if data.get('Version') != 1:
                continue
            image = metadata.with_suffix('.png')
            safe_image = (data.get('Captured') is True and image.is_file() and not image.is_symlink()
                          and image.resolve().parent == directory.resolve()
                          and image.stat().st_size <= 8 * 1024 * 1024)
            if safe_image:
                with image.open('rb') as stream:
                    safe_image = stream.read(8) == b'\x89PNG\r\n\x1a\n'
            # Metadata cannot point at another local file.
            events.append((metadata.stem, data, image if safe_image else None))
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return events[:8]


def failure_caption(data):
    return ('⚠️ Faza: ' + str(data.get('Stage', '?'))[:100]
            + '\nPosljednja potvrda: ' + str(data.get('Step', '?'))[:160]
            + '\nČekao sam: ' + str(data.get('Expected', '?'))[:300]
            + '\nGreška: ' + str(data.get('Message', '?'))[:700]
            + ('' if data.get('Captured') else '\nScreenshot nije dostupan: ' + str(data.get('CaptureError', '?'))[:200]))
