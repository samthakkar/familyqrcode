import hashlib
import io
import re
import zipfile
from datetime import date, time

import pandas as pd
import streamlit as st

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


NAME_HEADERS = ("familyname", "family", "household", "name")
COUNT_HEADERS = (
    "nooffamilymembers",
    "nofamilymembers",
    "numberoffamilymembers",
    "familymembers",
    "members",
    "numberofguests",
    "guestcount",
    "people",
    "count",
)
PRIORITY_HEADERS = ("priority", "entrypriority", "slotpriority")
DEFAULT_PAGES_URL = "https://iamsamirthakkar.github.io/familyqrcode/"


def read_family_file(file_name: str, file_bytes: bytes) -> pd.DataFrame:
    suffix = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
    source = io.BytesIO(file_bytes)
    if suffix == "csv":
        return pd.read_csv(source)
    if suffix == "xlsx":
        return pd.read_excel(source, engine="openpyxl")
    raise ValueError("Please upload an .xlsx or .csv file.")


def make_template() -> bytes:
    template = pd.DataFrame(
        [
            {
                "Family Name": "Example Family",
                "Number of Family Members": 4,
                "Priority": 1,
            }
        ]
    )
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        template.to_excel(writer, index=False)
    return output.getvalue()


def make_signature(
    file_bytes: bytes,
    event_name: str,
    poster_headline: str,
    poster_subtitle: str,
    pages_base_url: str,
    event_date: date,
    event_time: time,
    name_column: int,
    count_column: int,
    priority_column: int,
) -> str:
    digest = hashlib.sha256(file_bytes)
    digest.update(
        f"{event_name}|{poster_headline}|{poster_subtitle}|"
        f"{pages_base_url}|{event_date.isoformat()}|{event_time.isoformat()}|"
        f"{name_column}|{count_column}|{priority_column}".encode("utf-8")
    )
    return digest.hexdigest()


def safe_file_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-_")
    return cleaned or "family-function"


def main() -> None:
    st.set_page_config(page_title="Family Function QR Codes", page_icon="🎉")
    st.title("Family Function QR Codes")
    st.write(
        "Create a QR code for one family directly on screen, or generate a batch "
        "from your family list."
    )
    st.info(
        "Each QR code opens a family page hosted on GitHub Pages. Publish the "
        "repository's docs/ folder before sharing the codes. Family details are "
        "carried in the QR link, so anyone who scans it can view them."
    )

    template = make_template()
    st.download_button(
        "Download Excel template",
        data=template,
        file_name="family-list-template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    first, second = st.columns(2)
    with first:
        event_name = st.text_input("Event name", value="Moksh No Dwar")
        poster_headline = st.text_input("Poster headline", value="Welcome")
    with second:
        event_date = st.date_input("Event date (Excel upload)", value=date.today())
    poster_subtitle = st.text_input("Poster subtitle (optional)", value="")
    pages_base_url = st.text_input(
        "GitHub Pages site URL",
        value=DEFAULT_PAGES_URL,
        help="For this repository, the expected URL is https://iamsamirthakkar.github.io/familyqrcode/.",
    )
    try:
        pages_base_url = normalize_pages_base_url(pages_base_url)
    except ValueError as exc:
        st.error(str(exc))
        pages_url_valid = False
    else:
        pages_url_valid = True
    event_time = time(16, 45)
    time_slots = build_time_slots(event_time)
    st.caption(
        f"There are {SLOT_COUNT} 15-minute slots from 4:45 PM to 7:00 PM. "
        "Priority 1 is the first slot; priority 9 is the last. "
        "Families with the same priority share a slot."
    )
    slot_schedule = pd.DataFrame(
        {
            "Priority": range(1, SLOT_COUNT + 1),
            "Entry time": time_slots,
        }
    ).set_index("Priority")
    st.table(slot_schedule)

    st.subheader("Create one QR code")
    manual_name_column, manual_count_column = st.columns(2)
    with manual_name_column:
        manual_family_name = st.text_input("Family name", key="manual_family_name")
    with manual_count_column:
        manual_member_count = st.number_input(
            "Number of people",
            min_value=1,
            value=1,
            step=1,
            key="manual_member_count",
        )
    manual_date_column, manual_slot_column = st.columns(2)
    with manual_date_column:
        manual_event_date = st.date_input(
            "Event date for this family",
            value=event_date,
            key="manual_event_date",
        )
    with manual_slot_column:
        manual_slot_index = st.selectbox(
            "Entry time slot",
            options=range(SLOT_COUNT),
            format_func=lambda index: time_slots[index],
            key="manual_slot_index",
        )

    if manual_family_name.strip() and event_name.strip() and pages_url_valid:
        manual_slot = time_slots[manual_slot_index]
        manual_page_url = build_family_page_url(
            pages_base_url,
            manual_family_name.strip(),
            int(manual_member_count),
            manual_event_date,
            manual_slot,
            event_name.strip(),
            poster_headline,
            poster_subtitle,
        )
        manual_qr_png = generate_qr_png(manual_page_url)
        manual_poster_png = render_family_poster(
            manual_qr_png,
            poster_headline,
            poster_subtitle,
            event_name,
        )
        qr_preview_column, poster_preview_column = st.columns(2)
        with qr_preview_column:
            st.image(
                manual_qr_png,
                caption=f"Test QR — {manual_slot}",
                width=280,
            )
        with poster_preview_column:
            st.image(
                manual_poster_png,
                caption=f"Poster — {manual_family_name.strip()}",
                width=280,
            )
        st.link_button("Open this family's page", manual_page_url)
        st.download_button(
            "Download this family poster",
            data=manual_poster_png,
            file_name=f"{safe_file_part(manual_family_name)}-qr-poster.png",
            mime="image/png",
            key="download_manual_poster",
        )
    elif not manual_family_name.strip():
        st.caption("Enter a family name to see its QR code and poster preview.")
    elif not event_name.strip():
        st.warning("Enter an event name to generate the family QR code.")

    st.divider()
    uploaded_file = st.file_uploader(
        "Upload your family list", type=("xlsx", "csv")
    )
    if uploaded_file is None:
        st.caption(
            "Your spreadsheet should have one row per family, with a family name "
            "and the number of family members, plus a Priority value from 1 to 9."
        )
        return

    file_bytes = uploaded_file.getvalue()
    try:
        data = read_family_file(uploaded_file.name, file_bytes)
    except (
        ImportError,
        OSError,
        UnicodeDecodeError,
        ValueError,
        zipfile.BadZipFile,
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
    ) as exc:
        st.error(f"Could not read the uploaded file: {exc}")
        return

    if data.empty or len(data.columns) < 3:
        st.error("The spreadsheet needs a header row and at least three columns.")
        return

    headers = list(data.columns)
    st.subheader("Choose your spreadsheet columns")
    name_default = guess_column(headers, NAME_HEADERS)
    count_default = guess_column(headers, COUNT_HEADERS)
    priority_default = guess_column(headers, PRIORITY_HEADERS)
    name_index = st.selectbox(
        "Family name column",
        options=range(len(headers)),
        index=name_default if name_default is not None else 0,
        format_func=lambda index: str(headers[index]),
    )
    count_fallback = 1 if name_index == 0 else 0
    count_index = st.selectbox(
        "Number of family members column",
        options=range(len(headers)),
        index=count_default if count_default is not None else count_fallback,
        format_func=lambda index: str(headers[index]),
    )
    priority_fallback = next(
        (
            index
            for index in range(len(headers))
            if index not in (name_index, count_index)
        ),
        0,
    )
    priority_index = st.selectbox(
        "Priority column (values 1–9)",
        options=range(len(headers)),
        index=(
            priority_default
            if priority_default is not None
            else priority_fallback
        ),
        format_func=lambda index: str(headers[index]),
    )
    if len({name_index, count_index, priority_index}) != 3:
        st.error("Choose a different spreadsheet column for each field.")
        return

    families, row_errors = validate_families(
        data,
        headers[name_index],
        headers[count_index],
        headers[priority_index],
    )
    st.caption(f"Found {len(families)} valid family row(s).")
    with st.expander("Spreadsheet preview"):
        st.dataframe(data.head(20), use_container_width=True)
    if row_errors:
        with st.expander(f"Rows that will be skipped ({len(row_errors)})"):
            for error in row_errors:
                st.write(error)

    signature = make_signature(
        file_bytes,
        event_name,
        poster_headline,
        poster_subtitle,
        pages_base_url,
        event_date,
        event_time,
        name_index,
        count_index,
        priority_index,
    )
    if st.session_state.get("generated_signature") != signature:
        st.session_state.pop("generated_archive", None)
        st.session_state.pop("generated_families", None)
        st.session_state.pop("generated_signature", None)

    if st.button(
        "Generate family QR codes",
        type="primary",
        disabled=not families or not event_name.strip() or not pages_url_valid,
    ):
        ordered_families = sorted(families, key=lambda family: family["priority"])
        archive = build_qr_archive(
            ordered_families,
            pages_base_url,
            event_name.strip(),
            event_date,
            event_time,
            poster_headline,
            poster_subtitle,
        )
        st.session_state["generated_archive"] = archive
        st.session_state["generated_families"] = ordered_families
        st.session_state["generated_signature"] = signature

    if st.session_state.get("generated_signature") == signature:
        st.success(
            f"Created QR codes for "
            f"{len(st.session_state['generated_families'])} families."
        )
        st.download_button(
            "Download all QR codes (ZIP)",
            data=st.session_state["generated_archive"],
            file_name=f"{safe_file_part(event_name)}-family-qr-codes.zip",
            mime="application/zip",
        )
        generated_families = st.session_state["generated_families"]
        selected_index = st.selectbox(
            "Preview a family QR code",
            options=range(len(generated_families)),
            format_func=lambda index: generated_families[index]["name"],
        )
        selected = generated_families[selected_index]
        entry_time_slot = time_slots[selected["priority"] - 1]
        page_url = build_family_page_url(
            pages_base_url,
            selected["name"],
            selected["members"],
            event_date,
            entry_time_slot,
            event_name.strip(),
            poster_headline,
            poster_subtitle,
        )
        st.image(
            render_family_poster(
                generate_qr_png(page_url),
                poster_headline,
                poster_subtitle,
                event_name,
            ),
            caption=f"{selected['name']} — {entry_time_slot}",
            width=360,
        )
        st.link_button("Open this family's page", page_url)


if __name__ == "__main__":
    main()
