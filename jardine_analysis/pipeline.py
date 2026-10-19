from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd


AMERICA = "América"
ATLETICO_SAN_LUIS = "Atlético San Luis"
HIGH_X = 80.0
PPDA_X_LIMIT = 72.0
STAGE_RULES = {
    "pre_america": {
        "rule": "Focal team is Atlético de San Luis in the match identifier.",
        "period": "Available 2022-2023 context in the database",
        "confidence": "contextual",
    },
    "america_championship_context": {
        "rule": "Focal team is América and match year is 2024 or earlier.",
        "period": "Available América context through 2024",
        "confidence": "contextual",
    },
    "post_championship_context": {
        "rule": "Focal team is América and match year is after 2024.",
        "period": "Available América context after 2024",
        "confidence": "contextual",
    },
}


def _match_year(match_id: str) -> int:
    match = re.search(r"_(\d{4})-\d{2}-\d{2}$", match_id)
    if not match:
        raise ValueError(f"Invalid match id date: {match_id}")
    return int(match.group(1))


def classify_stage(match_id: str) -> str:
    """Assign a conservative narrative stage from the match identifier."""
    year = _match_year(match_id)
    if match_id.startswith("AtleticoSanLuis_"):
        return "pre_america"
    if match_id.startswith("America_") or (
        "_vs_America_" in match_id and not match_id.startswith("AtleticoSanLuis_")
    ):
        if year <= 2024:
            return "america_championship_context"
        return "post_championship_context"
    if "_vs_AtleticoSanLuis_" in match_id:
        return "pre_america"
    return "other_context"


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _empty_metric(value: int | float | None = None) -> int | float | None:
    return value


def compute_ppda(
    passes: pd.DataFrame,
    defensive_actions: pd.DataFrame,
    team: str,
    opponent: str | None = None,
    *,
    x_limit: float = PPDA_X_LIMIT,
) -> dict[str, int | float | None]:
    """Compute PPDA as opponent passes divided by team defensive actions.

    The dataset does not expose a normalized attacking direction, so this
    first version uses the raw x-coordinate and records the spatial cutoff.
    """
    pass_mask = passes["equipo"].ne(team) & passes["x_inicio"].le(x_limit)
    if opponent is not None:
        pass_mask &= passes["equipo"].eq(opponent)
    action_mask = defensive_actions["equipo"].eq(team) & defensive_actions["x"].le(x_limit)
    opponent_passes = int(pass_mask.sum())
    defensive_count = int(action_mask.sum())
    ppda = None if defensive_count == 0 else opponent_passes / defensive_count
    return {
        "opponent_passes": opponent_passes,
        "defensive_actions": defensive_count,
        "ppda": ppda,
    }


def compute_match_metrics(
    *,
    match_id: str,
    team: str,
    passes: pd.DataFrame,
    defensive: pd.DataFrame,
    shots: pd.DataFrame,
    opponent: str | None = None,
) -> dict[str, Any]:
    team_passes = passes[passes["equipo"].eq(team)].copy()
    team_defensive = defensive[defensive["equipo"].eq(team)].copy()
    team_shots = shots[shots["equipo"].eq(team)].copy()

    ppda = compute_ppda(passes, defensive, team, opponent)
    pressure_mask = team_defensive["tipo_accion"].eq("Pressure")
    recovery_mask = team_defensive["tipo_accion"].eq("Ball Recovery")
    high_mask = team_defensive["zona"].eq("ATTACKING_THIRD")
    goals = team_shots["tipo_gol_o_remate"].eq("Goal")

    return {
        "match_id": match_id,
        "team": team,
        "stage": classify_stage(match_id),
        "passes": int(len(team_passes)),
        "progressive_passes": int(_numeric(team_passes["progresivo"]).sum()),
        "key_passes": int(_numeric(team_passes["pase_clave"]).sum()),
        "defensive_actions": int(len(team_defensive)),
        "pressures": int(pressure_mask.sum()),
        "high_pressures": int((pressure_mask & high_mask).sum()),
        "recoveries": int(recovery_mask.sum()),
        "high_recoveries": int((recovery_mask & high_mask).sum()),
        "shots": int(len(team_shots)),
        "goals": int(goals.sum()),
        "xg": round(float(_numeric(team_shots["xg"]).sum()), 6),
        "opponent_passes": ppda["opponent_passes"],
        "ppda_actions": ppda["defensive_actions"],
        "ppda": ppda["ppda"],
    }


def _team_for_match(match_id: str) -> str | None:
    if match_id.startswith("America_") or (
        "_vs_America_" in match_id and not match_id.startswith("AtleticoSanLuis_")
    ):
        return AMERICA
    if match_id.startswith("AtleticoSanLuis_") or "_vs_AtleticoSanLuis_" in match_id:
        return ATLETICO_SAN_LUIS
    return None


def _opponent_for_match(
    match_id: str,
    team: str,
    available_teams: set[str] | None = None,
) -> str | None:
    if available_teams:
        alternatives = available_teams - {team}
        if len(alternatives) == 1:
            return next(iter(alternatives))
    parts = match_id.split("_vs_")
    if len(parts) != 2:
        return None
    opponent = parts[1].rsplit("_", 1)[0]
    if team == AMERICA and opponent == "AtleticoSanLuis":
        return ATLETICO_SAN_LUIS
    if team == ATLETICO_SAN_LUIS and opponent == "America":
        return AMERICA
    return opponent


def count_formation_changes(formations: pd.DataFrame) -> pd.DataFrame:
    """Count actual formation changes, ignoring repeated snapshots."""
    if formations.empty:
        return pd.DataFrame(
            columns=[
                "id_partido",
                "formation_change_events",
                "matches_with_formation_change",
            ]
        )
    ordered = formations.sort_values(["id_partido", "minuto", "segundo"]).copy()
    ordered["previous_formation"] = ordered.groupby("id_partido")["formacion"].shift()
    changes = ordered[
        ordered["minuto"].gt(0)
        & ordered["formacion"].ne(ordered["previous_formation"])
    ]
    return (
        changes.groupby("id_partido", as_index=False)
        .size()
        .rename(
            columns={
                "size": "formation_change_events",
            }
        )
        .assign(matches_with_formation_change=1)
    )


def run_pipeline(database: str | Path, output_dir: str | Path) -> pd.DataFrame:
    """Read the SQLite dataset and export match, stage, and action summaries."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        matches = pd.read_sql_query(
            "SELECT id_partido, rival FROM partidos ORDER BY id_partido",
            connection,
        )
        selected = matches[matches["id_partido"].map(_team_for_match).notna()].copy()
        passes = pd.read_sql_query(
            "SELECT id_partido, equipo, x_inicio, progresivo, pase_clave FROM pases",
            connection,
        )
        defensive = pd.read_sql_query(
            "SELECT id_partido, equipo, x, zona, tipo_accion FROM acciones_defensivas",
            connection,
        )
        shots = pd.read_sql_query(
            "SELECT id_partido, equipo, xg, tipo_gol_o_remate FROM remates",
            connection,
        )
        formations = pd.read_sql_query(
            "SELECT id_partido, equipo, minuto, segundo, formacion "
            "FROM formaciones_tacticas",
            connection,
        )
        match_state = pd.read_sql_query(
            "SELECT id_partido, event_index, minuto, equipo, estado, diferencia_goles "
            "FROM estado_partido",
            connection,
        )
        transitions = pd.read_sql_query(
            "SELECT id_partido, equipo, zona_recuperacion, segundos_hasta_tiro, "
            "xg_generado, hubo_tiro, hubo_gol FROM transiciones",
            connection,
        )
        decisions = pd.read_sql_query(
            "SELECT id_partido, minuto, equipo, tipo FROM disciplina_sustituciones",
            connection,
        )

    rows: list[dict[str, Any]] = []
    for match_id in selected["id_partido"]:
        team = _team_for_match(match_id)
        assert team is not None
        rows.append(
            compute_match_metrics(
                match_id=match_id,
                team=team,
                opponent=_opponent_for_match(
                    match_id,
                    team,
                    set(passes.loc[passes["id_partido"].eq(match_id), "equipo"]),
                ),
                passes=passes[passes["id_partido"].eq(match_id)],
                defensive=defensive[defensive["id_partido"].eq(match_id)],
                shots=shots[shots["id_partido"].eq(match_id)],
            )
        )

    match_metrics = pd.DataFrame(rows)
    focal_state = match_state[
        match_state["id_partido"].isin(match_metrics["match_id"])
        & match_state.apply(
            lambda row: _team_for_match(row["id_partido"]) == row["equipo"],
            axis=1,
        )
    ].copy()
    if not focal_state.empty:
        final_state = (
            focal_state.sort_values(["id_partido", "event_index"])
            .drop_duplicates("id_partido", keep="last")
            .rename(
                columns={
                    "estado": "final_state",
                    "diferencia_goles": "final_goal_difference",
                }
            )[["id_partido", "final_state", "final_goal_difference"]]
        )
        match_metrics = match_metrics.merge(
            final_state,
            left_on="match_id",
            right_on="id_partido",
            how="left",
        ).drop(columns="id_partido")
    match_metrics.to_csv(output_path / "match_metrics.csv", index=False)
    match_metrics.to_json(
        output_path / "match_metrics.json",
        orient="records",
        indent=2,
        force_ascii=False,
    )
    (output_path / "stage_rules.json").write_text(
        json.dumps(
            {
                "rules": STAGE_RULES,
                "limitations": [
                    "partidos.competencia and partidos.fecha are empty in the source database",
                    "stage labels are contextual and do not independently prove tournament membership",
                    "coordinate direction is not normalized; PPDA uses raw x <= 72 while high actions use the source ATTACKING_THIRD zone",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    stage_summary = (
        match_metrics.groupby(["stage", "team"], as_index=False)
        .agg(
            matches=("match_id", "nunique"),
            passes=("passes", "mean"),
            progressive_passes=("progressive_passes", "mean"),
            pressures=("pressures", "mean"),
            high_pressures=("high_pressures", "mean"),
            recoveries=("recoveries", "mean"),
            high_recoveries=("high_recoveries", "mean"),
            shots=("shots", "mean"),
            goals=("goals", "mean"),
            xg=("xg", "mean"),
            ppda=("ppda", "mean"),
        )
    )
    stage_summary.to_csv(output_path / "stage_summary.csv", index=False)
    focal_formations = formations[
        formations["id_partido"].isin(match_metrics["match_id"])
        & formations.apply(
            lambda row: _team_for_match(row["id_partido"]) == row["equipo"],
            axis=1,
        )
    ].copy()
    if not focal_formations.empty:
        initial_formations = (
            focal_formations.sort_values(["id_partido", "minuto", "segundo"])
            .drop_duplicates("id_partido", keep="first")
            .assign(
                team=lambda frame: frame["id_partido"].map(
                    lambda match_id: _team_for_match(match_id)
                ),
                stage=lambda frame: frame["id_partido"].map(classify_stage),
            )
        )
        formation_summary = (
            initial_formations.groupby(["stage", "team", "formacion"], as_index=False)
            .agg(matches=("id_partido", "nunique"))
            .sort_values(["stage", "matches"], ascending=[True, False])
        )
    else:
        formation_summary = pd.DataFrame(
            columns=["stage", "team", "formacion", "matches"]
        )
    formation_summary.to_csv(output_path / "formation_summary.csv", index=False)
    if not focal_state.empty:
        context_summary = (
            focal_state.assign(
                team=lambda frame: frame["id_partido"].map(
                    lambda match_id: _team_for_match(match_id)
                ),
                stage=lambda frame: frame["id_partido"].map(classify_stage),
            )
            .groupby(["stage", "team", "estado"], as_index=False)
            .agg(
                matches=("id_partido", "nunique"),
                event_rows=("id_partido", "size"),
                average_goal_difference=("diferencia_goles", "mean"),
            )
        )
    else:
        context_summary = pd.DataFrame(
            columns=[
                "stage",
                "team",
                "estado",
                "matches",
                "event_rows",
                "average_goal_difference",
            ]
        )
    context_summary.to_csv(output_path / "context_summary.csv", index=False)
    focal_transitions = transitions[
        transitions["id_partido"].isin(match_metrics["match_id"])
        & transitions.apply(
            lambda row: _team_for_match(row["id_partido"]) == row["equipo"],
            axis=1,
        )
    ].copy()
    if not focal_transitions.empty:
        transition_summary = (
            focal_transitions.assign(
                team=lambda frame: frame["id_partido"].map(
                    lambda match_id: _team_for_match(match_id)
                ),
                stage=lambda frame: frame["id_partido"].map(classify_stage),
            )
            .groupby(["stage", "team", "zona_recuperacion"], as_index=False)
            .agg(
                transitions=("id_partido", "size"),
                matches=("id_partido", "nunique"),
                shots=("hubo_tiro", "sum"),
                goals=("hubo_gol", "sum"),
                xg_generated=("xg_generado", "sum"),
                average_seconds_to_shot=("segundos_hasta_tiro", "mean"),
            )
        )
    else:
        transition_summary = pd.DataFrame(
            columns=[
                "stage",
                "team",
                "zona_recuperacion",
                "transitions",
                "matches",
                "shots",
                "goals",
                "xg_generated",
                "average_seconds_to_shot",
            ]
        )
    transition_summary.to_csv(output_path / "transition_summary.csv", index=False)
    focal_decisions = decisions[
        decisions["id_partido"].isin(match_metrics["match_id"])
        & decisions.apply(
            lambda row: _team_for_match(row["id_partido"]) == row["equipo"],
            axis=1,
        )
    ].copy()
    focal_decisions = focal_decisions[focal_decisions["tipo"].eq("Substitution")]
    decision_rows = count_formation_changes(focal_formations)
    if not focal_decisions.empty or not decision_rows.empty:
        substitution_summary = (
            focal_decisions.assign(
                team=lambda frame: frame["id_partido"].map(
                    lambda match_id: _team_for_match(match_id)
                ),
                stage=lambda frame: frame["id_partido"].map(classify_stage),
            )
            .groupby(["stage", "team"], as_index=False)
            .agg(
                substitution_events=("id_partido", "size"),
                matches_with_substitution=("id_partido", "nunique"),
                average_substitution_minute=("minuto", "mean"),
            )
        )
        formation_changes = decision_rows.assign(
            team=lambda frame: frame["id_partido"].map(
                lambda match_id: _team_for_match(match_id)
            ),
            stage=lambda frame: frame["id_partido"].map(classify_stage),
        ).groupby(["stage", "team"], as_index=False).agg(
            formation_change_events=("formation_change_events", "sum"),
            matches_with_formation_change=("matches_with_formation_change", "sum"),
        )
        decision_summary = substitution_summary.merge(
            formation_changes,
            on=["stage", "team"],
            how="outer",
        ).fillna(0)
    else:
        decision_summary = pd.DataFrame(
            columns=[
                "stage",
                "team",
                "substitution_events",
                "matches_with_substitution",
                "average_substitution_minute",
                "formation_change_events",
                "matches_with_formation_change",
            ]
        )
    decision_summary.to_csv(output_path / "decision_summary.csv", index=False)
    key_actions = match_metrics[
        [
            "match_id",
            "team",
            "stage",
            "high_pressures",
            "high_recoveries",
            "xg",
            "goals",
        ]
    ].sort_values(["high_recoveries", "xg"], ascending=False)
    key_actions.head(25).to_csv(output_path / "key_actions.csv", index=False)
    return match_metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="hackathon.db")
    parser.add_argument("--output-dir", default="outputs")
    args = parser.parse_args()
    result = run_pipeline(args.database, args.output_dir)
    print(f"Exported {len(result)} match summaries to {args.output_dir}")


if __name__ == "__main__":
    main()
