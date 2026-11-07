"""Build the deployed dashboard from its canonical production sources.

No ERP records or credentials are embedded. Data comes from /api/dataset.
Legacy review assembly files are retained as references and are not production
inputs; this preserves the latest navigation, permissions and filtering UX.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def build():
    page = (ROOT / "production_shell.html").read_text(encoding="utf-8")
    inputs = {
        "__PRODUCTION_FFLATE__": "vendor/fflate.js",
        "__PRODUCTION_D3__": "vendor/d3.min.js",
        "__PRODUCTION_APP__": "app_prod.js",
    }
    for token, path in inputs.items():
        assert page.count(token) == 1, f"Missing or duplicate placeholder: {token}"
        source = (ROOT / path).read_text(encoding="utf-8")
        assert "</script" not in source.lower(), f"Unsafe inline script: {path}"
        page = page.replace(token, source, 1)
    target = ROOT.parent / "app" / "web" / "dashboard.html"
    target.write_text(page, encoding="utf-8")
    print(f"Production dashboard: {len(page.encode())} bytes")

if __name__ == "__main__":
    build()
