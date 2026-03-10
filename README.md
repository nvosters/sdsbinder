# SDS Library Binder (Client-side MVP)

This project provides a simple **online SDS binder UI** organized like a library catalog.

## What it does
- Add products with name + manufacturer.
- Search products quickly.
- Organize products by alphabetic shelf (`A`, `B`, `C`, ...).
- Upload a product photo and attempt OCR extraction (in browser with Tesseract.js).
- If OCR fails, fallback to filename parsing (`Product by Manufacturer.jpg`).
- Auto-generate a one-click web search link for SDS PDF discovery.

## Run
You can host these static files with any web server, for example:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000`.

## Notes
- This MVP does not directly crawl vendor sites to auto-download PDFs due browser CORS and reliability constraints.
- Next step for full automation: add a backend worker that validates manufacturer/product matches and stores confirmed SDS PDF URLs.
