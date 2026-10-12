"""Download a real-world TEST set of freely-licensed photos from Wikimedia Commons.

This is how the Egyptian street-dog evaluation in docs/EVALUATION.md was built:

    python tools/fetch_commons.py datasets/egypt_eval/raw_dogs 250 2 "Category:Dogs of Egypt" "Category:Feral dogs in Egypt"
    python tools/fetch_commons.py datasets/egypt_eval/raw_cats 120 1 "Category:Feral cats in Egypt" "Category:Cats of Egypt"
    python tools/fetch_commons.py datasets/egypt_eval/raw_kids 120 0 "Category:Children of Egypt"

usage: fetch_commons.py OUT_DIR MAX_FILES DEPTH CATEGORY [CATEGORY ...]

* Sub-categories are followed up to DEPTH levels, but only if their name contains an Egyptian
  place name, and never into paintings / statues / ancient art.
* Images are saved as 960 px thumbnails (a standard Wikimedia size) together with
  ATTRIBUTION.csv (author, licence, source page). Respect each licence; do not commit the images.
* ALWAYS look through the images before using them: categories contain drawings, look-alikes
  and photos where the subject is tiny. tools/evaluate.py needs clean "dogs" / "no dogs" folders.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = "DogRepellerEval/1.0 (student graduation project; test set for a dog detector)"
SKIP = re.compile(r"ancient|painting|statue|hieroglyph|mumm|amulet|museum|relief|drawing|video", re.I)
EGYPT = re.compile(r"Egypt|Luxor|Aswan|Cairo|Alexandria|Giza|Sinai|Hurghada|Sharm|Dahab|Siwa|Nile|"
                   r"Port Said|Fayoum|Minya")


def api(**params) -> dict:
    time.sleep(0.5)  # be polite: Wikimedia rate-limits aggressive clients
    params.update(format="json", formatversion="2")
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except OSError:
            time.sleep(5 + 10 * attempt)
    raise RuntimeError(f"Wikimedia API failed: {url}")


def members(category: str, kind: str) -> list[str]:
    out, cont = [], {}
    while True:
        d = api(action="query", list="categorymembers", cmtitle=category, cmtype=kind,
                cmlimit=500, **cont)
        out += [m["title"] for m in d["query"]["categorymembers"]]
        if "continue" not in d:
            return out
        cont = {"cmcontinue": d["continue"]["cmcontinue"]}


def walk(category: str, depth: int, seen: set[str]) -> list[str]:
    if category in seen:
        return []
    seen.add(category)
    files = members(category, "file")
    if depth > 0:
        for sub in members(category, "subcat"):
            if not SKIP.search(sub) and EGYPT.search(sub):
                files += walk(sub, depth - 1, seen)
    return files


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print(__doc__)
        return 2
    out, max_files, depth, categories = Path(argv[0]), int(argv[1]), int(argv[2]), argv[3:]
    out.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    titles: list[str] = []
    for c in categories:
        titles += walk(c, depth, seen)
    titles = [t for t in dict.fromkeys(titles) if re.search(r"\.(jpe?g|png)$", t, re.I)][:max_files]
    print(f"{len(titles)} files to fetch")
    rows = []
    for i in range(0, len(titles), 40):
        d = api(action="query", prop="imageinfo", titles="|".join(titles[i:i + 40]),
                iiprop="url|extmetadata", iiurlwidth=960)
        for page in d["query"]["pages"]:
            info = (page.get("imageinfo") or [{}])[0]
            url = info.get("thumburl") or info.get("url")
            if not url:
                continue
            ext = ".png" if url.lower().endswith(".png") else ".jpg"
            name = f"{len(rows):04d}{ext}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=60) as r:
                    (out / name).write_bytes(r.read())
            except OSError as e:
                print("skip", page["title"], e)
                continue
            meta = info.get("extmetadata", {})
            rows.append({"file": name, "title": page["title"],
                         "author": re.sub("<[^>]+>", "", meta.get("Artist", {}).get("value", ""))[:120],
                         "license": meta.get("LicenseShortName", {}).get("value", ""),
                         "source": info.get("descriptionurl", "")})
            time.sleep(1.0)
    with open(out / "ATTRIBUTION.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "title", "author", "license", "source"])
        w.writeheader()
        w.writerows(rows)
    print(f"saved {len(rows)} images to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
