from base64 import b64encode
import json
from pathlib import Path
import re


ROOT = Path(__file__).parents[1]
DASHBOARD = ROOT / "dashboard"
OUTPUT = ROOT / "dist" / "index.html"


def build() -> None:
    html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
    styles = (DASHBOARD / "styles.css").read_text(encoding="utf-8")
    model = (DASHBOARD / "ui-model.mjs").read_text(encoding="utf-8")
    app = (DASHBOARD / "app.js").read_text(encoding="utf-8")
    report = json.loads((DASHBOARD / "report_data.json").read_text(encoding="utf-8"))

    html = html.replace(
        '<link rel="stylesheet" href="styles.css">',
        f"<style>\n{styles}\n</style>",
    )
    for filename in ("possession-rhythm.svg", "match-evidence.svg"):
        asset = (DASHBOARD / "assets" / filename).read_bytes()
        data_uri = f"data:image/svg+xml;base64,{b64encode(asset).decode('ascii')}"
        html = html.replace(f'assets/{filename}', data_uri)

    app = re.sub(r"^import \{.*?^\} from \"\./ui-model\.mjs\";\s*", "", app, count=1, flags=re.M | re.S)
    model = model.replace("export function ", "function ")
    model = model.replace("matchesScope", "matchesModelScope")
    app = app.replace(
        'const response = await fetch("./report_data.json");\n'
        '  if (!response.ok) throw new Error("No se pudo cargar el reporte actualizado.");\n'
        "  const report = await response.json();",
        'const report = JSON.parse(document.querySelector("#report-data").textContent);',
    )

    inline_report = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
    inline_report = inline_report.replace("<", "\\u003c")
    app = f"{model}\n{app}"
    inline_script = f'<script type="application/json" id="report-data">{inline_report}</script>\n<script>\n{app}\n</script>'
    html = html.replace(
        '<script type="module" src="app.js"></script>',
        inline_script,
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    build()
