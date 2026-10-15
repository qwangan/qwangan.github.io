"""Regression checks for shared service data in the generated CV."""

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
            r"Econ. \& Fin.:",
            r"Finance \& Stochastics",
            r"Statistics \& Probability Letters",
        ):
            self.assertIn(text, self.tex)

    def test_last_service_row_has_comma_separated_journals(self):
        self.assertIn(
            r"Econ. \& Fin.: \emph{Economic Modelling}, \emph{International Review of Financial Analysis}",
            self.tex,
        )


if __name__ == "__main__":
    unittest.main()
