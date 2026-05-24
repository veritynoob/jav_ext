import os
import requests


def download_cover(code, url, covers_dir="covers"):
    if not url:
        return None
    os.makedirs(covers_dir, exist_ok=True)
    ext = ".jpg"
    if url.lower().endswith((".png", ".gif", ".webp")):
        ext = os.path.splitext(url)[1]
    filepath = os.path.join(covers_dir, f"{code}{ext}")
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(resp.content)
        return filepath
    except Exception:
        return None
