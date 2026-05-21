#!/usr/bin/env python3
"""Refresh publication metadata in _pages/publications.yml.

The script is intentionally conservative. It reads DOI/arXiv identifiers from
existing publication entries, fetches metadata, and can fill missing fields or
refresh existing fields after review.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only on machines without PyYAML
    print(
        "PyYAML is required. Install it with: python3 -m pip install -r requirements-publications.txt",
        file=sys.stderr,
    )
    raise SystemExit(2)

ROOT = Path(__file__).resolve().parents[1]
PUBLICATIONS_FILE = ROOT / "_pages" / "publications.yml"
USER_AGENT = "qwangan.github.io publication updater (mailto:qwang30@gsu.edu)"

DOI_RE = re.compile(r"(?:doi\.org/|doi:)?(10\.\d{4,9}/[^\s<>\"']+)", re.I)
ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([^\s<>\"']+)|arxiv:([^\s<>\"']+)", re.I)


def fetch_url(url: str, accept: str = "application/json") -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"\s+", " ", value).strip()
    return value.rstrip(".")


def initials(given: str) -> str:
    parts = re.findall(r"[A-Za-z]+", given or "")
    if not parts:
        return ""
    return " ".join(f"{part[0]}." for part in parts)


def format_author(author: Dict[str, str]) -> str:
    family = clean_text(author.get("family") or author.get("name") or "")
    given = clean_text(author.get("given") or "")

    if not family and given:
        pieces = given.split()
        family = pieces[-1]
        given = " ".join(pieces[:-1])

    label = f"{family}, {initials(given)}".strip().rstrip(",")
    label = re.sub(r"\s+", " ", label)

    if family.lower() == "wang" and re.search(r"\bQ\.", label):
        return f"<strong>{label}</strong>"
    return label


def join_authors(authors: Iterable[Dict[str, str]]) -> str:
    names = [format_author(author) for author in authors]
    names = [name for name in names if name]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])} and {names[-1]}"


def get_nested_year(message: Dict[str, Any]) -> Optional[int]:
    for key in ("published-print", "published-online", "published", "issued"):
        date_parts = message.get(key, {}).get("date-parts") or []
        if date_parts and date_parts[0]:
            return int(date_parts[0][0])
    return None


def format_crossref_venue(message: Dict[str, Any]) -> str:
    journal = clean_text((message.get("container-title") or [""])[0])
    year = get_nested_year(message)
    volume = clean_text(message.get("volume") or "")
    issue = clean_text(message.get("issue") or "")
    pages = clean_text(message.get("page") or "")

    parts: List[str] = []
    if journal:
        parts.append(f"<em>{journal}</em>")
    if volume:
        vol = f"<strong>{volume}</strong>"
        if issue:
            vol += f"({issue})"
        parts.append(vol)
    if pages:
        parts.append(pages)
    if year:
        parts.append(str(year))

    if parts:
        return ", ".join(parts)
    return ""


def fetch_crossref(doi: str) -> Dict[str, str]:
    encoded = urllib.parse.quote(doi, safe="")
    url = f"https://api.crossref.org/works/{encoded}"
    payload = json.loads(fetch_url(url).decode("utf-8"))
    message = payload.get("message", {})
    title = clean_text((message.get("title") or [""])[0])
    authors = join_authors(message.get("author") or [])
    venue = format_crossref_venue(message)
    return {"title": title, "authors": authors, "venue": venue}


def fetch_arxiv(arxiv_id: str) -> Dict[str, str]:
    arxiv_id = arxiv_id.removesuffix(".pdf")
    url = "https://export.arxiv.org/api/query?id_list=" + urllib.parse.quote(arxiv_id)
    xml = fetch_url(url, accept="application/atom+xml")
    root = ET.fromstring(xml)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", ns)
    if entry is None:
        return {}

    title = clean_text(entry.findtext("atom:title", default="", namespaces=ns))
    published = entry.findtext("atom:published", default="", namespaces=ns)
    year = published[:4] if published else ""
    authors = []
    for author in entry.findall("atom:author", ns):
        name = clean_text(author.findtext("atom:name", default="", namespaces=ns))
        if name:
            pieces = name.split()
            authors.append({"given": " ".join(pieces[:-1]), "family": pieces[-1]})

    return {
        "title": title,
        "authors": join_authors(authors),
        "venue": f"Preprint, {year}" if year else "Preprint",
    }


def link_url(item: Dict[str, Any], label: str) -> Optional[str]:
    for link in item.get("links") or []:
        if str(link.get("label", "")).lower() == label.lower():
            return link.get("url")
    return None


def extract_doi(item: Dict[str, Any]) -> Optional[str]:
    candidates = [item.get("doi"), link_url(item, "Journal")]
    for link in item.get("links") or []:
        candidates.append(link.get("url"))
    for candidate in candidates:
        if not candidate:
            continue
        match = DOI_RE.search(str(candidate))
        if match:
            return match.group(1).rstrip(".")
    return None


def extract_arxiv(item: Dict[str, Any]) -> Optional[str]:
    candidates = [item.get("arxiv"), link_url(item, "arXiv")]
    for link in item.get("links") or []:
        candidates.append(link.get("url"))
    for candidate in candidates:
        if not candidate:
            continue
        match = ARXIV_RE.search(str(candidate))
        if match:
            return (match.group(1) or match.group(2)).rstrip(".")
    return None


def should_update(current: Any, new_value: str, mode: str) -> bool:
    if not new_value:
        return False
    if mode == "refresh":
        return clean_text(str(current or "")) != clean_text(new_value)
    return not clean_text(str(current or ""))


def update_item(item: Dict[str, Any], mode: str) -> Tuple[bool, List[str]]:
    doi = extract_doi(item)
    arxiv_id = extract_arxiv(item)
    metadata: Dict[str, str] = {}
    source = ""

    if doi:
        metadata = fetch_crossref(doi)
        source = f"DOI {doi}"
    elif arxiv_id:
        metadata = fetch_arxiv(arxiv_id)
        source = f"arXiv {arxiv_id}"
    else:
        return False, ["no DOI/arXiv identifier"]

    changed = False
    notes: List[str] = []
    for field in ("title", "authors", "venue"):
        new_value = metadata.get(field, "")
        if should_update(item.get(field), new_value, mode):
            old = item.get(field, "")
            item[field] = new_value
            changed = True
            notes.append(f"{field}: {old!r} -> {new_value!r}")

    if not notes:
        notes.append(f"checked {source}; no changes")
    else:
        notes.insert(0, f"updated from {source}")
    return changed, notes


def load_publications() -> List[Dict[str, Any]]:
    with PUBLICATIONS_FILE.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, list):
        raise ValueError(f"Expected a list in {PUBLICATIONS_FILE}")
    return data


def dump_publications(data: List[Dict[str, Any]]) -> None:
    class Dumper(yaml.SafeDumper):
        pass

    def represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.nodes.ScalarNode:
        if "\n" in value:
            return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", value)

    Dumper.add_representer(str, represent_str)
    rendered = yaml.dump(data, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=1000)
    PUBLICATIONS_FILE.write_text(rendered, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh _pages/publications.yml from DOI and arXiv metadata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Examples:
              python3 scripts/update_publications.py
              python3 scripts/update_publications.py --write
              python3 scripts/update_publications.py --write --mode refresh
            """
        ),
    )
    parser.add_argument("--write", action="store_true", help="write changes to _pages/publications.yml")
    parser.add_argument(
        "--mode",
        choices=("missing", "refresh"),
        default="missing",
        help="missing fills only blank fields; refresh updates title/authors/venue from metadata",
    )
    parser.add_argument("--sleep", type=float, default=1.0, help="seconds to pause between API requests")
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="return a non-zero exit code when any metadata lookup fails",
    )
    args = parser.parse_args()

    data = load_publications()
    total_changed = 0
    failures: List[str] = []

    for group in data:
        heading = group.get("heading", "Untitled")
        for item in group.get("items") or []:
            label = item.get("number", "?")
            title = item.get("title", "Untitled")
            try:
                changed, notes = update_item(item, args.mode)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ET.ParseError, ValueError) as exc:
                failures.append(f"[{label}] {title}: {exc}")
                continue

            if changed:
                total_changed += 1
            prefix = "changed" if changed else "checked"
            print(f"[{prefix}] {heading} / {label}: {title}")
            for note in notes:
                print(f"  - {note}")
            time.sleep(args.sleep)

    if args.write and total_changed:
        dump_publications(data)
        print(f"Wrote {PUBLICATIONS_FILE} with {total_changed} changed entr{'y' if total_changed == 1 else 'ies'}.")
    elif total_changed:
        print(f"Detected {total_changed} potential changed entr{'y' if total_changed == 1 else 'ies'}; rerun with --write to save.")
    else:
        print("No publication changes detected.")

    if failures:
        print("\nMetadata lookups that failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1 if args.fail_on_error else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
