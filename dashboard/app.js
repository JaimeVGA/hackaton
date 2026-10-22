import {
  filterPlayerActivity,
  filterTeamGoals,
  filterTeamSetPieces,
  formatFormation,
  aggregatePlayerPassConnections,
  uniquePlayers,
} from "./ui-model.mjs";

const stageNames = {
  pre_america: "Pre-América",
  america_championship_context: "América campeón",
  post_championship_context: "Post campeonatos",
};
const stageKeys = Object.keys(stageNames);
const definitionNames = {
  possession: "Posesión",
  offensive_sequence: "Secuencia ofensiva",
  pressure: "Presión",
  ppda: "PPDA",
  transition: "Transición",
  set_piece: "Balón parado",
};

const formatNumber = (value, decimals = 1) => {
  if (value === null || value === undefined || value === "") return "Sin datos";
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString("es-MX", { maximumFractionDigits: decimals })
    : "Sin datos";
};

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const stageLabel = (stage) => stageNames[stage]
  || "Etapa no disponible";
const metricNames = {
  passes: "Pases",
  progressive_passes: "Pases progresivos",
  pressures: "Presiones",
  high_pressures: "Presiones altas",
  recoveries: "Recuperaciones",
  high_recoveries: "Recuperaciones altas",
  shots: "Tiros",
  xg: "xG",
  ppda: "PPDA",
};
const metricUnitNames = {
  passes: "pases por partido",
  progressive_passes: "pases progresivos por partido",
  pressures: "presiones por partido",
  high_pressures: "presiones altas por partido",
  recoveries: "recuperaciones por partido",
  high_recoveries: "recuperaciones altas por partido",
  shots: "tiros por partido",
  xg: "xG por partido",
  ppda: "PPDA",
};
const positionNames = {
  "Center Attacking Midfield": "Mediocampista ofensivo central",
  "Center Forward": "Delantero centro",
  Goalkeeper: "Portero",
  "Left Back": "Lateral izquierdo",
  "Left Center Back": "Defensa central izquierdo",
  "Left Center Forward": "Delantero centro izquierdo",
  "Left Center Midfield": "Mediocampista central izquierdo",
  "Left Defensive Midfield": "Mediocampista defensivo izquierdo",
  "Left Midfield": "Mediocampista izquierdo",
  "Left Wing": "Extremo izquierdo",
  "Right Attacking Midfield": "Mediocampista ofensivo derecho",
  "Right Back": "Lateral derecho",
  "Right Center Back": "Defensa central derecho",
  "Right Center Forward": "Delantero centro derecho",
  "Right Center Midfield": "Mediocampista central derecho",
  "Right Defensive Midfield": "Mediocampista defensivo derecho",
  "Right Midfield": "Mediocampista derecho",
  "Right Wing": "Extremo derecho",
  "Right Wing Back": "Carrilero derecho",
};
const actionNames = {
  "Ball Recovery": "Recuperación",
  Block: "Bloqueo",
  Clearance: "Despeje",
  Dispossessed: "Pérdida",
  Duel: "Duelo",
  Error: "Error",
  Interception: "Intercepción",
  Pressure: "Presión",
};
const zoneNames = {
  "0-40": "Salida",
  "40-80": "Progresión",
  "80-120": "Último tercio",
  ATTACKING_THIRD: "Tercio ofensivo",
  DEFENSIVE_THIRD: "Tercio defensivo",
  MIDDLE_THIRD: "Tercio medio",
  PENALTY_BOX: "Área",
};
const laneNames = { center: "Centro", left: "Izquierdo", right: "Derecho" };
const sortBy = (rows, key) => [...rows].sort((a, b) =>
  String(a[key] ?? "").localeCompare(String(b[key] ?? ""), "es")
);
const matchesScope = (row, team, stage) =>
  (team === "all" || row.team === team)
  && (stage === "all" ? stageKeys.includes(row.stage) : row.stage === stage);

function renderTable(containerId, columns, rows, emptyMessage) {
  const container = document.querySelector(containerId);
  if (!rows.length) {
    container.innerHTML = `<p class="empty">${escapeHtml(emptyMessage)}</p>`;
    return;
  }
  container.innerHTML = `
    <table class="report-table">
      <thead><tr>${columns.map((column) => `<th>${column.label}</th>`).join("")}</tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr>${columns.map((column) => `<td>${column.render ? column.render(row) : escapeHtml(row[column.key])}</td>`).join("")}</tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function renderBars(containerId, rows, { label, value, detail, emptyMessage, limit = 12 }) {
  const container = document.querySelector(containerId);
  if (!rows.length) {
    container.innerHTML = `<p class="empty">${escapeHtml(emptyMessage)}</p>`;
    return;
  }
  const visible = rows.slice(0, limit);
  const max = Math.max(1, ...visible.map((row) => Number(value(row)) || 0));
  container.innerHTML = `
    <div class="bar-chart" role="list">
      ${visible.map((row) => {
        const number = Number(value(row)) || 0;
        const width = Math.max(number > 0 ? 2 : 0, number / max * 100);
        return `<div class="bar-row" role="listitem">
          <div class="bar-row-heading"><span>${escapeHtml(label(row))}</span><strong>${escapeHtml(formatNumber(number, 0))}</strong></div>
          <div class="bar-track" aria-hidden="true"><span style="width:${width}%"></span></div>
          ${detail ? `<small>${escapeHtml(detail(row))}</small>` : ""}
        </div>`;
      }).join("")}
    </div>
  `;
}

function fillSelect(selector, values, labels = {}) {
  const select = document.querySelector(selector);
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = labels[value] || value;
    select.append(option);
  });
}

function renderStageSummary(rows, team, stage) {
  const visible = rows.filter((row) => matchesScope(row, team, stage));
  const container = document.querySelector("#stage-summary");
  if (!visible.length) {
    container.innerHTML = '<p class="empty">No hay datos para estos filtros.</p>';
    return;
  }
  container.innerHTML = visible.map((row) => `
    <article class="stage-card">
      <h3>${escapeHtml(stageLabel(row.stage))}</h3>
      <p class="team">${escapeHtml(row.team)} · ${formatNumber(row.matches, 0)} partidos</p>
      <dl class="metric-list">
        <div><dt>Pases</dt><dd>${formatNumber(row.passes)}</dd></div>
        <div><dt>Pases progresivos</dt><dd>${formatNumber(row.progressive_passes)}</dd></div>
        <div><dt>Presiones</dt><dd>${formatNumber(row.pressures)}</dd></div>
        <div><dt>Recuperaciones</dt><dd>${formatNumber(row.recoveries)}</dd></div>
        <div><dt>Tiros</dt><dd>${formatNumber(row.shots)}</dd></div>
        <div><dt>xG</dt><dd>${formatNumber(row.xg, 2)}</dd></div>
      </dl>
    </article>
  `).join("");
}

function renderFormation(rows, team, stage) {
  const visible = rows.filter((row) => matchesScope(row, team, stage))
    .sort((a, b) => b.matches - a.matches);
  const container = document.querySelector("#formation-summary");
  if (!visible.length) {
    container.innerHTML = '<p class="empty">No hay formaciones disponibles.</p>';
    return;
  }
  container.innerHTML = visible.slice(0, 8).map((row) => `
    <div class="formation-item">
      <strong class="formation-name">${escapeHtml(formatFormation(row.formacion))}</strong>
      <span class="formation-bar"><i style="width:${Math.max(2, row.matches / visible[0].matches * 100)}%"></i></span>
      <span class="formation-count">${formatNumber(row.matches, 0)}</span>
      <small>${escapeHtml(stageLabel(row.stage))} · partidos</small>
    </div>
  `).join("");
}

function renderDecisions(rows, team, stage) {
  const visible = rows.filter((row) => matchesScope(row, team, stage));
  const container = document.querySelector("#decision-summary");
  if (!visible.length) {
    container.innerHTML = '<p class="empty">No hay decisiones disponibles.</p>';
    return;
  }
  container.innerHTML = visible.map((row) => `
    <div class="decision-card">
      <span class="panel-label">${escapeHtml(stageLabel(row.stage))}</span>
      <div class="decision-stats">
        <div><strong>${formatNumber(row.substitution_events, 0)}</strong><span>Sustituciones</span></div>
        <div><strong>${formatNumber(row.formation_change_events, 0)}</strong><span>Cambios de sistema</span></div>
        <div><strong>${formatNumber(row.average_substitution_minute, 0)}′</strong><span>Minuto medio</span></div>
      </div>
    </div>
  `).join("");
}

function renderVariability(rows, team, stage) {
  const visible = rows.filter((row) => matchesScope(row, team, stage));
  const container = document.querySelector("#variability-summary");
  if (!visible.length) {
    container.innerHTML = '<p class="empty">No hay variabilidad disponible.</p>';
    return;
  }
  const metrics = [...new Set(visible.map((row) => row.metric))];
  container.innerHTML = metrics.map((metric) => {
    const group = visible.filter((row) => row.metric === metric);
    const min = Math.min(...group.map((row) => Number(row.q1) || 0));
    const max = Math.max(...group.map((row) => Number(row.q3) || 0));
    const spread = max - min || 1;
    return `<div class="variability-metric">
      <div class="variability-heading"><span>${escapeHtml(metricNames[metric] || metric)}</span><small>${escapeHtml(metricUnitNames[metric] || "promedio por partido")}</small></div>
      ${group.map((row) => {
        const left = ((Number(row.q1) - min) / spread) * 100;
        const width = Math.max(2, ((Number(row.q3) - Number(row.q1)) / spread) * 100);
        const marker = ((Number(row.mean) - min) / spread) * 100;
        const sampleHint = row.matches < 5 ? " · muestra pequeña" : "";
        return `<div class="range-row"><span class="range-label">${escapeHtml(stageLabel(row.stage))}<small>${escapeHtml(row.team)} · ${formatNumber(row.matches, 0)} partidos${sampleHint}</small></span><div class="range-track"><i style="left:${left}%;width:${width}%"></i><b style="left:${marker}%"></b></div><strong>${formatNumber(row.mean, metric === "xg" || metric === "ppda" ? 2 : 0)}</strong></div>`;
      }).join("")}
    </div>`;
  }).join("");
}

function summarizeTerritory(rows, team, stage) {
  const grouped = new Map();
  rows.filter((row) => matchesScope(row, team, stage)).forEach((row) => {
    const key = `${row.stage}|${row.team}`;
    const group = grouped.get(key) || {
      stage: row.stage, team: row.team, matches: 0, shareTotal: 0, events: 0,
    };
    group.matches += 1;
    group.shareTotal += Number(row.proxy_share) || 0;
    group.events += Number(row.spatial_events) || 0;
    grouped.set(key, group);
  });
  return [...grouped.values()].map((row) => ({
    ...row,
    proxy_share: row.matches ? row.shareTotal / row.matches : null,
  }));
}

function renderTerritorial(rows, team, stage) {
  const visible = summarizeTerritory(rows, team, stage);
  const container = document.querySelector("#territorial-summary");
  if (!visible.length) {
    container.innerHTML = '<p class="empty">No hay proxy territorial disponible.</p>';
    return;
  }
  container.innerHTML = visible.map((row) => `
    <div class="territory-card">
      <div><span class="panel-label">${escapeHtml(stageLabel(row.stage))}</span><strong>${formatNumber(Number(row.proxy_share) * 100, 1)}%</strong></div>
      <div class="bar-track"><span style="width:${Math.min(100, Number(row.proxy_share) * 100)}%"></span></div>
      <small>Promedio por partido · ${formatNumber(row.events, 0)} pases en la zona · ${formatNumber(row.matches, 0)} partidos</small>
    </div>
  `).join("");
}

function summarizeBy(rows, team, stage, fields, countField) {
  const grouped = new Map();
  rows.filter((row) => matchesScope(row, team, stage)).forEach((row) => {
    const key = [row.stage, ...fields.map((field) => row[field])].join("|");
    const group = grouped.get(key) || {
      stage: row.stage,
      ...Object.fromEntries(fields.map((field) => [field, row[field]])),
      [countField]: 0,
    };
    group[countField] += Number(row[countField]) || 0;
    grouped.set(key, group);
  });
  return [...grouped.values()];
}

function renderDefensive(rows, team, stage) {
  const aggregated = summarizeBy(rows, team, stage, ["action", "zone"], "actions")
    .sort((a, b) => b.actions - a.actions);
  renderBars("#defensive-summary", aggregated, {
    label: (row) => `${actionNames[row.action] || row.action} · ${zoneNames[row.zone] || row.zone}`,
    value: (row) => row.actions,
    detail: (row) => `${stageLabel(row.stage)} · acciones registradas`,
    emptyMessage: "No hay acciones defensivas disponibles.",
    limit: 9,
  });
}

function renderProgression(rows, team, stage) {
  const visible = rows.filter((row) => matchesScope(row, team, stage));
  const grouped = new Map();
  visible.forEach((row) => {
    const key = `${row.stage}|${row.zone}|${row.lane}`;
    const group = grouped.get(key) || {
      stage: row.stage, zone: row.zone, lane: row.lane,
      matches: 0, passes: 0, progressive_passes: 0, key_passes: 0,
    };
    group.matches += 1;
    group.passes += Number(row.passes) || 0;
    group.progressive_passes += Number(row.progressive_passes) || 0;
    group.key_passes += Number(row.key_passes) || 0;
    grouped.set(key, group);
  });
  const chartRows = [...grouped.values()].sort((a, b) => b.progressive_passes - a.progressive_passes);
  renderBars("#progression-summary", chartRows, {
    label: (row) => `${zoneNames[row.zone] || row.zone} · ${laneNames[row.lane] || row.lane}`,
    value: (row) => row.progressive_passes,
    detail: (row) => `${formatNumber(row.passes, 0)} pases · ${formatNumber(row.key_passes, 0)} clave · ${formatNumber(row.matches, 0)} registros de partido`,
    emptyMessage: "No hay progresión disponible.",
    limit: 9,
  });
}

function renderMatches(rows, team, stage) {
  const visible = rows.filter((row) => matchesScope(row, team, stage));
  renderTable("#match-table", [
    { key: "match_id", label: "Partido" },
    { key: "stage", label: "Etapa", render: (row) => escapeHtml(stageLabel(row.stage)) },
    { key: "passes", label: "Pases", render: (row) => formatNumber(row.passes, 0) },
    { key: "progressive_passes", label: "Progresivos", render: (row) => formatNumber(row.progressive_passes, 0) },
    { key: "high_recoveries", label: "Rec. altas", render: (row) => formatNumber(row.high_recoveries, 0) },
    { key: "xg", label: "xG", render: (row) => formatNumber(row.xg, 2) },
    { key: "ppda", label: "PPDA", render: (row) => formatNumber(row.ppda, 2) },
  ], visible, "No hay partidos disponibles.");
}

function renderContext(rows, team, stage) {
  const visible = rows.filter((row) => matchesScope(row, team, stage));
  const container = document.querySelector("#context-summary");
  if (!visible.length) {
    container.innerHTML = '<p class="empty">No hay datos de contexto disponibles.</p>';
    return;
  }
  const stateLabels = { ganando: "Ganando", empatando: "Empatando", perdiendo: "Perdiendo" };
  container.innerHTML = visible.map((row) => `
    <article class="context-card">
      <span class="context-state">${escapeHtml(stateLabels[row.estado] || row.estado)}</span>
      <strong>${formatNumber(row.matches, 0)} <small>partidos</small></strong>
      <div class="bar-track"><span style="width:${Math.min(100, row.matches / Math.max(...visible.map((item) => item.matches)) * 100)}%"></span></div>
      <p>Diferencia media de gol: <b>${formatNumber(row.average_goal_difference, 2)}</b></p>
      <small>${formatNumber(row.event_rows, 0)} ventanas observadas · ${escapeHtml(stageLabel(row.stage))}</small>
    </article>
  `).join("");
}

function renderVenue(rows, opponents, team, stage) {
  const filtered = rows.filter((row) => matchesScope(row, team, stage));
  const columns = [
    { key: "stage", label: "Etapa", render: (row) => escapeHtml(stageLabel(row.stage)) },
    { key: "display", label: "Localía / rival" },
    { key: "matches", label: "Partidos", render: (row) => formatNumber(row.matches, 0) },
    { key: "average_xg", label: "xG medio", render: (row) => formatNumber(row.average_xg, 2) },
    { key: "average_ppda", label: "PPDA medio", render: (row) => formatNumber(row.average_ppda, 2) },
  ];
  const combined = filtered.map((row) => ({
    ...row,
    display: row.venue === "home" ? "Local" : "Visitante",
  }));
  const enemyRows = opponents.filter((row) => matchesScope(row, team, stage))
    .sort((a, b) => b.matches - a.matches)
    .slice(0, 10)
    .map((row) => ({ ...row, display: `vs. ${row.opponent}` }));
  renderTable("#venue-summary", columns, [...combined, ...enemyRows],
    "No hay datos de localía o rival disponibles.");
}

function renderTransitions(rows, team, stage) {
  const visible = rows.filter((row) => matchesScope(row, team, stage))
    .sort((a, b) => b.xg_generated - a.xg_generated);
  renderBars("#transition-summary", visible, {
    label: (row) => zoneNames[row.zona_recuperacion] || row.zona_recuperacion,
    value: (row) => row.xg_generated,
    detail: (row) => `${formatNumber(row.transitions, 0)} secuencias · ${formatNumber(row.shots, 0)} tiros · ${formatNumber(row.goals, 0)} goles · ${formatNumber(row.average_seconds_to_shot, 1)} s al tiro`,
    emptyMessage: "No hay transiciones disponibles.",
    limit: 6,
  });
}

function renderPossessions(rows, team, stage) {
  const visible = rows.filter((row) => matchesScope(row, team, stage));
  const container = document.querySelector("#possession-summary");
  if (!visible.length) {
    container.innerHTML = '<p class="empty">No hay resumen de posesiones disponible.</p>';
    return;
  }
  container.innerHTML = `
    <div class="possession-grid">
      ${visible.map((row) => `
        <div class="possession-card">
          <span class="panel-label">${escapeHtml(stageLabel(row.stage))}</span>
          <strong class="possession-total">${formatNumber(row.possessions, 0)}</strong>
          <small>posesiones registradas</small>
          <div class="possession-metrics">
            <div><b>${formatNumber(row.average_duration_seconds, 1)} s</b><span>duración media</span></div>
            <div><b>${formatNumber(row.average_passes, 1)}</b><span>pases por posesión</span></div>
            <div><b>${formatNumber(row.average_carries, 1)}</b><span>conducciones</span></div>
            <div><b>${formatNumber(row.shots, 0)}</b><span>tiros totales</span></div>
          </div>
        </div>
      `).join("")}
      </div>
  `;
}

function renderPlayerSelect(report, team, stage) {
  const select = document.querySelector("#player-filter");
  const previous = select.value;
  select.replaceChildren(new Option("Todos", "all"));
  const players = uniquePlayers(report.player_summary
    .filter((row) => matchesScope(row, team, stage)))
    .sort((a, b) => a.player.localeCompare(b.player, "es"));
  players.forEach((player) => {
    const position = positionNames[player.position] || "Posición no disponible";
    const option = new Option(`${player.player} · ${position}`, player.player_id);
    select.append(option);
  });
  select.value = players.some((player) => player.player_id === previous) ? previous : "all";
}

function enableSvgNavigation(svg, controls) {
  const bounds = svg.viewBox.baseVal;
  const original = {
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height,
  };
  const view = { ...original };
  const minWidth = original.width / 5;
  const maxWidth = original.width;
  const applyView = () => {
    svg.setAttribute("viewBox", `${view.x} ${view.y} ${view.width} ${view.height}`);
  };
  const zoomAt = (factor, anchorX = 0.5, anchorY = 0.5) => {
    const nextWidth = Math.max(minWidth, Math.min(maxWidth, view.width * factor));
    const scale = nextWidth / view.width;
    const nextHeight = view.height * scale;
    const pointX = view.x + view.width * anchorX;
    const pointY = view.y + view.height * anchorY;
    view.x = pointX - nextWidth * anchorX;
    view.y = pointY - nextHeight * anchorY;
    view.width = nextWidth;
    view.height = nextHeight;
    applyView();
  };

  svg.addEventListener("wheel", (event) => {
    event.preventDefault();
    const rect = svg.getBoundingClientRect();
    zoomAt(
      event.deltaY < 0 ? 0.85 : 1 / 0.85,
      Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
      Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
    );
  }, { passive: false });

  svg.addEventListener("dblclick", (event) => {
    event.preventDefault();
    zoomAt(0.7);
  });

  let drag;
  svg.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    const bounds = svg.getBoundingClientRect();
    drag = {
      pointerId: event.pointerId,
      clientX: event.clientX,
      clientY: event.clientY,
      viewX: view.x,
      viewY: view.y,
      width: view.width,
      height: view.height,
      bounds,
    };
    svg.setPointerCapture(event.pointerId);
  });
  svg.addEventListener("pointermove", (event) => {
    if (!drag || drag.pointerId !== event.pointerId) return;
    view.x = drag.viewX - (event.clientX - drag.clientX) * drag.width / drag.bounds.width;
    view.y = drag.viewY - (event.clientY - drag.clientY) * drag.height / drag.bounds.height;
    applyView();
  });
  const finishDrag = (event) => {
    if (drag?.pointerId === event.pointerId) drag = undefined;
  };
  svg.addEventListener("pointerup", finishDrag);
  svg.addEventListener("pointercancel", finishDrag);

  svg.addEventListener("keydown", (event) => {
    const panX = view.width * 0.1;
    const panY = view.height * 0.1;
    if (event.key === "+" || event.key === "=") zoomAt(0.8);
    else if (event.key === "-") zoomAt(1.25);
    else if (event.key === "ArrowLeft") view.x -= panX;
    else if (event.key === "ArrowRight") view.x += panX;
    else if (event.key === "ArrowUp") view.y -= panY;
    else if (event.key === "ArrowDown") view.y += panY;
    else if (event.key === "Home") {
      view.x = original.x;
      view.y = original.y;
      view.width = original.width;
      view.height = original.height;
    } else return;
    event.preventDefault();
    applyView();
  });

  controls.querySelector("[data-zoom-in]").addEventListener("click", () => zoomAt(0.8));
  controls.querySelector("[data-zoom-out]").addEventListener("click", () => zoomAt(1.25));
  controls.querySelector("[data-zoom-reset]").addEventListener("click", () => {
    view.x = original.x;
    view.y = original.y;
    view.width = original.width;
    view.height = original.height;
    applyView();
  });
}

function zoomControls(label) {
  return `<div class="map-controls" role="group" aria-label="${escapeHtml(label)}">
    <button type="button" data-zoom-in aria-label="Acercar" title="Acercar">+</button>
    <button type="button" data-zoom-out aria-label="Alejar" title="Alejar">−</button>
    <button type="button" data-zoom-reset aria-label="Restablecer vista" title="Restablecer">↺</button>
  </div>`;
}

function renderPlayerViews(report, team, stage, playerId) {
  const activity = filterPlayerActivity(report.player_activity_map, team, stage, playerId);
  const cells = new Map();
  activity.forEach((row) => {
    const key = `${row.grid_x},${row.grid_y}`;
    cells.set(key, (cells.get(key) || 0) + Number(row.events));
  });
  const peak = Math.max(0, ...cells.values());
  const map = document.querySelector("#player-activity-map");
  if (!cells.size) {
    map.innerHTML = '<p class="empty">No hay actividad disponible para esta selección.</p>';
  } else {
    const cellMarkup = [];
    for (let y = 0; y < 8; y += 1) {
      for (let x = 0; x < 12; x += 1) {
        const value = cells.get(`${x},${y}`) || 0;
        const intensity = peak ? value / peak : 0;
        if (value) {
          cellMarkup.push(`<rect x="${x * 10}" y="${y * 10}" width="10" height="10" class="heat-cell" opacity="${(0.12 + intensity * 0.78).toFixed(2)}"><title>Zona ${x + 1}, ${y + 1}: ${formatNumber(value, 0)} eventos</title></rect>`);
        }
      }
    }
    map.innerHTML = `
      <svg class="pitch activity-pitch" viewBox="0 0 120 80" role="img" aria-label="Mapa de actividad individual por zonas">
        <rect x="1" y="1" width="118" height="78" class="pitch-surface" />
        <g>${cellMarkup.join("")}</g>
        <path d="M60 1v78 M1 20h18v40H1 M119 20h-18v40h18 M19 29h8v22h-8 M101 29h-8v22h8" class="pitch-lines" />
        <circle cx="60" cy="40" r="12" class="pitch-lines" />
      </svg>
      <p class="map-caption">${formatNumber(activity.reduce((sum, row) => sum + Number(row.events), 0), 0)} eventos · intensidad relativa por celda; orientación original de la fuente</p>
    `;
  }

  const scopedNetwork = report.pass_network
    .filter((row) => matchesScope(row, team, stage));
  const selectedRows = report.player_summary.filter((row) =>
    row.player_id === playerId && matchesScope(row, team, stage)
  );
  const playerName = selectedRows[0]?.player;
  const playerMatches = selectedRows.reduce((sum, row) => sum + Number(row.matches || 0), 0);
  let centerName = playerName;
  if (!centerName && scopedNetwork.length) {
    const weights = new Map();
    scopedNetwork.forEach((row) => {
      weights.set(row.player, (weights.get(row.player) || 0) + Number(row.passes));
      weights.set(row.receiver, (weights.get(row.receiver) || 0) + Number(row.passes));
    });
    centerName = [...weights.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
  }
  const centerMatches = playerMatches || report.player_summary
    .filter((row) => row.player === centerName && matchesScope(row, team, stage))
    .reduce((sum, row) => sum + Number(row.matches || 0), 0);
  const nearby = aggregatePlayerPassConnections(scopedNetwork, centerName)
    .sort((a, b) => (b.outgoing + b.incoming) - (a.outgoing + a.incoming))
    .slice(0, 10);
  const networkContainer = document.querySelector("#player-pass-network");
  if (!nearby.length) {
    networkContainer.innerHTML = '<p class="empty">No hay conexiones de pase para esta selección.</p>';
  } else {
    const center = { x: 120, y: 180 };
    const maxPasses = Math.max(...nearby.map((edge) => edge.outgoing + edge.incoming));
    const nodes = nearby.map((edge, index) => {
      const spacing = nearby.length > 1 ? 312 / (nearby.length - 1) : 0;
      return { ...edge, x: 360, y: 24 + index * spacing };
    });
    const links = nodes.map((node) => {
      const directions = [
        { passes: node.outgoing, fromPlayer: true },
        { passes: node.incoming, fromPlayer: false },
      ].filter((direction) => direction.passes > 0);
      return directions.map((direction) => {
        const start = direction.fromPlayer ? center : node;
        const end = direction.fromPlayer ? node : center;
        const offset = directions.length > 1 ? 11 : 0;
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const length = Math.hypot(dx, dy) || 1;
        const controlX = (start.x + end.x) / 2 - (dy / length) * offset;
        const controlY = (start.y + end.y) / 2 + (dx / length) * offset;
        const average = centerMatches ? direction.passes / centerMatches : null;
        const directionLabel = direction.fromPlayer ? "Pases hacia" : "Pases recibidos de";
        const tooltip = `${directionLabel} ${node.name}: ${formatNumber(direction.passes, 0)} pases`
          + `${centerMatches ? ` en ${formatNumber(centerMatches, 0)} partidos del jugador (${formatNumber(average, 1)} por partido)` : ""}`;
        return `<path d="M ${start.x} ${start.y} Q ${controlX} ${controlY} ${end.x} ${end.y}"
          class="network-link" stroke-width="${1 + direction.passes / maxPasses * 5}"
          marker-end="url(#network-arrowhead)"><title>${escapeHtml(tooltip)}</title></path>`;
      }).join("");
    }).join("");
    const nodeMarkup = nodes.map((node) => `
      <g class="network-node">
        <circle cx="${node.x}" cy="${node.y}" r="${5 + (node.outgoing + node.incoming) / maxPasses * 3}">
          <title>${escapeHtml(node.name)} · hacia: ${formatNumber(node.outgoing, 0)} · desde: ${formatNumber(node.incoming, 0)}</title>
        </circle>
        <text x="${node.x + 20}" y="${node.y + 4}" text-anchor="start">${escapeHtml(node.name)}</text>
      </g>
    `).join("");
    networkContainer.innerHTML = `
      <div class="interactive-map-wrap">
        ${zoomControls("Controles de la red de pases")}
        <svg class="network-svg interactive-map" viewBox="0 0 760 360" role="img" aria-label="Conexiones de pase de ${escapeHtml(centerName)}" tabindex="0">
          <defs>
            <marker id="network-arrowhead" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" class="network-arrowhead"></path>
            </marker>
          </defs>
          <g>${links}</g><g>${nodeMarkup}</g>
          <g class="network-center">
            <circle cx="${center.x}" cy="${center.y}" r="31"></circle>
            <text x="${center.x}" y="${center.y + 4}" text-anchor="middle">Jugador</text>
            <text class="network-center-name" x="${center.x}" y="${center.y + 55}" text-anchor="middle">${escapeHtml(centerName)}</text>
          </g>
        </svg>
      </div>
    `;
    enableSvgNavigation(networkContainer.querySelector(".network-svg"), networkContainer);
  }
}

function renderTeamGoals(rows, team, stage) {
  const goals = filterTeamGoals(rows, team, stage);
  const container = document.querySelector("#team-goal-map");
  if (!goals.length) {
    container.innerHTML = '<p class="empty">No hay goles con coordenadas disponibles para esta selección.</p>';
    return;
  }
  const points = goals.map((row) => {
    const x = Math.min(120, Math.max(0, Number(row.x)));
    const y = Math.min(80, Math.max(0, Number(row.y)));
    return `<circle cx="${x}" cy="${y}" r="1.45" aria-label="${escapeHtml(row.shooting_team)} · ${escapeHtml(row.player || "rematador")}" />`;
  }).join("");
  container.innerHTML = `
    <div class="interactive-map-wrap">
      ${zoomControls("Controles del mapa de goles")}
      <svg class="pitch shot-pitch interactive-map" viewBox="0 0 120 80" role="img" aria-label="${goals.length} goles del equipo en coordenadas StatsBomb" tabindex="0">
        <rect x="1" y="1" width="118" height="78" rx="2" class="pitch-surface" />
        <path d="M60 1v78 M1 20h18v40H1 M119 20h-18v40h18 M19 29h8v22h-8 M101 29h-8v22h8" class="pitch-lines" />
        <circle cx="60" cy="40" r="12" class="pitch-lines" />
        <g class="goal-points">${points}</g>
      </svg>
    </div>
    <p class="map-caption">${formatNumber(goals.length, 0)} goles · equipo completo · usa los controles, la rueda o doble clic para acercar y arrastra para mover</p>
  `;
  enableSvgNavigation(container.querySelector(".shot-pitch"), container);
}

function renderMetadata(metadata = {}, matches = []) {
  const description = document.querySelector("#scope-description");
  const count = matches.filter((row) => stageKeys.includes(row.stage)).length;
  description.innerHTML =
    `<strong>${formatNumber(count, 0)} partidos.</strong> Comparación en tres etapas: Pre-América, América campeón y post campeonatos.`;
  description.classList.remove("loading");

  document.querySelector("#report-limitations").innerHTML = `
    <li class="scope-sample"><strong>${formatNumber(count, 0)} partidos</strong><span>en las tres etapas seleccionadas</span></li>
    ${(metadata.limitations || []).map((limitation) => `<li>${escapeHtml(limitation)}</li>`).join("")}
  `;
  document.querySelector("#metric-definitions").innerHTML = Object.entries(metadata.definitions || {})
    .map(([term, definition]) => `
      <div>
        <dt>${escapeHtml(definitionNames[term] || term)}</dt>
        <dd>${escapeHtml(definition)}</dd>
      </div>
    `).join("");
}

function renderSetPieces(rows, team, stage) {
  const visible = filterTeamSetPieces(rows, team, stage).sort((a, b) => b.shots - a.shots);
  renderBars("#team-set-pieces", visible, {
    label: (row) => `${row.role === "defensive" ? "Defensa" : "Ataque"} · ${row.pattern === "From Corner" ? "Córner" : row.pattern === "From Free Kick" ? "Tiro libre" : "Saque de banda"}`,
    value: (row) => row.shots,
    detail: (row) => `${stageLabel(row.stage)} · ${formatNumber(row.possessions, 0)} secuencias · ${formatNumber(row.goals, 0)} goles · ${formatNumber(row.xg, 2)} xG`,
    emptyMessage: "No hay datos colectivos de balón parado para esta selección.",
    limit: 12,
  });
}

function renderDashboard(report) {
  const stage = document.querySelector("#stage-filter").value;
  const team = document.querySelector("#team-filter").value;
  renderMetadata(report.metadata || {}, report.matches || []);
  renderPlayerSelect(report, team, stage);
  const playerId = document.querySelector("#player-filter").value;

  renderStageSummary(report.stage_summary, team, stage);
  renderFormation(report.formation_summary, team, stage);
  renderDecisions(report.decision_summary, team, stage);
  renderMatches(report.matches, team, stage);
  renderVariability(report.variability_summary, team, stage);
  renderTerritorial(report.territorial_proxy, team, stage);
  renderDefensive(report.defensive_summary, team, stage);
  renderProgression(report.progression_summary, team, stage);
  renderContext(report.context_summary, team, stage);
  renderVenue(report.venue_summary, report.opponent_summary, team, stage);
  renderTransitions(report.transition_summary, team, stage);
  renderPossessions(report.possession_summary, team, stage);
  renderPlayerViews(report, team, stage, playerId);
  renderTeamGoals(report.shot_map, team, stage);
  renderSetPieces(report.set_piece_summary, team, stage);
}

async function startDashboard() {
  const response = await fetch("./report_data.json");
  if (!response.ok) throw new Error("No se pudo cargar el reporte actualizado.");
  const report = await response.json();

  fillSelect("#stage-filter", stageKeys, stageNames);
  fillSelect("#team-filter", [...new Set(report.matches.map((row) => row.team))].sort());

  ["#stage-filter", "#team-filter", "#player-filter"].forEach((selector) => {
    document.querySelector(selector).addEventListener("change", () => renderDashboard(report));
  });
  renderDashboard(report);
}

startDashboard().catch((error) => {
  document.querySelectorAll(".loading").forEach((element) => {
    element.className = "error";
    element.textContent = error.message;
  });
});
