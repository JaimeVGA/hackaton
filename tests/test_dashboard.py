from pathlib import Path
import json
import re
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
    assert 'id="report-limitations"' not in html
    assert 'id="metric-definitions"' not in html
    assert "report_data.json" in script


def test_dashboard_presents_all_filtered_matches_and_unique_players():
    script = (DASHBOARD / "app.js").read_text(encoding="utf-8")
    model = (DASHBOARD / "ui-model.mjs").read_text(encoding="utf-8")
    html = (DASHBOARD / "index.html").read_text(encoding="utf-8")

    assert "const visible = rows.filter((row) => matchesScope(row, team, stage));" in script
    assert "slice(0, 40)" not in script
    assert "uniquePlayers(report.player_summary" in script
    assert "function uniquePlayers(rows)" in model
    assert "todos los partidos de la etapa seleccionada" in html
    assert "solo se muestran hasta 40" not in html.lower()


def test_dashboard_exposes_only_the_three_requested_stages():
    script = (DASHBOARD / "app.js").read_text(encoding="utf-8")
    model = (DASHBOARD / "ui-model.mjs").read_text(encoding="utf-8")
    html = (DASHBOARD / "index.html").read_text(encoding="utf-8")

    assert 'pre_america: "Pre-América"' in script
    assert 'america_championship_context: "América campeón"' in script
    assert 'post_championship_context: "Post campeonatos"' in script
    assert "other_context:" not in script
    assert 'fillSelect("#stage-filter", stageKeys, stageNames)' in script
    assert "includedStages.has(row.stage)" in model
    assert "3 ETAPAS · ANÁLISIS LONGITUDINAL" in html
    assert "tres etapas: Pre-América, América campeón y post campeonatos" in script


def test_unique_players_keeps_the_most_complete_row_per_player():
    result = run_ui_model(
        'import { uniquePlayers } from "./dashboard/ui-model.mjs";'
        'const rows = [{player_id:"p1",player:"Ana",stage:"A",active_windows:2},'
        '{player_id:"p1",player:"Ana",stage:"B",active_windows:7},'
        '{player_id:"p2",player:"Bia",stage:"A",active_windows:3}];'
        'console.log(JSON.stringify(uniquePlayers(rows)));'
    )

    assert [(row["player_id"], row["stage"]) for row in result] == [("p1", "B"), ("p2", "A")]


def test_pass_network_preserves_direction_and_aggregates_match_counts():
    result = run_ui_model(
        'import fs from "node:fs";'
        'import { aggregatePlayerPassConnections } from "./dashboard/ui-model.mjs";'
        'const report = JSON.parse(fs.readFileSync("./dashboard/report_data.json","utf8"));'
        'const rows = report.pass_network.filter(row => row.stage === "america_championship_context");'
        'const links = aggregatePlayerPassConnections(rows,"Luis Ángel Malagón Velázquez");'
        'console.log(JSON.stringify(links.find(row => row.name === "Julián Andrés Quiñones Quiñones")));'
    )

    assert result == {
        "name": "Julián Andrés Quiñones Quiñones",
        "outgoing": 97,
        "incoming": 3,
        "outgoingMatches": 30,
        "incomingMatches": 3,
    }


def test_dashboard_translates_raw_stage_names_and_avoids_statistical_shorthand():
    script = (DASHBOARD / "app.js").read_text(encoding="utf-8")

    assert '|| "Etapa no disponible"' in script
    assert "n=${" not in script
    assert "partidos${sampleHint}" in script
    assert "La barra muestra el rango central" in (DASHBOARD / "index.html").read_text(encoding="utf-8")


def test_player_positions_are_shown_in_spanish():
    script = (DASHBOARD / "app.js").read_text(encoding="utf-8")

    assert '"Center Attacking Midfield": "Mediocampista ofensivo central"' in script
    assert '"Left Center Back": "Defensa central izquierdo"' in script
    assert '"Right Wing Back": "Carrilero derecho"' in script
    assert "positionNames[player.position]" in script


def test_dashboard_preserves_editorial_visual_treatment():
    styles = (DASHBOARD / "styles.css").read_text(encoding="utf-8")
    html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
    script = (DASHBOARD / "app.js").read_text(encoding="utf-8")

    assert "--lime: #d8f06b" in styles
    assert ".hero-wrap" in styles
    assert ".bar-chart" in styles
    assert ".pitch" in styles
    assert ".map-controls" in styles
    assert ".network-arrowhead" in styles
    assert "marker-end=\"url(#network-arrowhead)\"" in script
    assert "Pases hacia" in script
    assert "Pases recibidos de" in script
    assert 'escapeHtml(node.name)}</text>' in script
    assert 'escapeHtml(centerName)}</text>' in script
    assert 'node.name.split(" ").slice(-1)' not in script
    assert ".network-center .network-center-name" in styles
    assert "promedio por partido" in html
    assert ".context-grid.lower-visuals > *" in styles
    assert 'src="assets/possession-rhythm.svg"' in html
    assert 'src="assets/match-evidence.svg"' in html
    assert "enableSvgNavigation" in script
    assert "data-zoom-in" in script
    assert 'addEventListener("pointermove"' in script
    assert 'addEventListener("wheel"' in script
    assert 'addEventListener("dblclick"' in script
    assert 'id="scope-description" class="section-lede loading"' in html
    assert 'x ≥ 60' in html
    assert "@media (max-width: 520px)" in styles


def test_dashboard_illustrations_are_local_svg_assets():
    for filename in ("possession-rhythm.svg", "match-evidence.svg"):
        asset = DASHBOARD / "assets" / filename
        assert asset.is_file(), filename
        assert asset.read_text(encoding="utf-8").lstrip().startswith("<svg")


def test_distribution_contains_the_same_dashboard_and_generated_data():
    for filename in ("app.js", "styles.css", "ui-model.mjs", "report_data.json"):
        assert (ROOT / "dist" / filename).is_file(), filename
    for filename in ("app.js", "styles.css", "ui-model.mjs", "report_data.json"):
        assert (DASHBOARD / filename).read_bytes() == (ROOT / "dist" / filename).read_bytes()
    for filename in ("possession-rhythm.svg", "match-evidence.svg"):
        assert (DASHBOARD / "assets" / filename).read_bytes() == (ROOT / "dist" / "assets" / filename).read_bytes()


def test_distribution_index_is_a_self_contained_offline_dashboard():
    html = (ROOT / "dist" / "index.html").read_text(encoding="utf-8")
    payload = re.search(
        r'<script type="application/json" id="report-data">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    inline_script = re.search(r"<script>\n(.*?)\n</script>", html, flags=re.DOTALL)
    assert payload
    assert inline_script
    report = json.loads(payload.group(1))

    assert report["metadata"]["match_count"] == 183
    assert len(report["pass_network"]) > 0
    assert "<style>" in html
    assert "<script>\n" in html
    assert "data:image/svg+xml;base64," in html
    assert '<link rel="stylesheet" href="styles.css">' not in html
    assert 'src="app.js"' not in html
    assert 'src="assets/' not in html
    assert 'fetch("./report_data.json")' not in html
    assert "fetch(" not in inline_script.group(1)
    assert not re.search(r'<(?:script|link|img)[^>]+(?:src|href)="(?!#|data:)', html)
    result = subprocess.run(
        ["node", "--check", "--input-type=commonjs"],
        input=inline_script.group(1),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


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


def test_all_stage_filters_exclude_other_context():
    result = run_ui_model(
        'import { filterPlayerActivity } from "./dashboard/ui-model.mjs";'
        'const rows = ["pre_america","america_championship_context","post_championship_context","other_context"]'
        '.map(stage=>({team:"América",stage,player_id:stage}));'
        'console.log(JSON.stringify(filterPlayerActivity(rows,"all","all","all").map(row=>row.stage)));'
    )

    assert result == [
        "pre_america",
        "america_championship_context",
        "post_championship_context",
    ]
