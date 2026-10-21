import pandas as pd
import sqlite3
import json

from jardine_analysis.pipeline import (
    _opponent_for_match,
    count_formation_changes,
    classify_stage,
    compute_match_metrics,
    compute_ppda,
    run_pipeline,
)


def test_opponent_for_match_uses_the_non_focal_canonical_team():
    assert _opponent_for_match(
        "Pachuca_vs_America_2024-02-18",
        "América",
        {"América", "Pachuca"},
    ) == "Pachuca"


def test_count_formation_changes_ignores_repeated_snapshots():
    formations = pd.DataFrame(
        [
            {"id_partido": "m1", "minuto": 0, "segundo": 0, "formacion": "4231"},
            {"id_partido": "m1", "minuto": 45, "segundo": 0, "formacion": "4231"},
            {"id_partido": "m1", "minuto": 70, "segundo": 0, "formacion": "343"},
        ]
    )

    result = count_formation_changes(formations)

    assert len(result) == 1
    assert result.iloc[0]["formation_change_events"] == 1


def test_classify_stage_uses_team_and_date_boundaries():
    assert classify_stage("AtleticoSanLuis_vs_Puebla_2023-05-14") == "pre_america"
    assert classify_stage("AtleticoSanLuis_vs_America_2023-05-14") == "pre_america"
    assert classify_stage("AtleticoSanLuis_vs_Puebla_2024-05-14") == "other_context"
    assert classify_stage("AtleticoSanLuis_vs_America_2025-09-25") == "other_context"
    assert classify_stage("America_vs_AtleticoSanLuis_2023-12-10") == "america_championship_context"
    assert classify_stage("Puebla_vs_AtleticoSanLuis_2023-05-14") == "pre_america"
    assert classify_stage("America_vs_CruzAzul_2024-12-15") == "america_championship_context"
    assert classify_stage("America_vs_Toluca_2025-03-01") == "post_championship_context"


def test_compute_ppda_counts_opponent_passes_over_defensive_actions():
    passes = pd.DataFrame(
        [
            {"equipo": "Rival", "x_inicio": 20},
            {"equipo": "Rival", "x_inicio": 71},
            {"equipo": "Rival", "x_inicio": 80},
            {"equipo": "América", "x_inicio": 30},
        ]
    )
    defensive = pd.DataFrame(
        [
            {"equipo": "América", "x": 30, "tipo_accion": "Pressure"},
            {"equipo": "América", "x": 70, "tipo_accion": "Interception"},
        ]
    )

    result = compute_ppda(passes, defensive, "América", "Rival", x_limit=72)

    assert result == {
        "opponent_passes": 2,
        "defensive_actions": 2,
        "ppda": 1.0,
    }


def test_compute_match_metrics_returns_normalized_tactical_summary():
    passes = pd.DataFrame(
        [
            {"equipo": "América", "x_inicio": 20, "x_fin": 40, "progresivo": 1, "pase_clave": 0},
            {"equipo": "América", "x_inicio": 40, "x_fin": 70, "progresivo": 1, "pase_clave": 1},
            {"equipo": "Rival", "x_inicio": 10, "x_fin": 20, "progresivo": 0, "pase_clave": 0},
        ]
    )
    defensive = pd.DataFrame(
        [
            {"equipo": "América", "x": 85, "zona": "ATTACKING_THIRD", "tipo_accion": "Pressure"},
            {"equipo": "América", "x": 65, "zona": "MIDDLE_THIRD", "tipo_accion": "Ball Recovery"},
        ]
    )
    shots = pd.DataFrame(
        [
            {"equipo": "América", "xg": 0.4, "tipo_gol_o_remate": "Goal"},
            {"equipo": "América", "xg": 0.1, "tipo_gol_o_remate": "Saved to Post"},
        ]
    )

    result = compute_match_metrics(
        match_id="America_vs_Rival_2024-12-15",
        team="América",
        passes=passes,
        defensive=defensive,
        shots=shots,
    )

    assert result["passes"] == 2
    assert result["progressive_passes"] == 2
    assert result["shots"] == 2
    assert result["goals"] == 1
    assert result["xg"] == 0.5
    assert result["high_pressures"] == 1
    assert result["recoveries"] == 1


def test_run_pipeline_exports_report_data(tmp_path):
    database = tmp_path / "sample.db"
    output_dir = tmp_path / "outputs"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE partidos (id_partido TEXT, rival TEXT, fecha TEXT, estadio TEXT, competencia TEXT);
        CREATE TABLE pases (
            id_evento TEXT, id_partido TEXT, possession_id INTEGER, equipo TEXT,
            jugador TEXT, receptor TEXT, resultado TEXT, x_inicio REAL, y_inicio REAL,
            x_fin REAL, y_fin REAL, longitud REAL, angulo REAL, progresivo INTEGER,
            shot_assist INTEGER, goal_assist INTEGER, assisted_shot_id TEXT,
            pase_clave INTEGER, cross INTEGER, cut_back INTEGER, through_ball INTEGER,
            switch_pass INTEGER
        );
        CREATE TABLE acciones_defensivas (
            id_evento TEXT, id_partido TEXT, equipo TEXT, jugador TEXT, tipo_accion TEXT,
            resultado TEXT, x REAL, y REAL, zona TEXT, exitosa INTEGER, counterpress INTEGER,
            penalty_box INTEGER, defensive_third INTEGER
        );
        CREATE TABLE remates (
            id_remate TEXT, id_partido TEXT, equipo TEXT, jugador TEXT, minuto INTEGER,
            segundo INTEGER, tipo_gol_o_remate TEXT, xg REAL, carril_creacion TEXT,
            tecnica TEXT, cuerpo_parte TEXT, possession_id INTEGER, key_pass_id TEXT
        );
        CREATE TABLE formaciones_tacticas (
            id_cambio TEXT, id_partido TEXT, equipo TEXT, minuto INTEGER,
            segundo INTEGER, formacion TEXT, alineacion_json TEXT
        );
        CREATE TABLE estado_partido (
            id_partido TEXT, event_index INTEGER, minuto REAL, equipo TEXT,
            marcador_equipo INTEGER, marcador_rival INTEGER, diferencia_goles INTEGER,
            estado TEXT, jugadores_activos INTEGER, rival_jugadores_activos INTEGER
        );
        CREATE TABLE transiciones (
            id_partido TEXT, id_recuperacion TEXT, equipo TEXT, zona_recuperacion TEXT,
            possession_id INTEGER, segundos_hasta_tiro REAL, eventos_hasta_tiro INTEGER,
            pases_hasta_tiro INTEGER, xg_generado REAL, hubo_tiro INTEGER, hubo_gol INTEGER
        );
        CREATE TABLE disciplina_sustituciones (
            id_evento TEXT, id_partido TEXT, minuto INTEGER, segundo INTEGER,
            equipo TEXT, jugador TEXT, tipo TEXT, jugador_reemplazo TEXT,
            tarjeta TEXT, razon TEXT
        );
        CREATE TABLE eventos (
            id_evento TEXT, id_partido TEXT, event_index INTEGER, equipo TEXT,
            tipo_evento TEXT, jugador TEXT, jugador_id TEXT, x_inicio REAL,
            y_inicio REAL, possession_id INTEGER, possession_team TEXT,
            patron_juego TEXT
        );
        CREATE TABLE posesiones (
            id_partido TEXT, possession_id INTEGER, possession_team TEXT,
            duracion REAL, eventos INTEGER, pases INTEGER, conducciones INTEGER,
            tiros INTEGER, recuperacion_alta INTEGER
        );
        CREATE TABLE jugadores_partido (
            id_partido TEXT, equipo TEXT, jugador_id TEXT, posicion TEXT
        );
        CREATE TABLE features_jugador_ventana (
            id_partido TEXT, equipo TEXT, jugador_id TEXT, jugador TEXT, periodo INTEGER,
            ventana_minuto INTEGER, minutos_activos INTEGER, pases INTEGER,
            pases_progresivos INTEGER, conducciones INTEGER, xa REAL, xg REAL,
            presiones INTEGER, recuperaciones INTEGER, perdidas INTEGER,
            duelos_ganados INTEGER, estado_partido TEXT
        );
        INSERT INTO partidos VALUES ('America_vs_Rival_2024-12-15', 'Rival', NULL, NULL, NULL);
        INSERT INTO pases VALUES ('p1', 'America_vs_Rival_2024-12-15', 1, 'América', 'A', 'B', 'Complete', 20, 20, 40, 20, 20, 0, 1, 0, 0, NULL, 0, 0, 0, 0, 0);
        INSERT INTO pases VALUES ('p2', 'America_vs_Rival_2024-12-15', 1, 'Rival', NULL, NULL, NULL, 20, 20, 40, 20, 20, 0, 0, 0, 0, NULL, 0, 0, 0, 0, 0);
        INSERT INTO pases VALUES ('p3', 'America_vs_Rival_2024-12-15', 1, 'América', 'A', NULL, 'Incomplete', 25, 25, NULL, NULL, NULL, NULL, 0, 0, 0, NULL, 0, 0, 0, 0, 0);
        INSERT INTO acciones_defensivas VALUES ('d1', 'America_vs_Rival_2024-12-15', 'América', NULL, 'Pressure', NULL, 85, 20, 'ATTACKING_THIRD', 0, 0, 0, 0);
        INSERT INTO remates VALUES ('s1', 'America_vs_Rival_2024-12-15', 'América', NULL, 1, 1, 'Goal', 0.5, NULL, NULL, NULL, 1, NULL);
        INSERT INTO eventos VALUES ('s1', 'America_vs_Rival_2024-12-15', 1, 'América', 'Shot', 'A', 'a1', 100, 20, 1, 'América', 'From Corner');
        INSERT INTO eventos VALUES ('s2', 'America_vs_Rival_2024-12-15', 2, 'América', 'Shot', 'A', 'a1', 90, 30, 2, 'América', NULL);
        INSERT INTO posesiones VALUES ('America_vs_Rival_2024-12-15', 1, 'América', 10, 2, 1, 0, 1, 0);
        INSERT INTO jugadores_partido VALUES ('America_vs_Rival_2024-12-15', 'América', 'a1', 'Center Midfield');
        INSERT INTO jugadores_partido VALUES ('America_vs_Rival_2024-12-15', 'América', 'b1', 'Center Forward');
        INSERT INTO features_jugador_ventana VALUES ('America_vs_Rival_2024-12-15', 'América', 'a1', 'A', 1, 0, 5, 1, 1, 0, 0.1, 0.1, 1, 0, 0, 0, 'empatando');
        INSERT INTO formaciones_tacticas VALUES ('f1', 'America_vs_Rival_2024-12-15', 'América', 0, 0, '4231', '[]');
        INSERT INTO estado_partido VALUES ('America_vs_Rival_2024-12-15', 1, 0, 'América', 0, 0, 0, 'empatando', 11, 11);
        INSERT INTO transiciones VALUES ('America_vs_Rival_2024-12-15', 'r1', 'América', 'ATTACKING_THIRD', 1, 5, 2, 1, 0.2, 1, 0);
        INSERT INTO disciplina_sustituciones VALUES ('sub1', 'America_vs_Rival_2024-12-15', 70, 0, 'América', 'A', 'Substitution', 'B', NULL, NULL);
        """
    )
    connection.commit()
    connection.close()

    run_pipeline(database, output_dir)

    assert (output_dir / "match_metrics.csv").exists()
    assert (output_dir / "match_metrics.json").exists()
    assert (output_dir / "stage_rules.json").exists()
    assert (output_dir / "formation_summary.csv").exists()
    assert (output_dir / "context_summary.csv").exists()
    assert (output_dir / "transition_summary.csv").exists()
    assert (output_dir / "decision_summary.csv").exists()
    report = json.loads((output_dir / "report_data.json").read_text(encoding="utf-8"))
    assert report["metadata"]["match_count"] == 1
    assert report["metadata"]["definitions"]["possession"].startswith("Tramo continuo")
    assert "recuperación" in report["metadata"]["definitions"]["transition"]
    assert "no se calcula" in report["metadata"]["limitations"][2]
    assert report["opponent_summary"][0]["opponent"] == "Rival"
    assert report["opponent_summary"][0]["matches"] == 1
    assert report["venue_summary"][0]["venue"] == "home"
    assert report["venue_summary"][0]["matches"] == 1
    assert report["score_state_summary"] == [
        {
            "stage": "america_championship_context",
            "team": "América",
            "score_state": "empatando",
            "matches": 1,
            "active_windows": 1,
            "passes": 1,
            "progressive_passes": 1,
            "carries": 0,
            "xa": 0.1,
            "xg": 0.1,
            "pressures": 1,
            "recoveries": 0,
            "losses": 0,
            "duels_won": 0,
        }
    ]
    assert report["player_summary"][0]["player"] == "A"
    assert report["player_summary"][0]["position"] == "Center Midfield"
    assert report["player_summary"][0]["active_windows"] == 1
    assert {
        (row["player_id"], row["grid_x"], row["grid_y"], row["events"])
        for row in report["player_activity_map"]
    } == {("a1", 9, 3, 1), ("a1", 10, 2, 1)}
    assert report["pass_network"] == [
        {
            "match_id": "America_vs_Rival_2024-12-15",
            "team": "América",
            "stage": "america_championship_context",
            "opponent": "Rival",
            "venue": "home",
            "player": "A",
            "receiver": "B",
            "passes": 1,
        }
    ]
    assert len(report["shot_map"]) == 1
    assert report["shot_map"][0]["pattern"] == "From Corner"
    assert report["shot_map"][0]["x"] == 100
    assert report["set_piece_summary"][0]["possessions"] == 1
    assert report["set_piece_summary"][0]["shots"] == 1
    assert "focal_defensive_actions" not in report["set_piece_summary"][0]

    with sqlite3.connect(database) as connection:
        connection.executescript(
            "DELETE FROM pases; DELETE FROM eventos; DELETE FROM posesiones; "
            "DELETE FROM jugadores_partido; DELETE FROM features_jugador_ventana;"
        )
    run_pipeline(database, output_dir)
    sparse_report = json.loads(
        (output_dir / "report_data.json").read_text(encoding="utf-8")
    )
    assert sparse_report["metadata"]["match_count"] == 1
    assert sparse_report["opponent_summary"]
    assert sparse_report["venue_summary"]
    assert sparse_report["score_state_summary"] == []
    assert sparse_report["player_summary"] == []
    assert sparse_report["player_activity_map"] == []
    assert sparse_report["pass_network"] == []
    assert sparse_report["shot_map"] == []
    assert sparse_report["possession_summary"] == []
    assert sparse_report["set_piece_summary"] == []
