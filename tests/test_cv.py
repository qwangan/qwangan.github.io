"""Regression checks for service and grant entries in the generated CV."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CVServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.workspace.cleanup)
        root = Path(cls.workspace.name)
        shutil.copytree(ROOT / "_pages", root / "_pages")
        shutil.copytree(ROOT / "cv-source" / "static", root / "cv-source" / "static")
        (root / "scripts").mkdir()
        script = root / "scripts" / "build_cv.rb"
        shutil.copy2(ROOT / "scripts" / "build_cv.rb", script)
        subprocess.run(["ruby", str(script), "--tex-only"], check=True, capture_output=True, text=True)
        cls.tex = (root / "cv-source" / "Curriculum_Vitae.tex").read_text()

    def test_ampersands_render_as_latex_symbols_not_html_entities(self):
        self.assertNotIn(r"\&amp", self.tex)
        for text in (
            r"Finance \& Stochastics",
            r"Statistics \& Probability Letters",
        ):
            self.assertIn(text, self.tex)

    def test_irfa_belongs_only_to_finance(self):
        finance = next(line for line in self.tex.splitlines() if line.strip().startswith(r"\item Finance:"))
        self.assertIn(
            r"\emph{Quantitative Finance}, \emph{International Review of Financial Analysis}",
            finance,
        )
        self.assertIn("\\item Economics: \\emph{Economic Modelling}\n", self.tex)
        self.assertEqual(self.tex.count("International Review of Financial Analysis"), 1)

    def test_research_grant_survives_regeneration(self):
        heading = r"{\large \bf Competitive Research Grants}"
        entry = (
            "Faculty Internal Grants (Tier 1), Georgia State University"
            r" & [sole PI] FY27--28\\"
        )
        self.assertEqual(self.tex.count(entry), 1)
        self.assertLess(self.tex.index(heading), self.tex.index(entry))
        self.assertLess(self.tex.index(entry), self.tex.index("Selected Honors and Awards"))


if __name__ == "__main__":
    unittest.main()
