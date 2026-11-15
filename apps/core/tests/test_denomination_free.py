"""Guard for decision 0001: CHORD never records or mentions a denomination.

Scans the project's own code, templates, static files and seed data. If this
fails, turn the church difference into a setting instead of naming a
denomination (see docs/CHORD-Vault/02-Architecture/Decisions/0001).
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

BANNED = re.compile(
    r"\b(denominations?|denominational|traditions?|religions?)\b", re.IGNORECASE
)
SCANNED_DIRS = ("apps", "config", "templates", "static")
SKIPPED_DIRS = {"__pycache__", "vendor"}
SUFFIXES = {".py", ".html", ".txt", ".json", ".js", ".css", ".csv", ".yaml", ".yml"}
BASE_DIR = Path(settings.BASE_DIR)
THIS_FILE = Path(__file__).resolve()


def scanned_files():
    for top in SCANNED_DIRS:
        for path in (BASE_DIR / top).rglob("*"):
            if (
                path.suffix in SUFFIXES
                and path.is_file()
                and not SKIPPED_DIRS.intersection(path.parts)
                and path.resolve() != THIS_FILE
            ):
                yield path


class DenominationFreeTests(SimpleTestCase):
    def test_scan_covers_project_code(self):
        scanned = {p.relative_to(BASE_DIR).as_posix() for p in scanned_files()}
        self.assertIn("config/settings.py", scanned)
        self.assertIn("templates/base.html", scanned)

    def test_no_denomination_wording(self):
        hits = [
            f"{path.relative_to(BASE_DIR)}:{number}: {line.strip()}"
            for path in scanned_files()
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            )
            if BANNED.search(line)
        ]
        self.assertEqual(hits, [], "Denomination wording found:\n" + "\n".join(hits))
