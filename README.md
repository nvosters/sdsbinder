# SDS Binder (AI-assisted verification workflow)

This version upgrades the binder to use an **AI-assisted intake flow**:

1. User uploads a product label image.
2. AI extracts `product_name` and `manufacturer` (with fallback to filename parsing).
3. App searches and ranks likely SDS URLs.
4. User verifies/edit selection.
5. On confirmation, item is saved to the binder automatically.

## Why this is better
- Keeps a human verification checkpoint before saving.
- Uses AI to improve image extraction and SDS ranking quality over plain search links.

## Setup
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install flask requests beautifulsoup4 openai
python app.py
```

Open: `http://localhost:8000`

## OpenAI configuration (optional, recommended)
Set your API key to enable AI image understanding + AI ranking:

```bash
export OPENAI_API_KEY="your_key_here"   # Windows PowerShell: $env:OPENAI_API_KEY="your_key_here"
```

Without the key, the app still works using filename parsing + heuristic ranking.
