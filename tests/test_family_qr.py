import io
import unittest
import zipfile
from datetime import date, time
from urllib.parse import parse_qs, urlsplit

import pandas as pd
from PIL import Image

from family_qr import (
    SLOT_COUNT,
    build_family_page_url,
    build_qr_archive,
    build_time_slots,
    generate_qr_png,
    guess_column,
    normalize_pages_base_url,
    render_family_poster,
    validate_families,
)
from streamlit_app import make_template, read_family_file


class FamilyQrTests(unittest.TestCase):
    def test_page_url_contains_encoded_family_and_event_details(self) -> None:
        page_url = build_family_page_url(
            "https://pknowledge.github.io/sample",
            "Samir & Family",
            5,
            date(2026, 12, 25),
            "05:00 PM - 05:15 PM",
            "To Moksh No Dwar",
            "Welcome",
            "",
        )

        parsed_url = urlsplit(page_url)
        params = parse_qs(parsed_url.query)
        self.assertEqual(parsed_url.scheme, "https")
        self.assertEqual(parsed_url.netloc, "pknowledge.github.io")
        self.assertEqual(parsed_url.path, "/sample/")
        self.assertEqual(params["event"], ["Moksh No Dwar"])
        self.assertEqual(params["family"], ["Samir & Family"])
        self.assertEqual(params["people"], ["5"])
        self.assertEqual(params["date"], ["2026-12-25"])
        self.assertEqual(params["slot"], ["05:00 PM - 05:15 PM"])
        self.assertEqual(params["headline"], ["Welcome"])

    def test_pages_base_url_requires_https(self) -> None:
        with self.assertRaises(ValueError):
            normalize_pages_base_url("http://pknowledge.github.io/sample/")

    def test_validation_checks_family_count_and_priority(self) -> None:
        data = pd.DataFrame(
            {
                "Family Name": [
                    "Patel Family",
                    "Missing count",
                    "Fractional",
                    "Bad priority",
                ],
                "Members": [5.0, None, 2.5, 3],
                "Priority": [1, 2, 3, 10],
            }
        )

        families, errors = validate_families(
            data, "Family Name", "Members", "Priority"
        )

        self.assertEqual(
            families, [{"name": "Patel Family", "members": 5, "priority": 1}]
        )
        self.assertEqual(len(errors), 3)
        self.assertIn("priority must be a whole number from 1 to 9", errors[-1])

    def test_time_slots_cover_4_45_to_7_in_15_minute_steps(self) -> None:
        slots = build_time_slots(time(16, 45))

        self.assertEqual(len(slots), 9)
        self.assertEqual(len(slots), SLOT_COUNT)
        self.assertEqual(slots[0], "04:45 PM - 05:00 PM")
        self.assertEqual(slots[-1], "06:45 PM - 07:00 PM")

    def test_column_detection_ignores_spaces_and_case(self) -> None:
        self.assertEqual(
            guess_column(
                ["Guest Name", " No. of Family Members "],
                ("nooffamilymembers", "numberoffamilymembers"),
            ),
            1,
        )

    def test_excel_template_can_be_read_back(self) -> None:
        template = read_family_file("template.xlsx", make_template())

        self.assertEqual(
            list(template.columns),
            ["Family Name", "Number of Family Members", "Priority"],
        )
        self.assertEqual(template.iloc[0]["Family Name"], "Example Family")

    def test_csv_family_list_can_be_read(self) -> None:
        data = read_family_file("families.csv", b"Family,Members\nPatel,5\n")

        self.assertEqual(data.iloc[0]["Family"], "Patel")
        self.assertEqual(data.iloc[0]["Members"], 5)

    def test_archive_contains_a_png_for_each_family(self) -> None:
        archive_bytes = build_qr_archive(
            [
                {"name": "Patel Family", "members": 5, "priority": 2},
                {"name": "Lee Family", "members": 2, "priority": 1},
            ],
            "https://pknowledge.github.io/sample/",
            "Family Reunion",
            date(2026, 12, 25),
            time(18, 30),
        )

        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            self.assertEqual(
                archive.namelist(),
                ["001_Lee-Family.png", "002_Patel-Family.png"],
            )
            self.assertTrue(archive.read(archive.namelist()[0]).startswith(b"\x89PNG"))

    def test_poster_uses_reference_image_dimensions(self) -> None:
        poster_bytes = render_family_poster(
            generate_qr_png("poster test"),
            "Welcome",
            "",
            "Moksh No Dwar",
        )

        with Image.open(io.BytesIO(poster_bytes)) as poster:
            self.assertEqual(poster.size, (768, 1086))


if __name__ == "__main__":
    unittest.main()
