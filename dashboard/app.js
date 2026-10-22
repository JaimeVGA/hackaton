const DATA_PATH = "../outputs/";

const stageNames = {
  pre_america: "Antes del América",
  america_championship_context: "América · etapa principal",
  post_championship_context: "Después de los campeonatos",
};

const formatNumber = (value, decimals = 1) => {
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString("es-MX", { maximumFractionDigits: decimals })
    : "—";
};

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) return [];
  const headers = lines[0].split(",");
  return lines.slice(1).map((line) => {
    const values = line.split(",");
    return headers.reduce((row, header, index) => {
      row[header] = values[index] ?? "";
      return row;
    }, {});
  });
}

async function loadCsv(filename) {
  const response = await fetch(`${DATA_PATH}${filename}`);
  if (!response.ok) throw new Error(`No se pudo cargar ${filename}`);
  return parseCsv(await response.text());
}

function renderStageSummary(rows, filter) {
  const container = document.querySelector("#stage-summary");
  const visible = filter === "all" ? rows : rows.filter((row) => row.stage === filter);
  if (!visible.length) {
    container.innerHTML = '<p class="empty">No hay datos para esta etapa.</p>';
    return;
  }
  container.innerHTML = visible.map((row) => `
    <article class="stage-card">
      <h3>${escapeHtml(stageNames[row.stage] || row.stage)}</h3>
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

function renderTable(containerId, columns, rows, emptyMessage) {
  const container = document.querySelector(containerId);
  if (!rows.length) {
    container.innerHTML = `<p class="empty">${emptyMessage}</p>`;
    return;
  }
  container.innerHTML = `
    <table>
      <thead><tr>${columns.map((column) => `<th>${column.label}</th>`).join("")}</tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr>${columns.map((column) => `<td>${column.render ? column.render(row) : escapeHtml(row[column.key])}</td>`).join("")}</tr>
        `).join("")}
      </tbody>
    </table>
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

async function startDashboard() {
  const [stages, matches, formations, decisions, variability, territorial, defensive, progression] = await Promise.all([
    loadCsv("stage_summary.csv"),
    loadCsv("match_metrics.csv"),
    loadCsv("formation_summary.csv"),
    loadCsv("decision_summary.csv"),
    loadCsv("variability_summary.csv"),
    loadCsv("territorial_proxy.csv"),
    loadCsv("defensive_summary.csv"),
    loadCsv("progression_summary.csv"),
  ]);

  fillSelect("#stage-filter", [...new Set(stages.map((row) => row.stage))], stageNames);
  fillSelect("#team-filter", [...new Set(matches.map((row) => row.team))]);

  const updateStages = () =>
    renderStageSummary(stages, document.querySelector("#stage-filter").value);
  document.querySelector("#stage-filter").addEventListener("change", updateStages);
  document.querySelector("#team-filter").addEventListener("change", () => {
    renderMatches(matches, document.querySelector("#team-filter").value);
  });

  updateStages();
  renderFormations(formations);
  renderDecisions(decisions);
  renderVariability(variability);
  renderTerritorial(territorial);
  renderDefensive(defensive);
  renderProgression(progression);
  renderMatches(matches, "all");
}

function renderFormations(rows) {
  renderTable("#formation-summary", [
    { key: "stage", label: "Etapa", render: (row) => escapeHtml(stageNames[row.stage] || row.stage) },
    { key: "formacion", label: "Formación" },
    { key: "matches", label: "Partidos", render: (row) => formatNumber(row.matches, 0) },
  ], rows, "No hay formaciones disponibles.");
}

function renderDecisions(rows) {
  renderTable("#decision-summary", [
    { key: "stage", label: "Etapa", render: (row) => escapeHtml(stageNames[row.stage] || row.stage) },
    { key: "substitution_events", label: "Sustituciones", render: (row) => formatNumber(row.substitution_events, 0) },
    { key: "formation_change_events", label: "Cambios de sistema", render: (row) => formatNumber(row.formation_change_events, 0) },
  ], rows, "No hay decisiones disponibles.");
}

function renderVariability(rows) {
  renderTable("#variability-summary", [
    { key: "stage", label: "Etapa", render: (row) => escapeHtml(stageNames[row.stage] || row.stage) },
    { key: "metric", label: "Métrica" },
    { key: "matches", label: "n", render: (row) => formatNumber(row.matches, 0) },
    { key: "mean", label: "Media", render: (row) => formatNumber(row.mean, 2) },
    { key: "std", label: "Desv.", render: (row) => formatNumber(row.std, 2) },
  ], rows.slice(0, 30), "No hay variabilidad disponible.");
}

function renderTerritorial(rows) {
  renderTable("#territorial-summary", [
    { key: "stage", label: "Etapa", render: (row) => escapeHtml(stageNames[row.stage] || row.stage) },
    { key: "team", label: "Equipo" },
    { key: "spatial_events", label: "Eventos", render: (row) => formatNumber(row.spatial_events, 0) },
    { key: "proxy_share", label: "Cuota", render: (row) => formatNumber(Number(row.proxy_share) * 100, 1) + "%" },
  ], rows.slice(0, 30), "No hay proxy territorial disponible.");
}

function renderDefensive(rows) {
  renderTable("#defensive-summary", [
    { key: "stage", label: "Etapa", render: (row) => escapeHtml(stageNames[row.stage] || row.stage) },
    { key: "action", label: "Acción" },
    { key: "zone", label: "Zona" },
    { key: "actions", label: "Acciones", render: (row) => formatNumber(row.actions, 0) },
  ], rows.slice(0, 30), "No hay acciones defensivas disponibles.");
}

function renderProgression(rows) {
  renderTable("#progression-summary", [
    { key: "stage", label: "Etapa", render: (row) => escapeHtml(stageNames[row.stage] || row.stage) },
    { key: "zone", label: "Zona" },
    { key: "lane", label: "Carril" },
    { key: "passes", label: "Pases", render: (row) => formatNumber(row.passes, 0) },
    { key: "progressive_passes", label: "Progresivos", render: (row) => formatNumber(row.progressive_passes, 0) },
  ], rows.slice(0, 30), "No hay progresión disponible.");
}

function renderMatches(rows, team) {
  const visible = team === "all" ? rows : rows.filter((row) => row.team === team);
  renderTable("#match-table", [
    { key: "match_id", label: "Partido" },
    { key: "stage", label: "Etapa", render: (row) => escapeHtml(stageNames[row.stage] || row.stage) },
    { key: "passes", label: "Pases", render: (row) => formatNumber(row.passes, 0) },
    { key: "progressive_passes", label: "Progresivos", render: (row) => formatNumber(row.progressive_passes, 0) },
    { key: "high_recoveries", label: "Rec. altas", render: (row) => formatNumber(row.high_recoveries, 0) },
    { key: "xg", label: "xG", render: (row) => formatNumber(row.xg, 2) },
    { key: "ppda", label: "PPDA", render: (row) => formatNumber(row.ppda, 2) },
  ], visible.slice(0, 40), "No hay partidos disponibles.");
}

startDashboard().catch((error) => {
  document.querySelectorAll(".loading").forEach((element) => {
    element.className = "error";
    element.textContent = error.message;
  });
});
