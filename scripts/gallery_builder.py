#!/usr/bin/env python3
from __future__ import annotations

"""
Gallery builder
- export: produce SPARQL URL and save CSV of candidate Arabic public figures
- plan: read a CSV exported from WDQS and write a JSONL plan (no downloads)
- download: fetch images listed in plan.jsonl with rate-limit and resume

CSV expected columns: person, personLabel, arTitle, image (as returned by WDQS)
"""

import argparse
import csv
import json
from urllib.parse import quote, urlparse, urlunparse, urlencode
import os
import time
import hashlib
from pathlib import Path
from typing import Iterable

SPARQL_TEMPLATE = """
# Humans with citizenship in Arab League countries, notable occupations, and Arabic Wikipedia pages
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd:  <http://www.wikidata.org/entity/>
PREFIX schema: <http://schema.org/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX bd: <http://www.bigdata.com/rdf#>

SELECT ?person ?personLabel ?arTitle ?image WHERE {
  ?person wdt:P31 wd:Q5.
  ?person wdt:P27 ?country.
  ?country wdt:P463 wd:Q7172.
  ?person wdt:P106 ?occ.
  VALUES ?occ { %OCCS% }
  OPTIONAL { ?person wdt:P18 ?image. }
  ?arSitelink schema:about ?person ;
              schema:isPartOf <https://ar.wikipedia.org/> ;
              schema:name ?arTitle .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "ar,en". }
}
LIMIT %LIMIT%
""".strip()

DEFAULT_OCCS = [
    "wd:Q82955",   # politician
    "wd:Q486748",  # journalist
    "wd:Q6625963", # television presenter
    "wd:Q33999",   # actor
    "wd:Q177220",  # singer
    "wd:Q937857",  # football player
]


def build_sparql_url(limit: int, occs: list[str]) -> str:
    q = SPARQL_TEMPLATE.replace("%OCCS%", " ".join(occs)).replace("%LIMIT%", str(limit))
    return "https://query.wikidata.org/#" + quote(q)


def cmd_export(args: argparse.Namespace) -> int:
    url = build_sparql_url(args.limit, args.occ)
    print(url)
    print("Save CSV from WDQS UI to data/gallery/candidates.csv")
    return 0


def _to_qid(person_field: str) -> str:
    # person is usually a WD URI like https://www.wikidata.org/entity/Q12345
    if not person_field:
        return ""
    return person_field.rstrip("/").split("/")[-1]


def _slug(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("/", "-")
        .replace("\\", "-")
        .replace(" ", "_")
        .strip()
    )


def cmd_plan(args: argparse.Namespace) -> int:
    input_csv = args.csv
    out_path = args.out
    total = 0
    with_image = 0
    items_written = 0
    # Write JSONL
    with open(out_path, "w", encoding="utf-8") as fout:
        with open(input_csv, "r", encoding="utf-8") as fin:
            reader = csv.DictReader(fin)
            for row in reader:
                total += 1
                qid = _to_qid(row.get("person", ""))
                title_ar = row.get("arTitle", "")
                label = row.get("personLabel", "")
                image_url = row.get("image", "")
                identity = title_ar or label or qid
                if image_url:
                    with_image += 1
                rec = {
                    "qid": qid,
                    "identity": identity,
                    "label": label,
                    "title_ar": title_ar,
                    "image_url": image_url,
                    "slug": _slug(identity),
                }
                fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                items_written += 1
    summary = {
        "csv": input_csv,
        "out": out_path,
        "total_rows": total,
        "with_image": with_image,
        "without_image": total - with_image,
        "written": items_written,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _hash_url(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def _iter_plan(path: str) -> Iterable[dict]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _safe_mkdir(p: str) -> None:
    Path(p).mkdir(parents=True, exist_ok=True)


def cmd_download(args: argparse.Namespace) -> int:
    plan = args.plan
    root = args.out
    rate = args.rate
    timeout = args.timeout
    _safe_mkdir(root)
    import requests  # lazy import

    def normalize_commons(url: str) -> str:
        # Force https and add download flag for Special:FilePath links
        try:
            parts = urlparse(url)
            scheme = 'https'
            netloc = parts.netloc
            path = parts.path
            query = parts.query
            if 'Special:FilePath' in path and 'download' not in query:
                if query:
                    query = query + '&download=1'
                else:
                    query = 'download=1'
            return urlunparse((scheme, netloc, path, '', query, ''))
        except Exception:
            return url

    downloaded = 0
    skipped = 0
    errors = 0
    sess = requests.Session()
    sess.headers.update({
        'User-Agent': 'Mobasher/1.0 (+https://github.com/AthbiHC/mobasher)'
    })
    for rec in _iter_plan(plan):
        url = rec.get("image_url")
        if not url:
            continue
        url = normalize_commons(url)
        ident = rec.get("slug") or rec.get("identity") or rec.get("qid")
        dest_dir = os.path.join(root, ident)
        _safe_mkdir(dest_dir)
        name = f"{_hash_url(url)}.jpg"
        dest = os.path.join(dest_dir, name)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            skipped += 1
            continue
        try:
            resp = sess.get(url, stream=True, timeout=timeout, allow_redirects=True)
            if resp.status_code == 200:
                ctype = resp.headers.get('Content-Type', '')
                if 'image' not in ctype:
                    errors += 1
                else:
                    with open(dest, "wb") as fout:
                        for chunk in resp.iter_content(chunk_size=8192):
                            if chunk:
                                fout.write(chunk)
                    downloaded += 1
            else:
                errors += 1
        except Exception:
            errors += 1
        time.sleep(1.0 / max(1, rate))
    print(json.dumps({"downloaded": downloaded, "skipped": skipped, "errors": errors, "out": root}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="gallery_builder", description="Arabic public-figures gallery scaffolding")
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("export", help="Print SPARQL URL to export CSV from WDQS")
    pe.add_argument("--limit", type=int, default=500)
    pe.add_argument("--occ", nargs="*", default=DEFAULT_OCCS)
    pe.set_defaults(func=cmd_export)

    pp = sub.add_parser("plan", help="Parse CSV and write JSONL plan (no downloads)")
    pp.add_argument("--csv", default="data/gallery/candidates.csv", help="Path to CSV exported from WDQS")
    pp.add_argument("--out", default="data/gallery/plan.jsonl", help="Output JSONL plan path")
    pp.set_defaults(func=cmd_plan)

    pd = sub.add_parser("download", help="Download images listed in plan.jsonl with rate-limit and resume")
    pd.add_argument("--plan", default="data/gallery/plan.jsonl")
    pd.add_argument("--out", default=os.environ.get("FACES_GALLERY_DIR", "/Volumes/ExternalDB/Media-View-Data/data/gallery/images"))
    pd.add_argument("--rate", type=int, default=1, help="Requests per second (default 1 rps)")
    pd.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds")
    pd.set_defaults(func=cmd_download)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
