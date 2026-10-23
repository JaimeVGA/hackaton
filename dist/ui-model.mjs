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

const insightStageNames = {
  pre_america: "Pre-América",
  america_championship_context: "América campeón",
  post_championship_context: "Post campeonatos",
};
const insightZoneNames = {
  "0-40": "salida",
  "40-80": "progresión",
  "80-120": "último tercio",
  ATTACKING_THIRD: "tercio ofensivo",
  DEFENSIVE_THIRD: "tercio defensivo",
  MIDDLE_THIRD: "tercio medio",
  PENALTY_BOX: "área",
};
const insightLaneNames = { center: "centro", left: "carril izquierdo", right: "carril derecho" };
const insightActionNames = {
  "Ball Recovery": "recuperaciones",
  Block: "bloqueos",
  Clearance: "despejes",
  Dispossessed: "pérdidas",
  Duel: "duelos",
  Error: "errores",
  Interception: "intercepciones",
  Pressure: "presiones",
};
const insightMetricNames = {
  passes: "pases por partido",
  progressive_passes: "pases progresivos por partido",
  pressures: "presiones por partido",
  high_pressures: "presiones altas por partido",
  recoveries: "recuperaciones por partido",
  high_recoveries: "recuperaciones altas por partido",
  shots: "remates por partido",
  xg: "xG por partido",
  ppda: "PPDA",
};
const insightStateNames = {
  ganando: "ventaja",
  empatando: "empate",
  perdiendo: "desventaja",
};
const insightPatternNames = {
  "From Corner": "córner",
  "From Free Kick": "tiro libre",
  "From Throw In": "saque de banda",
};

function insightNumber(value, digits = 1) {
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString("es-MX", { maximumFractionDigits: digits })
    : "sin datos";
}

function insightStage(stage) {
  return insightStageNames[stage] || "etapa no disponible";
}

function matchesScope(row, team, stage) {
  return (team === "all" || row.team === team)
    && (stage === "all" ? includedStages.has(row.stage) : row.stage === stage);
}

export function buildSectionCommentaries(report, team, stage, playerId) {
  const scope = (rows = []) => rows.filter((row) => matchesScope(row, team, stage));
  const matchCount = new Set(
    (report.matches || [])
      .filter((row) => includedStages.has(row.stage))
      .map((row) => row.match_id)
      .filter((id) => id != null),
  ).size;
  const reportMatchCount = Number(report.metadata?.match_count) || matchCount;

  const panoramaRows = scope(report.stage_summary)
    .filter((row) => Number(row.matches) > 0 && Number(row.shots) > 0);
  const panoramaComparisons = panoramaRows.map((row) => ({
    ...row,
    xgPerShot: Number(row.xg) / Number(row.shots),
  })).filter((row) => Number.isFinite(row.xgPerShot));
  let panorama = "No hay promedios disponibles para los filtros actuales.";
  if (panoramaComparisons.length === 1) {
    const row = panoramaComparisons[0];
    panorama = `En ${insightNumber(row.matches, 0)} partidos, ${row.team} promedió ${insightNumber(row.shots)} remates y ${insightNumber(row.xg, 2)} xG por partido; el xG por remate fue ${insightNumber(row.xgPerShot, 3)}. El xG estima qué tan probable era que cada tiro terminara en gol según la situación: ${insightNumber(row.xgPerShot * 100, 1)}% equivale aproximadamente a esa probabilidad media, no a una garantía para un tiro concreto.`;
  } else if (panoramaComparisons.length > 1) {
    const highest = [...panoramaComparisons].sort((a, b) => b.xgPerShot - a.xgPerShot)[0];
    const lowest = [...panoramaComparisons].sort((a, b) => a.xgPerShot - b.xgPerShot)[0];
    panorama = `Para comparar la calidad media de los tiros, dividimos el xG entre los remates: a eso le llamamos xG por remate. El valor más alto es ${insightNumber(highest.xgPerShot, 3)} en ${highest.team} · ${insightStage(highest.stage)} (${insightNumber(highest.matches, 0)} partidos), y el más bajo ${insightNumber(lowest.xgPerShot, 3)} en ${lowest.team} · ${insightStage(lowest.stage)} (${insightNumber(lowest.matches, 0)} partidos). El valor alto equivale aproximadamente a ${insightNumber(highest.xgPerShot * 100, 1)}% de probabilidad media por tiro, no a una promesa de gol. Rival, torneo y plantilla pueden diferir entre etapas, así que no es una comparación controlada.`;
  }

  const progressionGroups = new Map();
  scope(report.progression_summary).forEach((row) => {
    const key = `${row.team}|${row.stage}|${row.zone}|${row.lane}`;
    const group = progressionGroups.get(key) || {
      team: row.team, stage: row.stage, zone: row.zone, lane: row.lane, passes: 0, matches: new Set(),
    };
    group.passes += Number(row.progressive_passes) || 0;
    if (row.match_id != null) group.matches.add(row.match_id);
    progressionGroups.set(key, group);
  });
  const topProgression = [...progressionGroups.values()]
    .filter((row) => row.matches.size)
    .map((row) => ({ ...row, perMatch: row.passes / row.matches.size }))
    .sort((a, b) => b.perMatch - a.perMatch)[0];

  const defensiveGroups = new Map();
  scope(report.defensive_summary).forEach((row) => {
    const key = `${row.team}|${row.stage}|${row.action}|${row.zone}`;
    const group = defensiveGroups.get(key) || {
      team: row.team, stage: row.stage, action: row.action, zone: row.zone, actions: 0, matches: new Set(),
    };
    group.actions += Number(row.actions) || 0;
    if (row.match_id != null) group.matches.add(row.match_id);
    defensiveGroups.set(key, group);
  });
  const topDefensive = [...defensiveGroups.values()]
    .filter((row) => row.matches.size)
    .map((row) => ({ ...row, perMatch: row.actions / row.matches.size }))
    .sort((a, b) => b.perMatch - a.perMatch)[0];

  const transitionRows = scope(report.transition_summary);
  const topTransition = [...transitionRows]
    .filter((row) => Number(row.transitions) >= 5)
    .sort((a, b) =>
      (Number(b.xg_generated) || 0) / Number(b.transitions)
      - (Number(a.xg_generated) || 0) / Number(a.transitions)
    )[0];
  const variableMetric = scope(report.variability_summary)
    .filter((row) => Number(row.mean) > 0)
    .map((row) => ({
      ...row,
      relativeRange: (Number(row.q3) - Number(row.q1)) / Number(row.mean),
    }))
    .filter((row) => Number.isFinite(row.relativeRange))
    .sort((a, b) => b.relativeRange - a.relativeRange)[0];
  const topFormation = scope(report.formation_summary)
    .sort((a, b) => Number(b.matches) - Number(a.matches))[0];
  const decisionRows = scope(report.decision_summary)
    .sort((a, b) =>
      Number(b.matches_with_substitution) - Number(a.matches_with_substitution)
    );
  const representativeDecision = decisionRows[0];
  const territoryGroups = new Map();
  scope(report.territorial_proxy).forEach((row) => {
    const key = `${row.team}|${row.stage}`;
    const group = territoryGroups.get(key) || {
      team: row.team, stage: row.stage, matches: 0, share: 0,
    };
    group.matches += 1;
    group.share += Number(row.proxy_share) || 0;
    territoryGroups.set(key, group);
  });
  const topTerritory = [...territoryGroups.values()]
    .filter((row) => row.matches)
    .map((row) => ({ ...row, averageShare: row.share / row.matches }))
    .sort((a, b) => b.averageShare - a.averageShare)[0];
  const identityFindings = [];
  if (topProgression) {
    identityFindings.push(
      `Pases: el mayor volumen de pases progresivos —pases que la fuente marca como avance— fue ${insightNumber(topProgression.perMatch)} por partido en ${insightZoneNames[topProgression.zone] || topProgression.zone} · ${insightLaneNames[topProgression.lane] || topProgression.lane} (${topProgression.team}, ${insightStage(topProgression.stage)}, ${insightNumber(topProgression.matches.size, 0)} partidos). La zona es una coordenada original y no necesariamente indica hacia dónde se atacaba.`,
    );
  }
  if (topDefensive) {
    identityFindings.push(
      `Defensa: lo que más se registró fue ${insightActionNames[topDefensive.action] || topDefensive.action} en ${insightZoneNames[topDefensive.zone] || topDefensive.zone}: ${insightNumber(topDefensive.perMatch)} por partido (${topDefensive.team}, ${insightStage(topDefensive.stage)}, ${insightNumber(topDefensive.matches.size, 0)} partidos). Que haya más acciones no significa automáticamente defender mejor; también puede significar que el rival tuvo más tiempo el balón.`,
    );
  }
  if (topTransition) {
    identityFindings.push(
      `Tras recuperar: las secuencias iniciadas en ${insightZoneNames[topTransition.zona_recuperacion] || topTransition.zona_recuperacion} generaron ${insightNumber((Number(topTransition.xg_generated) || 0) / Number(topTransition.transitions), 3)} xG por transición en ${insightNumber(topTransition.transitions, 0)} secuencias (${topTransition.team} · ${insightStage(topTransition.stage)}). El xG estima la calidad de los tiros posteriores; no cuenta goles garantizados.`,
    );
  }
  const structureFindings = [];
  if (topFormation) {
    structureFindings.push(
      `Formación: ${formatFormation(topFormation.formacion)} fue la colocación inicial más repetida (${topFormation.team} · ${insightStage(topFormation.stage)}, ${insightNumber(topFormation.matches, 0)} partidos). El dibujo representa cuatro defensores, dos mediocampistas, tres jugadores más adelantados y un delantero; las posiciones pueden cambiar durante el juego.`,
    );
  }
  if (representativeDecision) {
    structureFindings.push(
      `Ajustes: en ${representativeDecision.team} · ${insightStage(representativeDecision.stage)} hubo ${insightNumber(representativeDecision.substitution_events, 0)} sustituciones y ${insightNumber(representativeDecision.formation_change_events, 0)} cambios de formación. Estos conteos no revelan la intención del cuerpo técnico ni demuestran si el cambio funcionó.`,
    );
  }
  if (variableMetric) {
    structureFindings.push(
      `Regularidad: la mitad de los partidos de ${variableMetric.team} · ${insightStage(variableMetric.stage)} quedó entre ${insightNumber(variableMetric.q1, 1)} y ${insightNumber(variableMetric.q3, 1)} en ${variableMetric.metric === "ppda" ? "PPDA (un indicador de presión)" : insightMetricNames[variableMetric.metric] || variableMetric.metric} (${insightNumber(variableMetric.matches, 0)} partidos). Un rango amplio indica que el promedio cambia bastante de un partido a otro.`,
    );
  }
  if (topTerritory) {
    structureFindings.push(
      `Ubicación del juego: el proxy territorial fue ${insightNumber(topTerritory.averageShare * 100, 1)}% para ${topTerritory.team} · ${insightStage(topTerritory.stage)} (${insightNumber(topTerritory.matches, 0)} partidos). Es una proporción de pases en una zona dibujada, no una medida oficial de dominio; la fuente no indica hacia qué portería se atacaba.`,
    );
  }
  const identity = identityFindings.length || structureFindings.length
    ? `${identityFindings.join("\n\n")} ${structureFindings.join("\n\n")}`
    : "No hay métricas de progresión, defensa, estructura o transición disponibles para los filtros actuales.";

  const contextRows = scope(report.context_summary);
  const stateGroups = new Map();
  contextRows.forEach((row) => {
    const group = stateGroups.get(row.estado) || { state: row.estado, matches: 0, eventRows: 0 };
    group.matches += Number(row.matches) || 0;
    group.eventRows += Number(row.event_rows) || 0;
    stateGroups.set(row.estado, group);
  });
  const topState = [...stateGroups.values()].sort((a, b) => b.eventRows - a.eventRows)[0];
  const venueGroups = new Map();
  scope(report.venue_summary).forEach((row) => {
    const group = venueGroups.get(row.venue) || { venue: row.venue, matches: 0, xg: 0 };
    const matches = Number(row.matches) || 0;
    group.matches += matches;
    group.xg += (Number(row.average_xg) || 0) * matches;
    venueGroups.set(row.venue, group);
  });
  const venueComparisons = [...venueGroups.values()].filter((row) => row.matches)
    .map((row) => ({ ...row, averageXg: row.xg / row.matches }));
  const home = venueComparisons.find((row) => row.venue === "home");
  const away = venueComparisons.find((row) => row.venue === "away");
  const opponentRows = scope(report.opponent_summary);
  const opponentCounts = opponentRows.map((row) => Number(row.matches) || 0).filter(Boolean);
  const possessionRows = scope(report.possession_summary);
  const possessions = possessionRows.reduce((sum, row) => sum + (Number(row.possessions) || 0), 0);
  const possessionPasses = possessions
    ? possessionRows.reduce((sum, row) =>
      sum + (Number(row.average_passes) || 0) * (Number(row.possessions) || 0), 0) / possessions
    : null;
  const possessionDuration = possessions
    ? possessionRows.reduce((sum, row) =>
      sum + (Number(row.average_duration_seconds) || 0) * (Number(row.possessions) || 0), 0) / possessions
    : null;
  const possessionShots = possessionRows.reduce((sum, row) => sum + (Number(row.shots) || 0), 0);
  const contextParts = [];
  if (topState) {
    contextParts.push(
      `Marcador: en los eventos se registró el estado de ${insightStateNames[topState.state] || topState.state} en ${insightNumber(topState.matches, 0)} apariciones por equipo/etapa, con ${insightNumber(topState.eventRows, 0)} filas. No indica qué porcentaje del encuentro se jugó así; muchos partidos empiezan empatados.`,
    );
  }
  if (possessions) {
    contextParts.push(
      `Ritmo: las ${insightNumber(possessions, 0)} posesiones promediaron ${insightNumber(possessionPasses)} pases y ${insightNumber(possessionDuration)} segundos; se asociaron ${insightNumber(possessionShots, 0)} remates. Una posesión es un tramo de control del balón: alargarla o dar más pases no garantiza crear peligro.`,
    );
  }
  if (home && away) {
    contextParts.push(
      `Localía: el xG medio fue ${insightNumber(home.averageXg, 2)} en casa (${insightNumber(home.matches, 0)} partidos) y ${insightNumber(away.averageXg, 2)} fuera (${insightNumber(away.matches, 0)} partidos). Es una diferencia observada, no prueba de que jugar en casa la haya causado.`,
    );
  }
  if (opponentCounts.length > 1) {
    contextParts.push(
      `Rivales: hay entre ${insightNumber(Math.min(...opponentCounts), 0)} y ${insightNumber(Math.max(...opponentCounts), 0)} partidos por rival; algunas comparaciones tienen más respaldo que otras.`,
    );
  }
  const context = contextParts.length
    ? contextParts.join("\n\n")
    : "No hay datos de contexto o posesiones para los filtros actuales.";

  const playerRows = scope(report.player_summary);
  let players;
  if (playerId === "all") {
    const playerCount = new Set(playerRows.map((row) => row.player_id).filter(Boolean)).size;
    const rankedPlayers = new Map();
    playerRows.forEach((row) => {
      const matches = Number(row.matches) || 0;
      if (!row.player_id || matches < 5) return;
      const player = rankedPlayers.get(row.player_id) || {
        player: row.player, position: row.position, matches: 0, progressivePasses: 0, xg: 0,
      };
      player.matches += matches;
      player.progressivePasses += Number(row.progressive_passes) || 0;
      player.xg += Number(row.xg) || 0;
      rankedPlayers.set(row.player_id, player);
    });
    const referencePlayer = [...rankedPlayers.values()]
      .sort((a, b) =>
        b.progressivePasses / b.matches - a.progressivePasses / a.matches
      )[0];
    players = referencePlayer
      ? `Hay ${insightNumber(playerCount, 0)} jugadores con datos. Como referencia estadística —no como “mejor jugador”—, ${referencePlayer.player} registra más pases progresivos por partido entre quienes aparecen en al menos cinco encuentros: ${insightNumber(referencePlayer.progressivePasses / referencePlayer.matches)} en ${insightNumber(referencePlayer.matches, 0)} partidos. Un pase progresivo avanza el balón según el registro; no mide por sí solo la calidad total del jugador. La actividad se agrupa en ventanas de cinco minutos, no en minutos exactos.`
      : `Hay ${insightNumber(playerCount, 0)} jugadores con datos, pero la muestra no permite destacar a alguien con una base mínima de cinco partidos. La actividad se agrupa en ventanas de cinco minutos, no en minutos exactos jugados.`;
  } else {
    const selectedRows = playerRows.filter((row) => row.player_id === playerId);
    if (!selectedRows.length) {
      players = "No hay métricas individuales para el jugador seleccionado con estos filtros.";
    } else {
      const player = selectedRows[0];
      const matches = selectedRows.reduce((sum, row) => sum + (Number(row.matches) || 0), 0);
      const passes = selectedRows.reduce((sum, row) => sum + (Number(row.passes) || 0), 0);
      const progressivePasses = selectedRows.reduce((sum, row) =>
        sum + (Number(row.progressive_passes) || 0), 0);
      const xg = selectedRows.reduce((sum, row) => sum + (Number(row.xg) || 0), 0);
      const windows = selectedRows.reduce((sum, row) => sum + (Number(row.active_windows) || 0), 0);
      const playerConnections = (report.pass_network || [])
        .filter((row) =>
          matchesScope(row, team, stage)
          && (row.player === player.player || row.receiver === player.player)
        )
        .reduce((connections, row) => {
          const teammate = row.player === player.player ? row.receiver : row.player;
          if (!teammate || teammate === player.player) return connections;
          const connection = connections.get(teammate) || { name: teammate, passes: 0, matches: new Set() };
          connection.passes += Number(row.passes) || 0;
          if (row.match_id != null) connection.matches.add(row.match_id);
          connections.set(teammate, connection);
          return connections;
        }, new Map());
      const mostConnected = [...playerConnections.values()]
        .sort((a, b) => b.passes - a.passes)[0];
      players = matches > 0
        ? `${player.player} aparece en ${insightNumber(matches, 0)} partidos, con ${insightNumber(passes / matches)} pases y ${insightNumber(progressivePasses / matches)} progresivos por partido; suma ${insightNumber(xg / matches, 2)} xG por partido. La red registra más pases con ${mostConnected?.name || "ningún compañero"} (${insightNumber(mostConnected?.passes || 0, 0)} pases en ${insightNumber(mostConnected?.matches.size || 0, 0)} partidos), pero volumen de pase no equivale a entendimiento o calidad. El mapa agrupa ${insightNumber(windows, 0)} ventanas de cinco minutos y no informa los minutos exactos jugados.`
        : "No hay suficientes partidos con datos individuales para calcular promedios.";
    }
  }

  const goals = filterTeamGoals(report.shot_map || [], team, stage);
  const setPieceRows = filterTeamSetPieces(report.set_piece_summary || [], team, stage);
  const pieceGroups = new Map();
  setPieceRows.forEach((row) => {
    const key = `${row.team}|${row.role}|${row.pattern}`;
    const group = pieceGroups.get(key) || {
      team: row.team, role: row.role, pattern: row.pattern, possessions: 0, xg: 0,
    };
    group.possessions += Number(row.possessions) || 0;
    group.xg += Number(row.xg) || 0;
    pieceGroups.set(key, group);
  });
  const topPieceByRole = (role) => [...pieceGroups.values()]
    .filter((row) => row.role === role && row.possessions > 0)
    .map((row) => ({ ...row, xgPerPossession: row.xg / row.possessions }))
    .sort((a, b) => b.xgPerPossession - a.xgPerPossession)[0];
  const attackPiece = topPieceByRole("offensive");
  const defensePiece = topPieceByRole("defensive");
  const pieceParts = [];
  if (attackPiece) {
    pieceParts.push(
      `En ataque, ${attackPiece.team} · ${insightPatternNames[attackPiece.pattern] || attackPiece.pattern} promedia ${insightNumber(attackPiece.xgPerPossession, 3)} xG por secuencia (${insightNumber(attackPiece.possessions, 0)} secuencias)`,
    );
  }
  if (defensePiece) {
    pieceParts.push(
      `Al defender, las secuencias rivales de ${insightPatternNames[defensePiece.pattern] || defensePiece.pattern} generaron ${insightNumber(defensePiece.xgPerPossession, 3)} xG por secuencia (${insightNumber(defensePiece.possessions, 0)} secuencias)`,
    );
  }
  const collective = `${insightNumber(goals.length, 0)} goles aparecen en el mapa colectivo para estos filtros. ${pieceParts.length ? `${pieceParts.join(". ")}.` : "No hay datos de balón parado para los filtros actuales."} xG es una estimación de la calidad de los tiros: no es el número de goles anotados. Las secuencias de balón parado pueden incluir acciones posteriores al saque, y las coordenadas del mapa no indican hacia qué portería se atacaba.`;

  return {
    scope: {
      analysis: `El archivo contiene ${insightNumber(reportMatchCount, 0)} partidos; ${insightNumber(matchCount, 0)} pertenecen a las tres etapas que aparecen en el recorrido longitudinal y los otros quedan fuera de esa comparación. Las etiquetas “Pre-América”, “América campeón” y “Post campeonatos” sirven para ordenar la historia, pero no certifican el torneo de cada encuentro. Las cifras describen lo que se registró: una diferencia entre etapas no prueba que Jardine la haya causado, porque también pueden cambiar rivales, jugadores y circunstancias del partido.`,
      action: "Empieza con la vista completa para conocer el panorama y después filtra un solo equipo y una etapa para comparar partidos parecidos. Toma la etapa previa como referencia, no como una comparación idéntica. Si una cifra te interesa, comprueba en la tabla partido por partido que el patrón se repita antes de proponer un cambio.",
    },
    panorama: {
      analysis: panorama,
      action: panoramaComparisons.length > 1
        ? `Revisa en video varias posesiones que terminaron en tiro de las etapas con valores más alto y más bajo. Pregunta si el remate llegó desde una posición cercana y con ventaja o desde lejos y con presión; luego mide tiros dentro del área y xG por remate. La meta no es tirar más, sino crear intentos mejores. Repite la comparación con rivales y marcadores similares.`
        : "Elige varios partidos de esta etapa y clasifica sus remates en dos grupos: tiros claros cerca del arco y tiros lejanos o forzados. Revisa qué pase o movimiento permitió llegar a cada grupo. Después prueba en entrenamiento una forma de repetir las llegadas más claras y comprueba si sube el xG por remate, no solo el total de tiros.",
    },
    identity: {
      analysis: identity,
      action: "En video, sigue una jugada de cada tipo: un avance progresivo, una acción defensiva y una recuperación seguida de ataque. Anota qué ocurrió antes y después, y cuál terminó en una ocasión. Prueba mantener la estructura que genera avances útiles; no cambies formación o presión solo porque un conteo sea alto. Evalúa cualquier ajuste en partidos comparables.",
    },
    context: {
      analysis: context,
      action: "Compara primero partidos en situaciones parecidas: mismo estado del marcador, localía y duración observada. Separa luego los rivales y revisa la tabla individual para comprobar si el promedio está impulsado por uno o dos encuentros. Si una diferencia persiste en varias comparaciones, úsala para preparar un plan distinto cuando el equipo vaya ganando, empatando o perdiendo.",
    },
    players: {
      analysis: players,
      action: playerId === "all"
        ? "Selecciona un jugador para ver sus zonas de actividad y a quién le pasa el balón. Usa la estadística como punto de partida, no como ranking de quién juega mejor: la base no incluye minutos exactos y los totales dependen de cuántos partidos disputó."
        : "Revisa en video algunas conexiones más frecuentes y algunas secuencias sin conexión registrada: ¿el pase ayudó a avanzar, creó una ocasión o fue una salida segura? Compara partidos y posición; antes de valorar el esfuerzo o rendimiento, confirma los minutos jugados y la función asignada, datos que esta base no mide con exactitud.",
    },
    collective: {
      analysis: collective,
      action: "Para atacar, revisa los saques que generaron más xG y registra quién toca primero, desde dónde sale el tiro y qué segunda jugada aparece. Para defender, mide tiros y xG permitidos por saque, incluida la continuación. Prueba una variante ofensiva y un ajuste defensivo por separado; no asignes marcas individuales solo con este mapa.",
    },
  };
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
