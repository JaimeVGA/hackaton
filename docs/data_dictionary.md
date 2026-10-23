# Diccionario inicial de métricas

Este documento describe la primera salida reproducible del análisis táctico de
Jardine. Las métricas se calculan desde `hackathon.db` con:

```bash
PYTHONPATH=. python -m jardine_analysis.pipeline \
  --database hackathon.db \
  --output-dir outputs
```

## Grano

- `match_metrics.csv` y `match_metrics.json`: una fila por partido y equipo
  focal.
- `stage_summary.csv`: promedio por etapa y equipo, con el número de partidos.
- `formation_summary.csv`: formación inicial por etapa y equipo.
- `context_summary.csv`: estados del marcador observados por etapa y equipo.
- `transition_summary.csv`: recuperaciones por zona y su continuación hacia
  tiros, goles y `xG`.
- `decision_summary.csv`: sustituciones y cambios de formación registrados por
  etapa y equipo.
- `variability_summary.csv`: media, desviación estándar, cuartiles y `n` por
  métrica, etapa y equipo.
- `progression_summary.csv`: pases, pases progresivos y pases clave por zona
  cruda y carril.
- `defensive_summary.csv`: acciones defensivas por tipo y zona de la fuente.
- `territorial_proxy.csv`: cuota espacial observable con etiqueta de proxy.
- `key_actions.csv`: los 25 partidos con mayor combinación de recuperaciones
  altas y `xG`.
- `stage_rules.json`: reglas y limitaciones de clasificación.

## Campos principales

| Campo | Definición |
|---|---|
| `match_id` | Identificador original del partido. |
| `team` | Equipo focal del registro. |
| `stage` | Etapa narrativa asignada por la regla documentada. |
| `passes` | Pases registrados del equipo focal. |
| `progressive_passes` | Pases marcados como progresivos por la fuente. |
| `key_passes` | Pases marcados como clave por la fuente. |
| `defensive_actions` | Acciones defensivas registradas del equipo focal. |
| `pressures` | Acciones de tipo `Pressure`. |
| `high_pressures` | `Pressure` en la zona `ATTACKING_THIRD` provista por la fuente. |
| `recoveries` | Acciones de tipo `Ball Recovery`. |
| `high_recoveries` | `Ball Recovery` en la zona `ATTACKING_THIRD` provista por la fuente. |
| `shots` | Remates registrados. |
| `goals` | Remates cuyo tipo es `Goal`. |
| `xg` | Suma del `xg` ya existente en la tabla `remates`. |
| `opponent_passes` | Pases del rival con coordenada cruda `x <= 72`. |
| `ppda_actions` | Acciones defensivas del equipo con `x <= 72`. |
| `ppda` | `opponent_passes / ppda_actions`; `null` si el denominador es cero. |
| `final_state` | Estado del marcador en el último evento disponible del equipo focal. |
| `final_goal_difference` | Diferencia de goles en ese último evento. |
| `proxy_share` | Proporción de eventos con `x_inicio >= 60` del equipo focal sobre ambos equipos; no es Field Tilt oficial. |
| `std`, `q1`, `q3` | Dispersión entre partidos; `std` no disponible cuando `n < 2`. |

`context_summary.csv` cuenta filas de eventos de `estado_partido` y también
reporta cuántos partidos aparecen en cada estado; no debe interpretarse como
porcentaje de tiempo sin normalizar por la duración de cada partido.

`decision_summary.csv` cuenta sustituciones y formaciones posteriores al minuto
0 como señales de ajuste observable. No prueba la intención del entrenador.

## Lectura responsable

Las etiquetas `pre_america`, `america_championship_context` y
`post_championship_context` son etapas narrativas de contexto. No equivalen
automáticamente a torneos: `partidos.competencia` y `partidos.fecha` están
vacíos en la base actual. La clasificación de campeonatos debe validarse antes
de usarla como afirmación histórica.

Las coordenadas no están normalizadas por dirección de ataque. Por eso las
presiones/recuperaciones altas usan la zona categórica de la fuente, mientras
que PPDA sigue siendo una primera definición operativa basada en `x <= 72`, no
una medida final lista para una conclusión fuerte.
Las zonas `0-40`, `40-80` y `80-120`, y los carriles, son particiones de
coordenadas crudas; no equivalen automáticamente a tercios ofensivos.
