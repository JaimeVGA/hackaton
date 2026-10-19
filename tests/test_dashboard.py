from pathlib import Path


ROOT = Path(__file__).parents[1]
DASHBOARD = ROOT / "dashboard"


def test_dashboard_has_static_entrypoint_and_data_sources():
    html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
    script = (DASHBOARD / "app.js").read_text(encoding="utf-8")

    assert '<title>La evolución de Jardine</title>' in html
    assert 'id="stage-summary"' in html
    assert 'loadCsv("stage_summary.csv")' in script
    assert 'loadCsv("match_metrics.csv")' in script
    assert 'loadCsv("formation_summary.csv")' in script


def test_dashboard_has_no_external_runtime_dependencies():
    html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
    script = (DASHBOARD / "app.js").read_text(encoding="utf-8")

    assert "https://" not in html
    assert "import " not in script
