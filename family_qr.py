import io
import re
import zipfile
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple, TypedDict
from urllib.parse import urlencode, urlsplit, urlunsplit

import pandas as pd
import qrcode
from PIL import Image, ImageDraw, ImageFont

SLOT_MINUTES = 15
EVENT_DURATION_MINUTES = 135
SLOT_COUNT = EVENT_DURATION_MINUTES // SLOT_MINUTES
POSTER_TEMPLATE_PATH = Path(__file__).parent / "assets" / "qr-poster-template.png"


class Family(TypedDict):
    name: str
    members: int
    priority: int


def normalize_header(header: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(header).casefold())


def guess_column(headers: List[object], candidates: Tuple[str, ...]) -> Optional[int]:
    normalized_candidates = {normalize_header(candidate) for candidate in candidates}
    for index, header in enumerate(headers):
        if normalize_header(header) in normalized_candidates:
            return index
    return None


def build_time_slots(start_time: time) -> List[str]:
    start = datetime.combine(date.today(), start_time)
    return [
        "{} - {}".format(
            (start + timedelta(minutes=index * SLOT_MINUTES)).strftime("%I:%M %p"),
            (
                start
                + timedelta(minutes=(index + 1) * SLOT_MINUTES)
            ).strftime("%I:%M %p"),
        )
        for index in range(SLOT_COUNT)
    ]


def validate_families(
    data: pd.DataFrame,
    name_column: object,
    count_column: object,
    priority_column: object,
) -> Tuple[List[Family], List[str]]:
    families: List[Family] = []
    errors: List[str] = []
    for row_number, (_, row) in enumerate(data.iterrows(), start=2):
        name_value = row[name_column]
        count_value = row[count_column]
        priority_value = row[priority_column]
        name = "" if pd.isna(name_value) else str(name_value).strip()
        if not name:
            errors.append(f"Row {row_number}: family name is missing.")
            continue

        try:
            member_count = Decimal(str(count_value).strip())
        except (InvalidOperation, ValueError):
            errors.append(f"Row {row_number}: member count must be a whole number.")
            continue
        if (
            not member_count.is_finite()
            or member_count != member_count.to_integral_value()
            or member_count < 1
        ):
            errors.append(
                f"Row {row_number}: member count must be a whole number greater than 0."
            )
            continue

        try:
            priority = Decimal(str(priority_value).strip())
        except (InvalidOperation, ValueError):
            errors.append(
                f"Row {row_number}: priority must be a whole number from 1 to {SLOT_COUNT}."
            )
            continue
        if (
            not priority.is_finite()
            or priority != priority.to_integral_value()
            or priority < 1
            or priority > SLOT_COUNT
        ):
            errors.append(
                f"Row {row_number}: priority must be a whole number from 1 to {SLOT_COUNT}."
            )
            continue

        families.append(
            {
                "name": name,
                "members": int(member_count),
                "priority": int(priority),
            }
        )
    return families, errors


def normalize_pages_base_url(base_url: str) -> str:
    parsed = urlsplit(base_url.strip())
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Enter a GitHub Pages base URL starting with https://.")
    path = parsed.path.rstrip("/") + "/"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def build_family_page_url(
    base_url: str,
    family_name: str,
    member_count: int,
    event_date: date,
    time_slot: str,
    event_name: str,
    headline: str,
    subtitle: str,
    organization: str = "Nirmal Jain Sangh Auckland",
) -> str:
    event_title = event_name.strip()
    if event_title.casefold().startswith("to "):
        event_title = event_title[3:].lstrip()
    query = urlencode(
        {
            "event": event_title,
            "family": family_name.strip(),
            "people": member_count,
            "date": event_date.isoformat(),
            "slot": time_slot,
            "headline": headline.strip(),
            "subtitle": subtitle.strip(),
            "organization": organization.strip(),
        }
    )
    return f"{normalize_pages_base_url(base_url)}?{query}"


def generate_qr_png(payload: str) -> bytes:
    image = qrcode.make(payload)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@lru_cache(maxsize=1)
def _load_poster_template() -> Image.Image:
    with Image.open(POSTER_TEMPLATE_PATH) as image:
        return image.convert("RGB")


def _load_poster_font(size: int, style: str) -> ImageFont.FreeTypeFont:
    font_names = {
        "bold": ("Georgia Bold.ttf", "Georgia-Bold.ttf"),
        "italic": ("Georgia Italic.ttf", "Georgia-Italic.ttf"),
        "regular": ("Georgia.ttf", "Georgia.ttf"),
    }
    font_directories = (
        Path("/System/Library/Fonts/Supplemental"),
        Path("/Library/Fonts"),
    )
    for directory in font_directories:
        for font_name in font_names[style]:
            font_path = directory / font_name
            if font_path.is_file():
                return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default(size=size)


def _fit_poster_font(
    draw: ImageDraw.ImageDraw, text: str, max_width: int, size: int, style: str
) -> ImageFont.FreeTypeFont:
    while size > 16:
        font = _load_poster_font(size, style)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return font
        size -= 2
    return _load_poster_font(size, style)


def render_family_poster(
    qr_png: bytes,
    headline: str,
    subtitle: str,
    event_name: str,
) -> bytes:
    poster = _load_poster_template().copy()
    draw = ImageDraw.Draw(poster)
    width, height = poster.size

    title_box = (
        int(width * 0.13),
        int(height * 0.215),
        int(width * 0.87),
        int(height * 0.40),
    )
    draw.rounded_rectangle(
        title_box,
        radius=int(width * 0.09),
        fill="#fffdfd",
        outline="#e8b44e",
        width=max(3, width // 150),
    )
    draw.rounded_rectangle(
        (
            title_box[0] + 8,
            title_box[1] + 8,
            title_box[2] - 8,
            title_box[3] - 8,
        ),
        radius=int(width * 0.08),
        outline="#b767ae",
        width=max(2, width // 300),
    )

    text_width = int(width * 0.60)
    if subtitle.strip():
        headline_y = int(height * 0.225)
        subtitle_y = int(height * 0.29)
        event_y = int(height * 0.34)
        event_size = 42
    else:
        headline_y = int(height * 0.245)
        event_y = int(height * 0.325)
        subtitle_y = 0
        event_size = 54

    headline = headline.strip()
    event_name = event_name.strip()
    if headline:
        headline_font = _fit_poster_font(
            draw, headline, text_width, 62, "bold"
        )
        draw.text(
            (width // 2, headline_y),
            headline,
            font=headline_font,
            fill="#310040",
            anchor="mt",
        )
    if subtitle.strip():
        subtitle_font = _fit_poster_font(
            draw, subtitle.strip(), text_width, 34, "italic"
        )
        draw.text(
            (width // 2, subtitle_y),
            subtitle.strip(),
            font=subtitle_font,
            fill="#171568",
            anchor="mt",
        )
    if event_name:
        event_font = _fit_poster_font(
            draw, event_name, text_width, event_size, "italic"
        )
        draw.text(
            (width // 2, event_y),
            event_name,
            font=event_font,
            fill="#50004f",
            anchor="mt",
        )

    card = (
        int(width * 0.18),
        int(height * 0.395),
        int(width * 0.82),
        int(height * 0.865),
    )
    draw.rounded_rectangle(
        card,
        radius=int(width * 0.05),
        fill="white",
        outline="#b767ae",
        width=max(5, width // 100),
    )
    draw.rounded_rectangle(
        (
            card[0] + 10,
            card[1] + 10,
            card[2] - 10,
            card[3] - 10,
        ),
        radius=int(width * 0.04),
        outline="#e8b44e",
        width=max(2, width // 300),
    )
    qr_size = int(width * 0.53)
    with Image.open(io.BytesIO(qr_png)) as qr_image:
        qr_image = qr_image.convert("RGB").resize(
            (qr_size, qr_size), Image.Resampling.NEAREST
        )
    qr_position = (
        (width - qr_size) // 2,
        card[1] + (card[3] - card[1] - qr_size) // 2,
    )
    poster.paste(qr_image, qr_position)

    output = io.BytesIO()
    poster.save(output, format="PNG")
    return output.getvalue()


def build_qr_archive(
    families: List[Family],
    pages_base_url: str,
    event_name: str,
    event_date: date,
    start_time: time,
    poster_headline: str = "Welcome",
    poster_subtitle: str = "",
) -> bytes:
    time_slots = build_time_slots(start_time)
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, family in enumerate(
            sorted(families, key=lambda item: item["priority"]), start=1
        ):
            priority = family["priority"]
            page_url = build_family_page_url(
                pages_base_url,
                family["name"],
                family["members"],
                event_date,
                time_slots[priority - 1],
                event_name,
                poster_headline,
                poster_subtitle,
            )
            safe_name = re.sub(
                r"[^A-Za-z0-9_-]+", "-", family["name"].strip()
            ).strip("-_") or "family"
            archive.writestr(
                f"{index:03d}_{safe_name}.png",
                render_family_poster(
                    generate_qr_png(page_url),
                    poster_headline,
                    poster_subtitle,
                    event_name,
                ),
            )
    return output.getvalue()
