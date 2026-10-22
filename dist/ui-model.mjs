export function formatFormation(value) {
  const formation = String(value ?? "").trim();
  if (!/^\d{3,5}$/.test(formation)) return formation || "—";

  return [...formation].join("-");
}

function matchesScope(row, team, stage) {
  return (team === "all" || row.team === team)
    && (stage === "all" || row.stage === stage);
}

export function filterPlayerActivity(rows, team, stage, playerId) {
  return rows.filter((row) =>
    matchesScope(row, team, stage)
    && (playerId === "all" || row.player_id === playerId)
  );
}

export function filterTeamGoals(rows, team, stage) {
  return rows.filter((row) =>
    (team === "all" || row.team === team)
    && (stage === "all" || row.stage === stage)
    && row.shooting_team === row.team
    && String(row.outcome).toLowerCase() === "goal"
  );
}

export function filterTeamSetPieces(rows, team, stage) {
  return rows.filter((row) => matchesScope(row, team, stage));
}
