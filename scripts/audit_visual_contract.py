"""Read-only source-to-visual inventory for the NG dashboard.

Run: python scripts/audit_visual_contract.py
This script never connects to Railway or modifies imported data.
"""
from pathlib import Path
import re
import json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend" / "app_prod.js"
OUTPUT = ROOT / "audit" / "visual_contract_inventory.json"

def inventory(source: str) -> dict:
    pages = re.findall(r"\bfunction\s+(page[A-Za-z0-9_]+|pp[A-Za-z0-9_]+)\s*\(", source)
    cards = re.findall(r"\bcard\s*\(\s*(['\"])(.*?)\1", source)
    kpis = re.findall(r"\bkpi\s*\(\s*(['\"])(.*?)\1", source)
    return {
        "source": "frontend/app_prod.js",
        "pages": sorted(set(pages)),
        "literal_card_titles": sorted(set(title for _, title in cards)),
        "literal_kpi_labels": sorted(set(title for _, title in kpis)),
        "checks": {
            "has_shared_card_renderer": "function card(" in source,
            "has_shared_kpi_renderer": "function kpi(" in source,
            "has_visual_export": "function exportVisibleVisuals(" in source,
            "has_filter_menu": "function renderMenu(" in source,
            "has_comparison_context": "function reportingContext(" in source,
            "has_business_explanation_terms": "What this means" in source and "How it is calculated" in source,
        },
        "limitations": [
            "Static inventory: dynamic labels and runtime-only visuals require browser audit.",
            "Does not establish source Excel-to-database reconciliation.",
            "Does not establish that historical needs_review imports are valid.",
        ],
    }

def main() -> None:
    result = inventory(SOURCE.read_text(encoding="utf-8"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"page_count": len(result["pages"]),
                      "literal_card_count": len(result["literal_card_titles"]),
                      "literal_kpi_count": len(result["literal_kpi_labels"]),
                      "checks": result["checks"]}, indent=2))
    if not all(v for k, v in result["checks"].items() if k != "has_business_explanation_terms"):
        raise SystemExit("Required visual infrastructure missing")

if __name__ == "__main__":
    main()
