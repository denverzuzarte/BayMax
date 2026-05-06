#!/usr/bin/env python3
"""
parse_insurance_pdf.py — Parse insurance network hospital PDFs using Claude Haiku.

STRATEGY (cheapest + most reliable):
  1. pdfplumber extracts raw text from the PDF page by page (free, handles tables)
  2. Text is sent to Claude claude-haiku-4-5 in batches of 15 pages
  3. Haiku extracts {name, city, state} JSON from each batch
  4. Results are deduplicated and saved to data/insurance_networks/{slug}.json

WHY HAIKU: ~$0.25 per million input tokens. A 100-page PDF is ~50,000 tokens = ~$0.01.
WHY BATCHES: Avoids context limits. 15 pages ≈ 3,000-5,000 tokens per batch.
WHY pdfplumber OVER DIRECT PDF TO CLAUDE: Some insurance PDFs are 200+ pages.
  Sending the whole PDF as a document would be slow and expensive.
  Text extraction is instant and produces cleaner, smaller input.

Usage:
  python3 tools/parse_insurance_pdf.py --url <pdf_url> --insurer "Star Health"
  python3 tools/parse_insurance_pdf.py --file network.pdf --insurer "HDFC ERGO"
  python3 tools/parse_insurance_pdf.py --demo
  python3 tools/parse_insurance_pdf.py --test    # test with a known public PDF

Output:
  data/insurance_networks/{insurer_slug}.json
"""

import os, sys, json, re, time, argparse, tempfile, hashlib
from pathlib import Path

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import pdfplumber
except ImportError:
    print("pdfplumber not installed. Run: pip3 install pdfplumber")
    sys.exit(1)

try:
    import anthropic
except ImportError:
    print("anthropic not installed. Run: pip3 install anthropic")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("requests not installed. Run: pip3 install requests")
    sys.exit(1)

from dotenv import load_dotenv
load_dotenv()

OUT_DIR = Path(__file__).parent.parent / "data" / "insurance_networks"
OUT_DIR.mkdir(parents=True, exist_ok=True)

EXTRACT_PROMPT = """Extract every hospital, clinic, or medical facility listed in the text below.
Return ONLY a JSON array. No explanation, no markdown fences, just the array.
Each entry must have these fields:
  "name"  — exact hospital/clinic name as written
  "city"  — city name (infer from context if not explicit per row)
  "state" — Indian state name (2-3 letter code if known, else full name)

If the same hospital appears multiple times, include it once.
If a field cannot be determined, use null.

Text:
{text}"""


# ─────────────────────────────────────────────────────────────
#  PDF extraction
# ─────────────────────────────────────────────────────────────

def extract_text_from_pdf(path: str, max_pages: int = 200) -> list[str]:
    """Returns list of page text strings."""
    pages = []
    try:
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages[:max_pages]):
                text = page.extract_text() or ""
                # Also try table extraction — many insurance PDFs are tables
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row:
                            text += " | ".join(str(c or "") for c in row) + "\n"
                pages.append(text.strip())
    except Exception as e:
        print(f"  [pdfplumber error] {e}")
    return pages


def download_pdf(url: str) -> str:
    """Downloads a PDF to a temp file, returns the path."""
    print(f"  Downloading: {url}")
    resp = requests.get(url, timeout=30, headers={
        "User-Agent": "Mozilla/5.0 (BayMax/1.0 insurance-parser)"
    })
    resp.raise_for_status()
    suffix = ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(resp.content)
        return tmp.name


# ─────────────────────────────────────────────────────────────
#  Claude Haiku extraction
# ─────────────────────────────────────────────────────────────

def extract_hospitals_with_claude(pages: list[str], batch_size: int = 15,
                                   verbose: bool = True) -> list[dict]:
    """
    Sends page batches to Claude Haiku and extracts hospital records.
    Returns deduplicated list of {name, city, state} dicts.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("  [ERROR] ANTHROPIC_API_KEY not set")
        return []

    client = anthropic.Anthropic(api_key=api_key)
    all_hospitals = []
    seen = set()

    batches = [pages[i:i+batch_size] for i in range(0, len(pages), batch_size)]
    total_batches = len(batches)

    for idx, batch in enumerate(batches, 1):
        text = "\n\n--- PAGE BREAK ---\n\n".join(batch)
        if len(text.strip()) < 50:
            continue   # skip near-empty pages

        if verbose:
            print(f"  Batch {idx}/{total_batches} ({len(batch)} pages, ~{len(text)//4} tokens)...",
                  end="", flush=True)

        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": EXTRACT_PROMPT.format(text=text[:12000])  # cap per batch
                }]
            )
            raw = msg.content[0].text.strip()

            # Strip accidental markdown fences
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$",       "", raw)
            raw = raw.strip()

            parsed = json.loads(raw)
            if isinstance(parsed, list):
                added = 0
                for h in parsed:
                    if not isinstance(h, dict) or not h.get("name"):
                        continue
                    key = (h["name"].lower().strip(), (h.get("city") or "").lower().strip())
                    if key not in seen:
                        seen.add(key)
                        all_hospitals.append({
                            "name":  h.get("name", "").strip(),
                            "city":  (h.get("city") or "").strip(),
                            "state": (h.get("state") or "").strip(),
                        })
                        added += 1
                if verbose:
                    print(f" +{added} hospitals")
            else:
                if verbose: print(" (no array returned)")

        except json.JSONDecodeError:
            if verbose: print(" (JSON parse error — skipping batch)")
        except Exception as e:
            if verbose: print(f" (error: {e})")

        # Rate limit cushion
        time.sleep(0.3)

    return all_hospitals


# ─────────────────────────────────────────────────────────────
#  Save output
# ─────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def save_output(insurer: str, hospitals: list[dict], source_url: str = None) -> Path:
    slug    = slugify(insurer)
    outpath = OUT_DIR / f"{slug}.json"
    payload = {
        "insurer":      insurer,
        "slug":         slug,
        "total":        len(hospitals),
        "source_url":   source_url,
        "parsed_at":    time.strftime("%Y-%m-%d"),
        "hospitals":    sorted(hospitals, key=lambda h: (h.get("city",""), h.get("name",""))),
    }
    outpath.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return outpath


# ─────────────────────────────────────────────────────────────
#  Main entry points
# ─────────────────────────────────────────────────────────────

def parse_pdf(source: str, insurer: str, is_url: bool = False) -> Path:
    """Parse a PDF (file path or URL) and save output."""
    print(f"\n{'='*55}")
    print(f"  Insurer : {insurer}")
    print(f"  Source  : {source[:70]}")

    tmp_path = None
    try:
        if is_url:
            tmp_path = download_pdf(source)
            pdf_path = tmp_path
        else:
            pdf_path = source

        print(f"  Extracting text with pdfplumber...")
        pages = extract_text_from_pdf(pdf_path)
        print(f"  Extracted {len(pages)} pages")

        print(f"  Sending to Claude Haiku for structured extraction...")
        hospitals = extract_hospitals_with_claude(pages)

        out = save_output(insurer, hospitals, source if is_url else None)
        print(f"  ✓ Saved {len(hospitals)} hospitals → {out}")
        return out

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# Known public PDF URLs for demo insurers
DEMO_PDFS = [
    {
        "insurer": "Star Health",
        "url": "https://www.starhealth.in/pdf/StarHealthNetworkHospitalList.pdf",
        "fallback": True,  # use seed data if URL fails
    },
    {
        "insurer": "HDFC ERGO",
        "url": "https://www.hdfcergo.com/docs/default-source/downloads/network-hospitals.pdf",
        "fallback": True,
    },
    {
        "insurer": "Niva Bupa",
        "url": "https://www.nivabupa.com/content/dam/bajaja-allianz/niva-bupa/pdfs/network-hospitals.pdf",
        "fallback": True,
    },
]


def run_demo():
    """Process all demo PDFs. Uses fallback seed data if URLs fail."""
    from tools.seed_insurance_data import write_seed_data
    write_seed_data()

    for item in DEMO_PDFS:
        out_path = OUT_DIR / f"{slugify(item['insurer'])}.json"
        if out_path.exists():
            data = json.loads(out_path.read_text())
            print(f"  {item['insurer']}: already parsed ({data['total']} hospitals) — skipping")
            continue

        try:
            parse_pdf(item["url"], item["insurer"], is_url=True)
        except Exception as e:
            print(f"  {item['insurer']}: URL failed ({e}) — using seed data")
            if item.get("fallback"):
                from tools.seed_insurance_data import write_seed_data
                write_seed_data(only=item["insurer"])


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse insurance network PDFs")
    parser.add_argument("--url",     help="PDF URL to download and parse")
    parser.add_argument("--file",    help="Local PDF file path")
    parser.add_argument("--insurer", help="Insurer name (e.g. 'Star Health')")
    parser.add_argument("--demo",    action="store_true", help="Process all demo insurers")
    parser.add_argument("--test",    action="store_true", help="Test with a small public PDF")
    args = parser.parse_args()

    if args.demo:
        run_demo()

    elif args.test:
        # Test with a tiny public PDF
        print("Testing parser with a sample public PDF...")
        test_url = "https://pmjay.gov.in/sites/default/files/2023-01/HospitalEmpanelmentList.pdf"
        try:
            parse_pdf(test_url, "PMJAY Hospitals", is_url=True)
        except Exception as e:
            print(f"Test URL failed ({e}). Testing with local seed data instead.")
            from tools.seed_insurance_data import write_seed_data
            write_seed_data()

    elif args.url and args.insurer:
        parse_pdf(args.url, args.insurer, is_url=True)

    elif args.file and args.insurer:
        parse_pdf(args.file, args.insurer, is_url=False)

    else:
        parser.print_help()
