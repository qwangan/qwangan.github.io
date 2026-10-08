#!/usr/bin/env python3
"""Discover arXiv/SSRN papers and refresh the website's publication metadata."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import textwrap
import time
import unicodedata
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
SOURCES_FILE = ROOT / "publication-sources.yml"
USER_AGENT = "qwangan.github.io publication updater (mailto:qwang30@gsu.edu)"

DOI_RE = re.compile(r"(?:doi\.org/|doi:)?(10\.\d{4,9}/[^\s<>\"']+)", re.I)
ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([^\s<>\"']+)|arxiv:([^\s<>\"']+)", re.I)
SSRN_RE = re.compile(r"ssrn\.(\d+)|(?:abstract_id|abstractid|abstract)=(\d+)", re.I)
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "os": "http://a9.com/-/spec/opensearch/1.1/",
}
LAST_ARXIV_REQUEST = 0.0
LOOKUP_ERRORS = (urllib.error.URLError, TimeoutError, ET.ParseError, ValueError)


def fetch_url(url: str, accept: str = "application/json") -> bytes:
    global LAST_ARXIV_REQUEST
    request = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": USER_AGENT,
        },
    )
    for attempt in range(3):
        if urllib.parse.urlparse(url).hostname == "export.arxiv.org":
            time.sleep(max(0, 3 - (time.monotonic() - LAST_ARXIV_REQUEST)))
            LAST_ARXIV_REQUEST = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(3 * (attempt + 1))
    raise RuntimeError("Unreachable retry state")


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"\s+", " ", value).strip()
    return value.rstrip(".")


def initials(given: str) -> str:
    parts = re.findall(r"[^\W\d_]+", given or "", flags=re.UNICODE)
    parts = [part for part in parts if len(part) > 1 or part.isupper()]
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

    label = f"{html.escape(family)}, {initials(given)}".strip().rstrip(",")
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
    pages = format_pages(clean_text(message.get("page") or ""))

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
    title = html.escape(clean_text((message.get("title") or [""])[0]))
    authors = join_authors(message.get("author") or [])
    venue = format_crossref_venue(message)
    return {"title": title, "authors": authors, "venue": venue}


def canonical_arxiv_id(value: str) -> str:
    return re.sub(r"v\d+$", "", value.removesuffix(".pdf"))


def parse_arxiv_entry(entry: ET.Element) -> Dict[str, Any]:
    identifier_url = entry.findtext("atom:id", default="", namespaces=NS)
    match = ARXIV_RE.search(identifier_url)
    if match is None:
        raise ValueError(f"Invalid arXiv entry: {identifier_url}")
    title = html.escape(clean_text(entry.findtext("atom:title", default="", namespaces=NS)))
    published = entry.findtext("atom:published", default="", namespaces=NS)
    year = published[:4] if published else ""
    authors = []
    for author in entry.findall("atom:author", NS):
        name = clean_text(author.findtext("atom:name", default="", namespaces=NS))
        if name:
            pieces = name.split()
            authors.append({"given": " ".join(pieces[:-1]), "family": pieces[-1]})

    return {
        "title": title,
        "authors": join_authors(authors),
        "venue": f"Preprint, {year}" if year else "Preprint",
        "author_data": authors,
        "source": "arXiv",
        "identifier": canonical_arxiv_id(match.group(1) or match.group(2)),
        "published": published,
    }


def parse_arxiv_feed(xml: bytes) -> Tuple[List[Dict[str, Any]], int]:
    root = ET.fromstring(xml)
    entries = [parse_arxiv_entry(entry) for entry in root.findall("atom:entry", NS)]
    total = int(root.findtext("os:totalResults", default=str(len(entries)), namespaces=NS))
    return entries, total


def fetch_arxiv(arxiv_id: str) -> Dict[str, Any]:
    url = "https://export.arxiv.org/api/query?id_list=" + urllib.parse.quote(canonical_arxiv_id(arxiv_id))
    entries, _ = parse_arxiv_feed(fetch_url(url, accept="application/atom+xml"))
    if not entries:
        raise ValueError(f"No metadata for arXiv {arxiv_id}")
    return entries[0]


def normalized_name(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", value).casefold() if ch.isalnum())


def is_owner(authors: Iterable[Dict[str, str]], config: Dict[str, Any]) -> bool:
    target = normalized_name(config["author"])
    orcid = config.get("orcid", "")
    for author in authors:
        if orcid and author.get("ORCID", "").rstrip("/").rsplit("/", 1)[-1] == orcid:
            return True
        name = " ".join((author.get("given", ""), author.get("family", ""))).strip()
        if normalized_name(name) == target:
            return True
    return False


def discover_arxiv(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    start = 0
    while True:
        params = urllib.parse.urlencode({
            "search_query": f'au:"{config["author"]}"',
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "start": start,
            "max_results": 100,
        })
        entries, total = parse_arxiv_feed(fetch_url("https://export.arxiv.org/api/query?" + params, "application/atom+xml"))
        records.extend(entry for entry in entries if is_owner(entry["author_data"], config))
        start += len(entries)
        if start >= total:
            return records
        if not entries:
            raise ValueError("arXiv returned an incomplete author feed")


def ssrn_record(message: Dict[str, Any]) -> Dict[str, Any]:
    doi = message.get("DOI", "")
    match = re.fullmatch(r"10\.2139/ssrn\.(\d+)", doi, re.I)
    if not match:
        raise ValueError(f"Not an SSRN DOI: {doi}")
    year = get_nested_year(message)
    published = (message.get("posted") or message.get("issued") or {}).get("date-parts") or []
    date = "-".join(f"{part:02d}" for part in published[0]) if published else message.get("created", {}).get("date-time", "")
    return {
        "title": html.escape(clean_text((message.get("title") or [""])[0])),
        "authors": join_authors(message.get("author") or []),
        "author_data": message.get("author") or [],
        "venue": f"Preprint, {year}" if year else "Preprint",
        "source": "SSRN",
        "identifier": match.group(1),
        "published": date,
    }


def discover_ssrn(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    # SSRN blocks automated HTML requests. Use its publisher-deposited Crossref
    # records: ORCID gives a complete exact-ID query; a name query catches older
    # deposits without ORCID. Never accept an initials-only author match.
    queries = [{"filter": "prefix:10.2139", "query.author": config["author"], "rows": 100}]
    if config.get("orcid"):
        queries.insert(0, {
            "filter": f'prefix:10.2139,orcid:{config["orcid"]}',
            "rows": 100,
            "cursor": "*",
        })
    records: Dict[str, Dict[str, Any]] = {}
    for query in queries:
        seen_cursors = set()
        while True:
            url = "https://api.crossref.org/works?" + urllib.parse.urlencode(query)
            message = json.loads(fetch_url(url).decode("utf-8"))["message"]
            items = message.get("items", [])
            for item in items:
                if re.fullmatch(r"10\.2139/ssrn\.\d+", item.get("DOI", ""), re.I) and is_owner(item.get("author") or [], config):
                    record = ssrn_record(item)
                    records[record["identifier"]] = record
            if "cursor" not in query or len(items) < query["rows"]:
                break
            cursor = message.get("next-cursor")
            if not cursor or cursor in seen_cursors:
                raise ValueError("Crossref returned an incomplete SSRN author feed")
            seen_cursors.add(cursor)
            query["cursor"] = cursor
            time.sleep(1)
    return list(records.values())


def fetch_ssrn(identifier: str) -> Dict[str, Any]:
    url = "https://api.crossref.org/works/10.2139/ssrn." + identifier
    return ssrn_record(json.loads(fetch_url(url).decode("utf-8"))["message"])


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
        if match and not match.group(1).lower().startswith("10.2139/ssrn."):
            return match.group(1).rstrip(".")
    return None


def extract_arxiv(item: Dict[str, Any]) -> Optional[str]:
    candidates = [item.get("arxiv"), link_url(item, "arXiv")]
    for link in item.get("links") or []:
        candidates.append(link.get("url"))
    for candidate in candidates:
        if not candidate:
            continue
        if candidate == item.get("arxiv") and re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z.-]+/\d{7})(?:v\d+)?", str(candidate), re.I):
            return canonical_arxiv_id(str(candidate))
        match = ARXIV_RE.search(str(candidate))
        if match:
            return canonical_arxiv_id((match.group(1) or match.group(2)).rstrip("."))
    return None


def extract_ssrn(item: Dict[str, Any]) -> Optional[str]:
    candidates = [item.get("ssrn"), item.get("doi")]
    candidates.extend(link.get("url") for link in item.get("links") or [])
    for candidate in candidates:
        if not candidate:
            continue
        value = str(candidate)
        if value.isdigit() and candidate == item.get("ssrn"):
            return value
        if "ssrn" in value.lower():
            match = SSRN_RE.search(value)
            if match:
                return match.group(1) or match.group(2)
    return None


def title_key(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", clean_text(value)).replace("Λ", "Lambda").replace("λ", "lambda")
    return normalized_name(text)


def merge_discoveries(data: List[Dict[str, Any]], records: List[Dict[str, Any]], config: Dict[str, Any]) -> Tuple[int, List[str]]:
    group = next((group for group in data if group.get("heading") == "Pre-publication Manuscripts"), None)
    if group is None:
        raise ValueError("Missing Pre-publication Manuscripts group")
    existing = [item for section in data for item in section.get("items") or []]
    next_number = max((int(item["number"][1:]) for item in existing if re.fullmatch(r"P\d+", str(item.get("number", "")))), default=0)
    changed_items = set()
    notes = []
    for record in records:
        if not record["title"] or not record["authors"]:
            raise ValueError(f'Incomplete {record["source"]} record {record["identifier"]}')
    # Ascending insertion assigns stable numbers; newest additions end up first.
    for record in sorted(records, key=lambda record: (record["published"], record["source"], record["identifier"])):
        source, identifier = record["source"], record["identifier"]
        mapping = (config.get("related_records") or {}).get(f"{source}:{identifier}")
        target = None
        for item in existing:
            same_id = extract_arxiv(item) == identifier if source == "arXiv" else extract_ssrn(item) == identifier
            if (mapping and item.get("number") == mapping["publication"]) or (not mapping and (same_id or title_key(item.get("title", "")) == title_key(record["title"]))):
                target = item
                break
        if mapping and target is None:
            raise ValueError(f"Related-record target does not exist: {mapping}")
        if target is None:
            next_number += 1
            target = {
                "number": f"P{next_number}",
                "authors": record["authors"],
                "title": record["title"],
                "venue": record["venue"],
                "links": [],
            }
            group.setdefault("items", []).insert(0, target)
            existing.append(target)
            changed_items.add(target["number"])
            notes.append(f'Added {target["number"]}: {record["title"]}')
        url = f"https://arxiv.org/abs/{identifier}" if source == "arXiv" else f"https://ssrn.com/abstract={identifier}"
        links = target.setdefault("links", [])
        if not any(link.get("url") == url or (extract_arxiv({"links": [link]}) == identifier if source == "arXiv" else extract_ssrn({"links": [link]}) == identifier) for link in links):
            links.append({
                "label": mapping.get("label", source) if mapping else source,
                "url": url,
                "class": "tag-arxiv" if source == "arXiv" else "tag-ssrn",
            })
            changed_items.add(target["number"])
            notes.append(f'Linked {source} {identifier} to {target["number"]}')
    return len(changed_items), notes


def format_pages(value: str) -> str:
    return re.sub(r"(?<=\d)-(?=\d)", "–", value)


def is_provisional_venue(value: Any) -> bool:
    text = clean_text(str(value or "")).lower()
    return "available online" in text or "forthcoming" in text


def is_final_venue(value: str) -> bool:
    text = clean_text(value)
    return bool(text) and not is_provisional_venue(text) and bool(re.search(r"<strong>[^<]+</strong>", text))


def should_update(current: Any, new_value: str, mode: str, field: str) -> bool:
    if not new_value:
        return False
    current_text = clean_text(str(current or ""))
    new_text = clean_text(new_value)
    if field in ("title", "authors") and current_text.casefold() == new_text.casefold():
        return False
    if mode == "refresh":
        return current_text != new_text
    if field == "venue" and is_provisional_venue(current) and is_final_venue(new_value):
        return True
    return not current_text


def update_item(item: Dict[str, Any], mode: str, cache: Optional[Dict[str, Dict[str, Any]]] = None) -> Tuple[bool, List[str]]:
    doi = extract_doi(item)
    arxiv_id = extract_arxiv(item)
    ssrn_id = extract_ssrn(item)
    metadata: Dict[str, str] = {}
    source = ""

    if doi:
        metadata = fetch_crossref(doi)
        source = f"DOI {doi}"
    elif arxiv_id:
        metadata = (cache or {}).get(f"arXiv:{arxiv_id}") or fetch_arxiv(arxiv_id)
        source = f"arXiv {arxiv_id}"
    elif ssrn_id:
        metadata = (cache or {}).get(f"SSRN:{ssrn_id}") or fetch_ssrn(ssrn_id)
        source = f"SSRN {ssrn_id}"
    else:
        return False, ["no DOI/arXiv/SSRN identifier; add a source link to enable metadata refresh"]

    changed = False
    notes: List[str] = []
    for field in ("title", "authors", "venue"):
        new_value = metadata.get(field, "")
        if should_update(item.get(field), new_value, mode, field):
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
        def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
            return super().increase_indent(flow, False)

    def represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.nodes.ScalarNode:
        if "\n" in value:
            return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", value)

    Dumper.add_representer(str, represent_str)
    rendered = yaml.dump(data, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=1000)
    PUBLICATIONS_FILE.write_text(rendered, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover arXiv/SSRN papers and refresh publication metadata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Examples:
              python3 scripts/update_publications.py
              python3 scripts/update_publications.py --write
              python3 scripts/update_publications.py --write --discover
              python3 scripts/update_publications.py --write --mode refresh
            """
        ),
    )
    parser.add_argument("--write", action="store_true", help="write changes to _pages/publications.yml")
    parser.add_argument("--discover", action="store_true", help="discover arXiv and SSRN papers using publication-sources.yml")
    parser.add_argument(
        "--mode",
        choices=("missing", "refresh"),
        default="missing",
        help="missing fills blank fields and finalizes provisional venues; refresh updates title/authors/venue from metadata",
    )
    parser.add_argument("--sleep", type=float, default=1.0, help="seconds to pause between API requests")
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="return a non-zero exit code when any metadata lookup fails",
    )
    args = parser.parse_args()

    data = load_publications()
    original_items = {item.get("number"): json.dumps(item, sort_keys=True) for group in data for item in group.get("items") or []}
    failures: List[str] = []
    cache: Dict[str, Dict[str, Any]] = {}
    if args.discover:
        with SOURCES_FILE.open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle)
        for name, discover in (("arXiv", discover_arxiv), ("SSRN", discover_ssrn)):
            try:
                records = discover(config)
                _, notes = merge_discoveries(data, records, config)
                cache.update({f'{record["source"]}:{record["identifier"]}': record for record in records})
                print(f"[discovery] {name}: {len(records)} author-verified records")
                for note in notes:
                    print(f"  - {note}")
            except LOOKUP_ERRORS as exc:
                failures.append(f"{name} discovery: {exc}")

    for group in data:
        heading = group.get("heading", "Untitled")
        for item in group.get("items") or []:
            label = item.get("number", "?")
            title = item.get("title", "Untitled")
            try:
                changed, notes = update_item(item, args.mode, cache)
            except LOOKUP_ERRORS as exc:
                failures.append(f"[{label}] {title}: {exc}")
                continue

            prefix = "changed" if changed else "checked"
            print(f"[{prefix}] {heading} / {label}: {title}")
            for note in notes:
                print(f"  - {note}")
            time.sleep(args.sleep)

    total_changed = sum(original_items.get(item.get("number")) != json.dumps(item, sort_keys=True) for group in data for item in group.get("items") or [])
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
        print("Successful source updates have been saved." if args.write else "Dry run only; no changes saved.", file=sys.stderr)
        return 1 if args.fail_on_error else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
