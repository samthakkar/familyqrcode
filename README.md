# Family Function QR Codes

Create a separate QR code for every family on your guest list. Each code opens
a public GitHub Pages pass in the phone browser, showing the welcome message,
family name, number of people, event date, and entry time slot.

The QR codes link to a static page, so no server needs to be managed. Family
details are encoded in each link and can be seen by anyone who scans that QR.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Publish the family page

This repository is public, which is required for free GitHub Pages hosting.
On GitHub, open **Settings → Pages**, choose **Deploy from a branch**, select
`mts` and `/docs`, then save. GitHub Pages will publish the site at
`https://pknowledge.github.io/sample/`.

The app's default GitHub Pages URL matches this repository. Wait for the page
to publish before distributing QR codes. If the repository or Pages URL changes,
update the URL in the app before generating codes.

## Generate QR codes

Upload an `.xlsx` spreadsheet or `.csv` file with one family per row. Select the
columns containing family names, member counts, and priority, set the event
details and poster wording, then generate and download a ZIP containing a
decorative poster PNG for each family. You can also enter a single family's
details on screen to preview and download one poster. The poster uses the
supplied design, and the QR links to the matching family page.
Download the Excel template from the app for the expected column layout.

Rows with missing family names or invalid member counts are skipped and shown
before generation. Member counts must be whole numbers greater than zero.
Priority must be a whole number from 1 to 9: priority 1 starts at 4:45 PM,
followed by consecutive 15-minute slots through 7:00 PM. Families sharing a
priority have the same entry slot.

To run the focused tests:

```bash
python -m unittest discover -s tests
```
