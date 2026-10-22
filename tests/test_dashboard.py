from pathlib import Path
import json
import subprocess


ROOT = Path(__file__).parents[1]
DASHBOARD = ROOT / "dashboard"


def test_dashboard_has_static_entrypoint_and_data_sources():
    html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
    script = (DASHBOARD / "app.js").read_text(encoding="utf-8")

    assert '<title>La evolución de Jardine</title>' in html
    assert 'id="stage-summary"' in html
    assert 'class="hero-wrap"' in html
    assert 'class="report-nav"' in html
    assert 'id="balon-parado"' in html
    assert 'id="jugadores"' in html
    assert html.index('id="alcance"') < html.index('id="panorama"')
    assert 'id="report-limitations"' in html
    assert 'id="metric-definitions"' in html
    assert "report_data.json" in script


def test_dashboard_translates_raw_stage_names_and_avoids_statistical_shorthand():
    script = (DASHBOARD / "app.js").read_text(encoding="utf-8")

    assert 'other_context: "Otros contextos"' in script
    assert 'replaceAll("_", " ")' in script
    assert "n=${" not in script
    assert "partidos${sampleHint}" in script
    assert 'offensive_sequence: "Secuencia ofensiva"' in script
    assert "La barra muestra el rango central" in (DASHBOARD / "index.html").read_text(encoding="utf-8")


def test_player_positions_are_shown_in_spanish():
    script = (DASHBOARD / "app.js").read_text(encoding="utf-8")

    assert '"Center Attacking Midfield": "Mediocampista ofensivo central"' in script
    assert '"Left Center Back": "Defensa central izquierdo"' in script
    assert '"Right Wing Back": "Carrilero derecho"' in script
    assert "positionNames[player.position]" in script


def test_dashboard_preserves_editorial_visual_treatment():
    styles = (DASHBOARD / "styles.css").read_text(encoding="utf-8")

    assert "--lime: #d8f06b" in styles
    assert ".hero-wrap" in styles
    assert ".bar-chart" in styles
    assert ".pitch" in styles
    assert "@media (max-width: 520px)" in styles


def test_distribution_contains_the_same_dashboard_and_generated_data():
    for filename in ("index.html", "app.js", "styles.css", "ui-model.mjs", "report_data.json"):
        assert (ROOT / "dist" / filename).is_file(), filename
    for filename in ("index.html", "app.js", "styles.css", "ui-model.mjs", "report_data.json"):
        assert (DASHBOARD / filename).read_bytes() == (ROOT / "dist" / filename).read_bytes()


def test_dashboard_has_no_external_runtime_dependencies():
    html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
    script = (DASHBOARD / "app.js").read_text(encoding="utf-8")

    assert "https://" not in html
    assert 'from "./ui-model.mjs"' in script
    assert 'type="module"' in html


def test_dashboard_data_supports_each_longitudinal_section():
    report = json.loads((ROOT / "dist/report_data.json").read_text(encoding="utf-8"))

    for collection in (
        "variability_summary",
        "progression_summary",
        "defensive_summary",
        "territorial_proxy",
    ):
        assert report[collection], f"{collection} must contain regenerated data"
    assert report["metadata"]["match_count"] == 183
    assert report["metadata"]["limitations"]


def run_ui_model(source):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_formation_display_groups_digits_without_changing_existing_labels():
    result = run_ui_model(
        'import { formatFormation } from "./dashboard/ui-model.mjs";'
        'console.log(JSON.stringify([formatFormation("4231"), formatFormation("433"), formatFormation("343"), formatFormation("3-4-3"), formatFormation("—")]));'
    )

    assert result == ["4-2-3-1", "4-3-3", "3-4-3", "3-4-3", "—"]


def test_team_goals_and_set_pieces_ignore_the_selected_player():
    result = run_ui_model(
        'import { filterPlayerActivity, filterTeamGoals, filterTeamSetPieces } from "./dashboard/ui-model.mjs";'
        'const activities = [{team:"América",stage:"A",player_id:"p1"},{team:"América",stage:"A",player_id:"p2"}];'
        'const shots = [{team:"América",stage:"A",shooting_team:"América",player:"p1",outcome:"Goal"},{team:"América",stage:"A",shooting_team:"América",player:"p2",outcome:"Goal"},{team:"América",stage:"A",shooting_team:"Rival",player:"p3",outcome:"Goal"}];'
        'const pieces = [{team:"América",stage:"A",player:"p1",pattern:"From Corner"},{team:"América",stage:"A",player:"p2",pattern:"From Free Kick"}];'
        'console.log(JSON.stringify({activity:filterPlayerActivity(activities,"América","A","p1"),goals:filterTeamGoals(shots,"América","A"),pieces:filterTeamSetPieces(pieces,"América","A")}));'
    )

    assert [row["player_id"] for row in result["activity"]] == ["p1"]
    assert [row["player"] for row in result["goals"]] == ["p1", "p2"]
    assert [row["pattern"] for row in result["pieces"]] == ["From Corner", "From Free Kick"]
