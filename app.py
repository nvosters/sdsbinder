from __future__ import annotations

import base64
import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "binder.db"

app = Flask(__name__)


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              product_name TEXT NOT NULL,
              manufacturer TEXT,
              sds_url TEXT,
              source TEXT,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def parse_filename(filename: str) -> tuple[str, str]:
    stem = Path(filename).stem.replace("_", " ").replace("-", " ")
    parts = re.split(r"\s+by\s+", stem, flags=re.I)
    if len(parts) == 2:
        return parts[0].strip().title(), parts[1].strip().title()
    return stem.strip().title(), ""


def image_to_data_url(path: Path) -> str:
    b = path.read_bytes()
    mime = "image/jpeg"
    if path.suffix.lower() == ".png":
        mime = "image/png"
    if path.suffix.lower() == ".webp":
        mime = "image/webp"
    return f"data:{mime};base64,{base64.b64encode(b).decode('utf-8')}"


def analyze_image(path: Path, filename: str) -> dict[str, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key and OpenAI is not None:
        client = OpenAI(api_key=api_key)
        prompt = (
            "Extract product name and manufacturer from this product label image. "
            "Return strict JSON with keys product_name and manufacturer."
        )
        try:
            data_url = image_to_data_url(path)
            resp = client.responses.create(
                model="gpt-4.1-mini",
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {"type": "input_image", "image_url": data_url},
                        ],
                    }
                ],
                temperature=0,
            )
            text = resp.output_text.strip()
            payload = json.loads(text)
            return {
                "product_name": str(payload.get("product_name", "")).strip(),
                "manufacturer": str(payload.get("manufacturer", "")).strip(),
            }
        except Exception:
            pass

    product, manufacturer = parse_filename(filename)
    return {"product_name": product, "manufacturer": manufacturer}


def ddg_results(query: str) -> list[str]:
    url = "https://duckduckgo.com/html/"
    try:
        r = requests.get(url, params={"q": query}, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except requests.RequestException:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    out: list[str] = []
    for a in soup.select("a.result__a"):
        href = a.get("href", "")
        if href and href not in out:
            out.append(href)
    return out


def heuristic_score(url: str, product_name: str, manufacturer: str) -> int:
    text = f"{url} {product_name} {manufacturer}".lower()
    score = 0
    if ".pdf" in text:
        score += 6
    if "sds" in text or "safety-data-sheet" in text or "safety data sheet" in text:
        score += 5
    if manufacturer and manufacturer.lower() in text:
        score += 3
    for token in product_name.lower().split():
        if len(token) > 2 and token in text:
            score += 1
    trusted = ["sigmaaldrich", "fisher", "scjp", "3m", "diversey", "clorox", "ecolab", "wd40"]
    if any(t in text for t in trusted):
        score += 2
    return score


def ai_rank(product_name: str, manufacturer: str, urls: list[str]) -> list[dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not (api_key and OpenAI is not None):
        ranked = sorted(urls, key=lambda u: heuristic_score(u, product_name, manufacturer), reverse=True)
        return [{"url": u, "confidence": "medium" if i == 0 else "low"} for i, u in enumerate(ranked[:5])]

    client = OpenAI(api_key=api_key)
    prompt = (
        "You are selecting likely SDS links for a chemical/product. "
        "Given product name, manufacturer, and candidate URLs, return strict JSON list: "
        "[{url, confidence}] confidence one of high/medium/low. Prioritize direct PDFs and manufacturer pages."
    )
    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=f"{prompt}\nProduct: {product_name}\nManufacturer: {manufacturer}\nURLs:\n" + "\n".join(urls[:15]),
            temperature=0,
        )
        parsed = json.loads(resp.output_text)
        if isinstance(parsed, list):
            return [
                {"url": str(x.get("url", "")).strip(), "confidence": str(x.get("confidence", "low")).strip()}
                for x in parsed
                if isinstance(x, dict) and x.get("url")
            ][:5]
    except Exception:
        pass

    ranked = sorted(urls, key=lambda u: heuristic_score(u, product_name, manufacturer), reverse=True)
    return [{"url": u, "confidence": "medium" if i == 0 else "low"} for i, u in enumerate(ranked[:5])]


def find_sds_candidates(product_name: str, manufacturer: str) -> list[dict[str, Any]]:
    queries = [
        f'"{product_name}" "{manufacturer}" SDS pdf',
        f'"{product_name}" "safety data sheet"',
        f'"{manufacturer}" "{product_name}" sds',
    ]
    urls: list[str] = []
    for q in queries:
        urls.extend(ddg_results(q))
    deduped = []
    seen = set()
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return ai_rank(product_name, manufacturer, deduped)


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/products")
def list_products():
    with db() as conn:
        rows = conn.execute("SELECT * FROM products ORDER BY product_name").fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/scan")
def api_scan():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
    f = request.files["image"]
    if not f.filename:
        return jsonify({"error": "Missing filename"}), 400

    suffix = Path(f.filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        f.save(tmp.name)
        tmp_path = Path(tmp.name)

    extracted = analyze_image(tmp_path, f.filename)
    product = extracted.get("product_name", "").strip()
    manufacturer = extracted.get("manufacturer", "").strip()
    if not product:
        return jsonify({"error": "Could not identify product name"}), 422

    candidates = find_sds_candidates(product, manufacturer)
    return jsonify(
        {
            "product_name": product,
            "manufacturer": manufacturer,
            "candidates": candidates,
            "needs_verification": True,
        }
    )


@app.post("/api/verify-add")
def api_verify_add():
    payload = request.get_json(force=True)
    product = str(payload.get("product_name", "")).strip()
    manufacturer = str(payload.get("manufacturer", "")).strip()
    sds_url = str(payload.get("sds_url", "")).strip()
    source = str(payload.get("source", "ai-assisted")).strip()
    if not product or not sds_url:
        return jsonify({"error": "product_name and sds_url are required"}), 400

    with db() as conn:
        conn.execute(
            "INSERT INTO products (product_name, manufacturer, sds_url, source) VALUES (?, ?, ?, ?)",
            (product, manufacturer, sds_url, source),
        )
        conn.commit()
    return jsonify({"ok": True})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=True)
