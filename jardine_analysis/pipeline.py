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
        "rule": "Focal team is Atlético de San Luis and the match ID year is 2022 or 2023.",
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
    "other_context": {
        "rule": "The focal team or match ID year does not match the contextual stages above.",
        "period": "Excluded from the three focal narrative stages",
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
        return "pre_america" if year <= 2023 else "other_context"
    if match_id.startswith("America_") or (
        "_vs_America_" in match_id and not match_id.startswith("AtleticoSanLuis_")
    ):
        if year <= 2024:
            return "america_championship_context"
        return "post_championship_context"
    if "_vs_AtleticoSanLuis_" in match_id:
        return "pre_america" if year <= 2023 else "other_context"
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


def _venue_for_match(match_id: str, team: str) -> str:
    parts = match_id.split("_vs_")
    if len(parts) != 2:
        return "unknown"
    focal_token = {
        AMERICA: "America",
        ATLETICO_SAN_LUIS: "AtleticoSanLuis",
    }.get(team)
    if focal_token is None:
        return "unknown"
    home_team = parts[0]
    away_team = parts[1].rsplit("_", 1)[0]
    if home_team == focal_token:
        return "home"
    if away_team == focal_token:
        return "away"
    return "unknown"


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


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(frame.to_json(orient="records", force_ascii=False))


def compute_progression_profile(passes: pd.DataFrame, team: str) -> pd.DataFrame:
    """Summarize observable progression by source zone and lateral lane."""
    team_passes = passes[passes["equipo"].eq(team)].copy()
    if team_passes.empty:
        return pd.DataFrame(
            columns=["zone", "lane", "passes", "progressive_passes", "key_passes"]
        )
    team_passes["zone"] = pd.cut(
        pd.to_numeric(team_passes["x_inicio"], errors="coerce"),
        bins=[-1, 40, 80, 121],
        labels=["0-40", "40-80", "80-120"],
    ).astype("object").fillna("unknown")
    team_passes["lane"] = pd.cut(
        pd.to_numeric(team_passes["y_inicio"], errors="coerce"),
        bins=[-1, 26.67, 53.33, 81],
        labels=["left", "center", "right"],
    ).astype("object").fillna("unknown")
    return (
        team_passes.groupby(["zone", "lane"], as_index=False, dropna=False)
        .agg(
            passes=("equipo", "size"),
            progressive_passes=("progresivo", lambda values: _numeric(values).sum()),
            key_passes=("pase_clave", lambda values: _numeric(values).sum()),
        )
    )


def compute_territorial_proxy(
    passes: pd.DataFrame, team: str, *, x_limit: float = 60
) -> dict[str, Any]:
    """Estimate territorial share without claiming directional Field Tilt."""
    valid = passes[pd.to_numeric(passes["x_inicio"], errors="coerce").notna()].copy()
    valid["x_inicio"] = pd.to_numeric(valid["x_inicio"], errors="coerce")
    spatial = valid[valid["x_inicio"].ge(x_limit)]
    focal = int((spatial["equipo"] == team).sum())
    opponent = int((spatial["equipo"] != team).sum())
    total = focal + opponent
    return {
        "team": team,
        "x_limit": x_limit,
        "spatial_events": total,
        "team_events": focal,
        "opponent_events": opponent,
        "proxy_share": None if total == 0 else focal / total,
        "proxy_label": "control territorial proxy; no es Field Tilt oficial",
    }


def compute_defensive_profile(defensive: pd.DataFrame, team: str) -> pd.DataFrame:
    """Count observable defensive actions by type and source zone."""
    focal = defensive[defensive["equipo"].eq(team)].copy()
    if focal.empty:
        return pd.DataFrame(columns=["action", "zone", "actions"])
    return (
        focal.assign(
            action=focal["tipo_accion"].fillna("unknown"),
            zone=focal["zona"].fillna("unknown"),
        )
        .groupby(["action", "zone"], as_index=False)
        .size()
        .rename(columns={"size": "actions"})
    )


def summarize_variability(match_metrics: pd.DataFrame) -> pd.DataFrame:
    """Report sample size and dispersion so stage averages retain context."""
    if match_metrics.empty:
        return pd.DataFrame(
            columns=["stage", "team", "matches", "metric", "mean", "std", "q1", "q3"]
        )
    metrics = [
        "passes", "progressive_passes", "pressures", "recoveries",
        "shots", "xg", "ppda",
    ]
    rows = []
    for (stage, team), group in match_metrics.groupby(["stage", "team"]):
        for metric in metrics:
            values = pd.to_numeric(group[metric], errors="coerce").dropna()
            rows.append({
                "stage": stage,
                "team": team,
                "matches": int(values.size),
                "metric": metric,
                "mean": None if values.empty else float(values.mean()),
                "std": None if values.size < 2 else float(values.std(ddof=1)),
                "q1": None if values.empty else float(values.quantile(0.25)),
                "q3": None if values.empty else float(values.quantile(0.75)),
            })
    return pd.DataFrame(rows)


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
            "SELECT id_evento, id_partido, possession_id, equipo, jugador, receptor, "
            "resultado, x_inicio, y_inicio, x_fin, y_fin, progresivo, pase_clave FROM pases",
            connection,
        )
        defensive = pd.read_sql_query(
            "SELECT id_partido, equipo, x, y, zona, tipo_accion "
            "FROM acciones_defensivas",
            connection,
        )
        shots = pd.read_sql_query(
            "SELECT id_remate, id_partido, possession_id, equipo, jugador, minuto, segundo, "
            "xg, tipo_gol_o_remate FROM remates",
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
        selected_ids = selected["id_partido"].tolist()
        placeholders = ",".join("?" for _ in selected_ids) or "NULL"
        events = pd.read_sql_query(
            "SELECT id_evento, id_partido, event_index, equipo, tipo_evento, jugador, "
            "jugador_id, x_inicio, y_inicio, possession_id, possession_team, patron_juego "
            f"FROM eventos WHERE id_partido IN ({placeholders})",
            connection,
            params=selected_ids,
        )
        possessions = pd.read_sql_query(
            "SELECT id_partido, possession_id, possession_team, duracion, eventos, pases, "
            "conducciones, tiros, recuperacion_alta FROM posesiones "
            f"WHERE id_partido IN ({placeholders})",
            connection,
            params=selected_ids,
        )
        player_features = pd.read_sql_query(
            "SELECT id_partido, equipo, jugador_id, jugador, periodo, ventana_minuto, "
            "minutos_activos, pases, pases_progresivos, conducciones, xa, xg, presiones, "
            "recuperaciones, perdidas, duelos_ganados, estado_partido "
            "FROM features_jugador_ventana "
            f"WHERE id_partido IN ({placeholders})",
            connection,
            params=selected_ids,
        )
        player_appearances = pd.read_sql_query(
            "SELECT id_partido, equipo, jugador_id, posicion FROM jugadores_partido "
            f"WHERE id_partido IN ({placeholders})",
            connection,
            params=selected_ids,
        )
    roster_team = (
        player_appearances.drop_duplicates(["id_partido", "jugador_id"])
        .rename(columns={"equipo": "roster_team"})
        [["id_partido", "jugador_id", "roster_team"]]
    )
    player_features = player_features.merge(
        roster_team,
        on=["id_partido", "jugador_id"],
        how="inner",
    )
    player_features = player_features[
        player_features["equipo"].eq(player_features["roster_team"])
    ].copy()
    rows: list[dict[str, Any]] = []
    for match_id in selected["id_partido"]:
        team = _team_for_match(match_id)
        assert team is not None
        opponent = _opponent_for_match(
            match_id,
            team,
            set(passes.loc[passes["id_partido"].eq(match_id), "equipo"]),
        )
        rows.append(
            {
                **compute_match_metrics(
                    match_id=match_id,
                    team=team,
                    opponent=opponent,
                    passes=passes[passes["id_partido"].eq(match_id)],
                    defensive=defensive[defensive["id_partido"].eq(match_id)],
                    shots=shots[shots["id_partido"].eq(match_id)],
                ),
                "opponent": opponent,
                "venue": _venue_for_match(match_id, team),
            }
        )

    match_metrics = pd.DataFrame(rows)
    variability_summary = summarize_variability(match_metrics)
    progression_rows = []
    defensive_rows = []
    territorial_rows = []
    for match_id in match_metrics["match_id"]:
        team = _team_for_match(match_id)
        assert team is not None
        match_passes = passes[passes["id_partido"].eq(match_id)]
        match_defensive = defensive[defensive["id_partido"].eq(match_id)]
        context_row = match_metrics.loc[
            match_metrics["match_id"].eq(match_id)
        ].iloc[0]
        progression = compute_progression_profile(match_passes, team)
        if not progression.empty:
            progression.insert(0, "match_id", match_id)
            progression.insert(1, "team", team)
            progression.insert(2, "stage", context_row["stage"])
            progression_rows.extend(progression.to_dict("records"))
        defensive_profile = compute_defensive_profile(match_defensive, team)
        if not defensive_profile.empty:
            defensive_profile.insert(0, "match_id", match_id)
            defensive_profile.insert(1, "team", team)
            defensive_profile.insert(2, "stage", context_row["stage"])
            defensive_rows.extend(defensive_profile.to_dict("records"))
        territorial_rows.append(
            {
                "match_id": match_id,
                "team": team,
                "stage": context_row["stage"],
                **compute_territorial_proxy(match_passes, team),
            }
        )
    progression_summary = pd.DataFrame(progression_rows)
    if progression_summary.empty:
        progression_summary = pd.DataFrame(
            columns=["match_id", "team", "stage", "zone", "lane",
                     "passes", "progressive_passes", "key_passes"]
        )
    defensive_summary = pd.DataFrame(defensive_rows)
    if defensive_summary.empty:
        defensive_summary = pd.DataFrame(
            columns=["match_id", "team", "stage", "action", "zone", "actions"]
        )
    territorial_summary = pd.DataFrame(territorial_rows)
    if territorial_summary.empty:
        territorial_summary = pd.DataFrame(
            columns=["match_id", "team", "stage", "x_limit", "spatial_events",
                     "team_events", "opponent_events", "proxy_share", "proxy_label"]
        )
    progression_summary.to_csv(output_path / "progression_summary.csv", index=False)
    defensive_summary.to_csv(output_path / "defensive_summary.csv", index=False)
    territorial_summary.to_csv(output_path / "territorial_proxy.csv", index=False)
    variability_summary.to_csv(output_path / "variability_summary.csv", index=False)
    context = match_metrics[
        ["match_id", "team", "opponent", "venue", "stage"]
    ].copy()
    events = events.merge(
        context.rename(columns={"match_id": "id_partido", "team": "focal_team"}),
        on="id_partido",
        how="inner",
    )
    possessions = possessions.merge(
        context.rename(columns={"match_id": "id_partido", "team": "focal_team"}),
        on="id_partido",
        how="inner",
    )
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
                    "stage labels are contextual and do not independently prove tournament membership; Atlético de San Luis matches after 2023 are excluded from the pre-América stage",
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
    context_metrics = {
        "average_passes": ("passes", "mean"),
        "average_progressive_passes": ("progressive_passes", "mean"),
        "average_pressures": ("pressures", "mean"),
        "average_high_pressures": ("high_pressures", "mean"),
        "average_recoveries": ("recoveries", "mean"),
        "average_xg": ("xg", "mean"),
        "average_ppda": ("ppda", "mean"),
    }
    opponent_summary = (
        match_metrics.groupby(["stage", "team", "opponent"], as_index=False, dropna=False)
        .agg(matches=("match_id", "nunique"), **context_metrics)
        .sort_values(["stage", "team", "matches"], ascending=[True, True, False])
    )
    venue_summary = (
        match_metrics.groupby(["stage", "team", "venue"], as_index=False, dropna=False)
        .agg(matches=("match_id", "nunique"), **context_metrics)
        .sort_values(["stage", "team", "venue"])
    )
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

    shot_events = events[events["tipo_evento"].eq("Shot")].rename(
        columns={
            "id_evento": "shot_event_id",
            "equipo": "event_team",
            "possession_id": "event_possession_id",
            "x_inicio": "x",
            "y_inicio": "y",
            "patron_juego": "pattern",
        }
    )
    shot_map = shot_events.merge(
        shots.rename(
            columns={
                "id_remate": "shot_event_id",
                "equipo": "shooting_team",
                "possession_id": "shot_possession_id",
                "tipo_gol_o_remate": "outcome",
            }
        )[
            [
                "shot_event_id",
                "shooting_team",
                "shot_possession_id",
                "xg",
                "outcome",
            ]
        ],
        on="shot_event_id",
        how="inner",
        validate="one_to_one",
    )
    shot_map = shot_map[
        shot_map["x"].notna() & shot_map["y"].notna()
    ].copy()
    shot_map["side"] = shot_map.apply(
        lambda row: "focal" if row["shooting_team"] == row["focal_team"] else "opponent",
        axis=1,
    )
    shot_map = shot_map[
        [
            "id_partido",
            "focal_team",
            "opponent",
            "venue",
            "stage",
            "shooting_team",
            "side",
            "x",
            "y",
            "xg",
            "outcome",
            "pattern",
            "event_possession_id",
        ]
    ].rename(
        columns={
            "id_partido": "match_id",
            "focal_team": "team",
            "shooting_team": "shooting_team",
            "event_possession_id": "possession_id",
        }
    )

    focal_passes = passes.merge(
        context.rename(columns={"match_id": "id_partido", "team": "focal_team"}),
        on="id_partido",
        how="inner",
    )
    focal_passes = focal_passes[
        focal_passes["equipo"].eq(focal_passes["focal_team"])
    ].copy()
    pass_network = (
        focal_passes[focal_passes["jugador"].notna() & focal_passes["receptor"].notna()]
        .groupby(
            ["id_partido", "focal_team", "stage", "opponent", "venue", "jugador", "receptor"],
            as_index=False,
        )
        .size()
        .rename(
            columns={
                "id_partido": "match_id",
                "focal_team": "team",
                "jugador": "player",
                "receptor": "receiver",
                "size": "passes",
            }
        )
    )

    player_events = events[
        events["equipo"].eq(events["focal_team"])
        & events["jugador_id"].notna()
        & events["x_inicio"].notna()
        & events["y_inicio"].notna()
    ].copy()
    player_events["x_inicio"] = pd.to_numeric(
        player_events["x_inicio"], errors="coerce"
    )
    player_events["y_inicio"] = pd.to_numeric(
        player_events["y_inicio"], errors="coerce"
    )
    player_events = player_events[
        player_events["x_inicio"].between(0, 120)
        & player_events["y_inicio"].between(0, 80)
    ].copy()
    player_events["grid_x"] = (player_events["x_inicio"] // 10).clip(upper=11).astype(int)
    player_events["grid_y"] = (player_events["y_inicio"] // 10).clip(upper=7).astype(int)
    player_activity_map = (
        player_events.groupby(
            [
                "focal_team",
                "stage",
                "jugador_id",
                "jugador",
                "grid_x",
                "grid_y",
            ],
            as_index=False,
            dropna=False,
        )
        .size()
        .rename(
            columns={
                "focal_team": "team",
                "jugador_id": "player_id",
                "jugador": "player",
                "size": "events",
            }
        )
        .sort_values(["team", "stage", "player_id", "grid_y", "grid_x"])
    )

    focal_features = player_features.merge(
        context.rename(columns={"match_id": "id_partido", "team": "focal_team"}),
        on="id_partido",
        how="inner",
    )
    focal_features = focal_features[
        focal_features["equipo"].eq(focal_features["focal_team"])
    ].copy()
    score_state_summary = (
        focal_features.groupby(
            ["stage", "focal_team", "estado_partido"],
            as_index=False,
            dropna=False,
        )
        .agg(
            matches=("id_partido", "nunique"),
            active_windows=("ventana_minuto", "size"),
            passes=("pases", "sum"),
            progressive_passes=("pases_progresivos", "sum"),
            carries=("conducciones", "sum"),
            xa=("xa", "sum"),
            xg=("xg", "sum"),
            pressures=("presiones", "sum"),
            recoveries=("recuperaciones", "sum"),
            losses=("perdidas", "sum"),
            duels_won=("duelos_ganados", "sum"),
        )
        .rename(columns={"focal_team": "team", "estado_partido": "score_state"})
    )
    if not player_appearances.empty:
        player_positions = (
            player_appearances.dropna(subset=["posicion"])
            .groupby(["equipo", "jugador_id"], as_index=False)["posicion"]
            .agg(lambda values: values.mode().iloc[0])
            .rename(columns={"posicion": "position"})
        )
        focal_features = focal_features.merge(
            player_positions,
            on=["equipo", "jugador_id"],
            how="left",
        )
    else:
        focal_features["position"] = None
    player_summary = (
        focal_features.groupby(
            ["focal_team", "stage", "jugador_id", "jugador", "position"],
            as_index=False,
            dropna=False,
        )
        .agg(
            matches=("id_partido", "nunique"),
            active_windows=("ventana_minuto", "size"),
            passes=("pases", "sum"),
            progressive_passes=("pases_progresivos", "sum"),
            carries=("conducciones", "sum"),
            xa=("xa", "sum"),
            xg=("xg", "sum"),
            pressures=("presiones", "sum"),
            recoveries=("recuperaciones", "sum"),
            losses=("perdidas", "sum"),
            duels_won=("duelos_ganados", "sum"),
        )
        .rename(
            columns={
                "focal_team": "team",
                "jugador_id": "player_id",
                "jugador": "player",
            }
        )
        .sort_values(["team", "stage", "active_windows"], ascending=[True, True, False])
    )

    possession_summary = (
        possessions[possessions["possession_team"].eq(possessions["focal_team"])]
        .groupby(["stage", "focal_team"], as_index=False)
        .agg(
            possessions=("possession_id", "size"),
            average_duration_seconds=("duracion", "mean"),
            average_events=("eventos", "mean"),
            average_passes=("pases", "mean"),
            average_carries=("conducciones", "mean"),
            shots=("tiros", "sum"),
            high_recoveries=("recuperacion_alta", "sum"),
        )
        .rename(columns={"focal_team": "team"})
    )

    patterns = events[
        events["patron_juego"].isin(
            ["From Corner", "From Free Kick", "From Throw In"]
        )
        & events["possession_id"].notna()
        & events["possession_team"].notna()
    ]
    if not patterns.empty:
        piece_possessions = (
            patterns.groupby(
                [
                    "id_partido",
                    "possession_id",
                    "focal_team",
                    "opponent",
                    "venue",
                    "stage",
                    "possession_team",
                    "patron_juego",
                ],
                as_index=False,
            )
            .size()
            .rename(columns={"size": "event_rows", "patron_juego": "pattern"})
        )
        piece_possessions["role"] = piece_possessions.apply(
            lambda row: (
                "offensive"
                if row["possession_team"] == row["focal_team"]
                else "defensive"
            ),
            axis=1,
        )
        set_piece_shots = (
            shot_map.merge(
                piece_possessions[
                    ["id_partido", "possession_id", "pattern", "role", "focal_team"]
                ],
                left_on=["match_id", "possession_id", "pattern", "team"],
                right_on=[
                    "id_partido",
                    "possession_id",
                    "pattern",
                    "focal_team",
                ],
                how="inner",
            )
            .groupby(["id_partido", "possession_id", "pattern", "role"], as_index=False)
            .agg(
                shots=("outcome", "size"),
                goals=("outcome", lambda values: values.eq("Goal").sum()),
                xg=("xg", "sum"),
            )
        )
        piece_possessions = piece_possessions.merge(
            set_piece_shots,
            on=["id_partido", "possession_id", "pattern", "role"],
            how="left",
        )
        piece_possessions[["shots", "goals", "xg"]] = piece_possessions[
            ["shots", "goals", "xg"]
        ].fillna(0)
        set_piece_summary = (
            piece_possessions.groupby(
                ["stage", "focal_team", "role", "pattern"], as_index=False
            )
            .agg(
                matches=("id_partido", "nunique"),
                possessions=("possession_id", "nunique"),
                event_rows=("event_rows", "sum"),
                shots=("shots", "sum"),
                goals=("goals", "sum"),
                xg=("xg", "sum"),
            )
            .rename(columns={"focal_team": "team"})
        )
    else:
        set_piece_summary = pd.DataFrame(
            columns=[
                "stage",
                "team",
                "role",
                "pattern",
                "matches",
                "possessions",
                "event_rows",
                "shots",
                "goals",
                "xg",
            ]
        )

    report_data = {
        "metadata": {
            "match_count": int(len(match_metrics)),
            "coordinate_system": "Coordenadas originales de la fuente: x de 0 a 120 e y de 0 a 80; no se ajustan según la dirección del ataque.",
            "limitations": [
                "Las etapas son contextuales; no confirman la competición de cada partido.",
                "La fecha, la competición y el estadio están vacíos en la tabla de partidos de origen.",
                "Las coordenadas no indican hacia qué portería se ataca; por eso no se calcula el dominio territorial (Field Tilt).",
                "La red de pases incluye solo pases cuyo receptor está identificado.",
                "La actividad de jugadores se resume en intervalos de cinco minutos de la fuente, no en minutos exactos jugados.",
                "El resumen de balón parado cuenta posesiones asociadas a una reanudación, no únicamente la jugada inmediata del saque.",
                "Las asociaciones observadas no demuestran la intención táctica ni una relación de causa y efecto.",
            ],
            "definitions": {
                "possession": "Tramo continuo en el que un equipo controla el balón, según la tabla de posesiones de la fuente.",
                "offensive_sequence": "Posesión utilizada para observar cómo un equipo inicia, avanza y termina sus ataques.",
                "pressure": "Acción de presión registrada por la fuente. Se considera alta si aparece en el tercio ofensivo según esa misma fuente.",
                "ppda": "Pases del rival divididos entre acciones defensivas del equipo en la zona definida por la fuente. Un valor menor suele indicar presión más intensa.",
                "transition": "Secuencia registrada desde una recuperación hasta un posible remate; no representa todas las transiciones del partido.",
                "set_piece": "Posesión relacionada con un córner, tiro libre o saque de banda; no necesariamente termina en un remate inmediato.",
            },
        },
        "matches": _records(match_metrics),
        "stage_summary": _records(stage_summary),
        "context_summary": _records(context_summary),
        "opponent_summary": _records(opponent_summary),
        "venue_summary": _records(venue_summary),
        "score_state_summary": _records(score_state_summary),
        "formation_summary": _records(formation_summary),
        "transition_summary": _records(transition_summary),
        "decision_summary": _records(decision_summary),
        "variability_summary": _records(variability_summary),
        "progression_summary": _records(progression_summary),
        "defensive_summary": _records(defensive_summary),
        "territorial_proxy": _records(territorial_summary),
        "possession_summary": _records(possession_summary),
        "player_summary": _records(player_summary),
        "player_activity_map": _records(player_activity_map),
        "pass_network": _records(pass_network),
        "shot_map": _records(shot_map),
        "set_piece_summary": _records(set_piece_summary),
    }
    (output_path / "report_data.json").write_text(
        json.dumps(report_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
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
