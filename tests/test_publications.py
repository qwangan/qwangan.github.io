"""Offline regression checks for author discovery and publication merging."""

import copy
import importlib.util
import json
import unittest
import urllib.error
import urllib.parse
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("publications", Path(__file__).resolve().parents[1] / "scripts" / "update_publications.py")
pub = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pub)
CONFIG = {"author": "Qiuqi Wang", "orcid": "0000-0002-9671-8425"}


def record(title, identifier, source="arXiv", date="2026-10-07"):
    return {"title": title, "identifier": identifier, "source": source, "published": date, "authors": "<strong>Wang, Q.</strong> and Wang, R.", "venue": "Preprint, 2026"}


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.data = [
            {"heading": "Pre-publication Manuscripts", "items": [{"number": "P3", "title": "Existing manuscript", "authors": "Curated authors", "venue": "Preprint, 2025", "links": [{"label": "arXiv", "url": "https://arxiv.org/abs/2511.05840"}]}]},
            {"heading": "Peer-reviewed Journal Articles", "items": [{"number": "J10", "title": "E-backtesting", "authors": "Curated authors", "venue": "Published journal citation, 2026", "links": [{"label": "Journal", "url": "https://doi.org/10.1287/mnsc.2023.01659"}]}]},
        ]

    def test_full_name_or_exact_orcid_required(self):
        self.assertTrue(pub.is_owner([{"given": "Qiuqi", "family": "Wang"}], CONFIG))
        self.assertTrue(pub.is_owner([{"given": "Q.", "family": "Wang", "ORCID": "https://orcid.org/0000-0002-9671-8425"}], CONFIG))
        self.assertFalse(pub.is_owner([{"given": "Qiang", "family": "Wang"}], CONFIG))
        self.assertFalse(pub.is_owner([{"given": "Q.", "family": "Wang"}], CONFIG))

    def test_versions_and_ssrn_url_forms(self):
        self.assertEqual(pub.extract_arxiv({"links": [{"url": "https://arxiv.org/pdf/2610.09622v2.pdf"}]}), "2610.09622")
        for url in ("https://ssrn.com/abstract=1234", "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1234", "https://doi.org/10.2139/ssrn.1234"):
            self.assertEqual(pub.extract_ssrn({"links": [{"url": url}]}), "1234")
            self.assertIsNone(pub.extract_doi({"links": [{"url": url}]}))

    def test_arxiv_feed_parsing_and_api_errors(self):
        xml = b'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:os="http://a9.com/-/spec/opensearch/1.1/">
        <os:totalResults>1</os:totalResults><entry><id>http://arxiv.org/abs/2610.09622v1</id>
        <title>Risk &amp; testing</title><published>2026-10-07T08:00:06Z</published>
        <author><name>Qiuqi Wang</name></author></entry></feed>'''
        entries, total = pub.parse_arxiv_feed(xml)
        self.assertEqual(total, 1)
        self.assertEqual(entries[0]["identifier"], "2610.09622")
        self.assertEqual(entries[0]["title"], "Risk &amp; testing")
        self.assertEqual(entries[0]["authors"], "<strong>Wang, Q.</strong>")
        with self.assertRaises(ValueError):
            pub.parse_arxiv_feed(b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/api/errors</id></entry></feed>')

    def test_arxiv_pagination_and_false_positive_filter(self):
        good = {"author_data": [{"given": "Qiuqi", "family": "Wang"}]}
        wrong = {"author_data": [{"given": "Qiang", "family": "Wang"}]}
        with patch.object(pub, "fetch_url", return_value=b"feed"), patch.object(pub, "parse_arxiv_feed", side_effect=[([good], 2), ([wrong], 2)]):
            self.assertEqual(pub.discover_arxiv(CONFIG), [good])

    def test_ssrn_discovery_queries_orcid_and_older_name_only_records(self):
        def work(identifier, given="Qiuqi"):
            return {
                "DOI": f"10.2139/ssrn.{identifier}",
                "title": [f"Paper {identifier}"],
                "author": [{"given": given, "family": "Wang"}],
            }

        queries = []

        def response(url):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            queries.append(query)
            if "cursor" in query:
                items = [work("1234"), work("9999", given="Qiang")]
            else:
                items = [work("1234"), work("5678"), work("9998", given="Q.")]
            return json.dumps({"message": {"items": items}}).encode()

        with patch.object(pub, "fetch_url", side_effect=response):
            records = pub.discover_ssrn(CONFIG)
        self.assertEqual({entry["identifier"] for entry in records}, {"1234", "5678"})
        self.assertIn("orcid:0000-0002-9671-8425", queries[0]["filter"][0])
        self.assertEqual(queries[1]["query.author"], ["Qiuqi Wang"])

    def test_ssrn_orcid_query_paginates(self):
        work = {
            "DOI": "10.2139/ssrn.1234",
            "title": ["Paper"],
            "author": [{"given": "Qiuqi", "family": "Wang"}],
        }
        pages = [
            {"items": [work] * 100, "next-cursor": "next"},
            {"items": []},
            {"items": []},
        ]
        with patch.object(pub, "fetch_url", side_effect=[json.dumps({"message": page}).encode() for page in pages]) as fetch, patch.object(pub.time, "sleep"):
            records = pub.discover_ssrn(CONFIG)
        self.assertEqual(len(records), 1)
        second_query = urllib.parse.parse_qs(urllib.parse.urlparse(fetch.call_args_list[1].args[0]).query)
        self.assertEqual(second_query["cursor"], ["next"])

    def test_newest_first_stable_numbers_and_idempotence(self):
        entries = [record("Newer paper", "2610.00002", date="2026-10-07T08:00:00Z"), record("Older paper", "2610.00001", date="2026-10-07T02:00:00Z")]
        pub.merge_discoveries(self.data, entries, CONFIG)
        items = self.data[0]["items"]
        self.assertEqual([(item["number"], item["title"]) for item in items], [("P5", "Newer paper"), ("P4", "Older paper"), ("P3", "Existing manuscript")])
        snapshot = copy.deepcopy(self.data)
        changed, _ = pub.merge_discoveries(self.data, entries, CONFIG)
        self.assertEqual(changed, 0)
        self.assertEqual(self.data, snapshot)

    def test_same_paper_on_both_sources_gets_one_entry(self):
        entries = [record("New paper: a result", "2610.00001"), record("NEW PAPER -- A RESULT", "1234", "SSRN")]
        pub.merge_discoveries(self.data, entries, CONFIG)
        new_items = [item for item in self.data[0]["items"] if item["number"] != "P3"]
        self.assertEqual(len(new_items), 1)
        self.assertEqual({link["label"] for link in new_items[0]["links"]}, {"arXiv", "SSRN"})

    def test_existing_published_paper_keeps_citation_and_capitalization(self):
        pub.merge_discoveries(self.data, [record("E-BACKTESTING", "4206997", "SSRN")], CONFIG)
        article = self.data[1]["items"][0]
        self.assertEqual(len(self.data[0]["items"]), 1)
        self.assertEqual(article["title"], "E-backtesting")
        self.assertEqual(article["authors"], "Curated authors")
        self.assertEqual(article["venue"], "Published journal citation, 2026")
        self.assertEqual(article["links"][-1]["label"], "SSRN")

    def test_renamed_version_matches_existing_identifier(self):
        pub.merge_discoveries(self.data, [record("Renamed manuscript", "2511.05840")], CONFIG)
        self.assertEqual(len(self.data[0]["items"]), 1)
        self.assertEqual(self.data[0]["items"][0]["title"], "Existing manuscript")

    def test_companion_mapping(self):
        config = dict(CONFIG, related_records={"SSRN:4346325": {"publication": "J10", "label": "SSRN supplement"}})
        pub.merge_discoveries(self.data, [record("Simulation and data analysis for E-backtesting", "4346325", "SSRN")], config)
        self.assertEqual(len(self.data[0]["items"]), 1)
        self.assertEqual(self.data[1]["items"][0]["links"][-1]["label"], "SSRN supplement")

    def test_ssrn_preprint_is_not_a_journal_citation(self):
        message = {"DOI": "10.2139/ssrn.1234", "title": ["New paper"], "issued": {"date-parts": [[2026, 10, 7]]}, "author": [{"given": "Qiuqi", "family": "Wang"}], "container-title": ["SSRN Electronic Journal"]}
        self.assertEqual(pub.ssrn_record(message)["venue"], "Preprint, 2026")
        item = {"title": "New paper", "authors": "", "venue": "", "links": [{"label": "SSRN", "url": "https://ssrn.com/abstract=1234"}]}
        changed, _ = pub.update_item(item, "missing", {"SSRN:1234": pub.ssrn_record(message)})
        self.assertTrue(changed)
        self.assertEqual(item["venue"], "Preprint, 2026")

    def test_curated_case_and_final_venues(self):
        self.assertFalse(pub.should_update("A lowercase title", "A Lowercase Title", "refresh", "title"))
        self.assertFalse(pub.should_update("<strong>Wang, Q.</strong>", "<strong>WANG, Q.</strong>", "refresh", "authors"))
        self.assertTrue(pub.should_update("Journal, forthcoming", "<em>Journal</em>, <strong>4</strong>, 2026", "missing", "venue"))
        self.assertFalse(pub.should_update("Published citation, 2026", "Preprint, 2025", "missing", "venue"))

    def test_source_failure_does_not_discard_other_source(self):
        with patch.object(pub, "discover_arxiv", return_value=[record("New arXiv paper", "2610.00001")]), patch.object(pub, "discover_ssrn", side_effect=urllib.error.URLError("unavailable")), patch.object(pub, "load_publications", return_value=self.data), patch.object(pub, "dump_publications") as save, patch.object(pub, "update_item", return_value=(False, [])), patch.object(pub.time, "sleep"), patch("sys.argv", ["updater", "--discover", "--write", "--fail-on-error"]):
            self.assertEqual(pub.main(), 1)
        save.assert_called_once()
        self.assertEqual(self.data[0]["items"][0]["title"], "New arXiv paper")


if __name__ == "__main__":
    unittest.main()
