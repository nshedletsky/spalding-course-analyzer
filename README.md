# Spalding Course Requirement Analyzer

Upload program-sheet PDFs or a ZIP, identify numbered course codes, match them against Jane's course catalog, view program-sheet counts and named programs, and download a formatted Excel analysis.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Important limitations
- Counts **program-sheet listings**, not student enrollment or projected demand.
- A listed course isn't always required; alternatives, notes, concentrations and double majors need review.
- Subject-only requirements such as HIST and RS are reported separately.
- Scanned/image-only PDFs need OCR and may yield no results.
- Review **Extraction Audit** and **Unmatched Codes** before using counts for curriculum decisions.
- Uploaded files and analyses aren't stored in a database.
