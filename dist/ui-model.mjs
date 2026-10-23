export function formatFormation(value) {
  const formation = String(value ?? "").trim();
  if (!/^\d{3,5}$/.test(formation)) return formation || "—";

  return [...formation].join("-");
}

const includedStages = new Set([
  "pre_america",
  "america_championship_context",
  "post_championship_context",
]);

function matchesScope(row, team, stage) {
  return (team === "all" || row.team === team)
    && (stage === "all" ? includedStages.has(row.stage) : row.stage === stage);
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

export function uniquePlayers(rows) {
  const players = new Map();
  rows.forEach((row) => {
    const key = row.player_id || `${row.team}:${row.player}`;
    const existing = players.get(key);
    if (!existing || Number(row.active_windows) > Number(existing.active_windows)) {
      players.set(key, row);
    }
  });
  return [...players.values()];
}

export function aggregatePlayerPassConnections(rows, playerName) {
  const connections = new Map();
  rows.forEach((row) => {
    const passes = Number(row.passes) || 0;
    if (row.player === playerName && row.receiver !== playerName) {
      const edge = connections.get(row.receiver) || {
        name: row.receiver,
        outgoing: 0,
        incoming: 0,
        outgoingMatches: new Set(),
        incomingMatches: new Set(),
      };
      edge.outgoing += passes;
      if (row.match_id != null) edge.outgoingMatches.add(row.match_id);
      connections.set(row.receiver, edge);
    }
    if (row.receiver === playerName && row.player !== playerName) {
      const edge = connections.get(row.player) || {
        name: row.player,
        outgoing: 0,
        incoming: 0,
        outgoingMatches: new Set(),
        incomingMatches: new Set(),
      };
      edge.incoming += passes;
      if (row.match_id != null) edge.incomingMatches.add(row.match_id);
      connections.set(row.player, edge);
    }
  });
  return [...connections.values()].map((edge) => ({
    ...edge,
    outgoingMatches: edge.outgoingMatches.size,
    incomingMatches: edge.incomingMatches.size,
  }));
}
