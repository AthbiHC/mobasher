#!/usr/bin/env python3
from __future__ import annotations

"""
Gallery builder (scaffold)
- export: produce SPARQL URL and save CSV of candidate Arabic public figures (no downloads)
- plan: generate a download plan JSON (no downloads)

NOTE: This scaffold DOES NOT download images without explicit approval.
"""

import argparse
import json
from urllib.parse import quote

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


def cmd_plan(args: argparse.Namespace) -> int:
    plan = {
        "note": "Placeholder. After approval, parse CSV and create download items.",
        "csv_hint": "data/gallery/candidates.csv",
        "items": [
            {"qid": "Q42", "identity": "مثال", "image_url": "https://.../commons.jpg"}
        ],
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="gallery_builder", description="Arabic public-figures gallery scaffolding")
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("export", help="Print SPARQL URL to export CSV from WDQS")
    pe.add_argument("--limit", type=int, default=500)
    pe.add_argument("--occ", nargs="*", default=DEFAULT_OCCS)
    pe.set_defaults(func=cmd_export)

    pp = sub.add_parser("plan", help="Emit example download plan JSON (no downloads)")
    pp.set_defaults(func=cmd_plan)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
