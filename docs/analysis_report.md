# Primera lectura narrativa

## Reproducción

```bash
PYTHONPATH=. python -m jardine_analysis.pipeline \
  --database hackathon.db \
  --output-dir outputs
```

## Hallazgos candidatos

1. **La estructura no basta para explicar el modelo.** La distribución de
   `formation_summary.csv` muestra que América usa varias formaciones iniciales;
   la historia debe cruzarlas con presión, progresión, transiciones y estado
   del marcador.
2. **El perfil defensivo cambia entre etapas.** En la primera agregación, las
   presiones y presiones altas por partido de América son mayores después de
   2024 (`n=58`) que en el contexto América hasta 2024 (`n=70`). Es una
   asociación descriptiva, no una explicación causal.
3. **La línea base tiene que conservarse visible.** Atlético de San Luis aporta
   `n=55` partidos focales previos; sus promedios sirven como contexto, pero
   deben ajustarse por rival, exposición y estado del marcador antes de una
   conclusión fuerte.

4. **La zona de recuperación cambia el valor de la transición.**
   `transition_summary.csv` permite comparar no solo cuántas recuperaciones
   existen, sino cuántas terminan en tiro, gol o `xG` según la zona.

5. **Los ajustes durante el partido son una dimensión separada de la
   formación inicial.** `decision_summary.csv` permite estudiar sustituciones y
   cambios de formación posteriores al inicio sin llamarlos automáticamente
   decisiones causales de Jardine.

## Límites actuales

- `partidos.competencia` y `partidos.fecha` están vacíos; las etapas son
  contextuales, no una asignación definitiva de torneo.
- Las coordenadas no están normalizadas por dirección de ataque.
- PPDA usa pases rivales y acciones defensivas con `x <= 72`; presiones y
  recuperaciones altas usan `x >= 80`.
- `context_summary.csv` resume filas de eventos de estado; `matches` muestra
  cuántos partidos aparecen y `event_rows` cuántos registros aportan.
- Los resultados son observacionales: no demuestran que una decisión causó un
  campeonato.
- `variability_summary.csv` conserva `n`, media, desviación y cuantiles para
  evitar conclusiones basadas solo en promedios.
- `territorial_proxy.csv` usa eventos con `x_inicio >= 60`; es una
  aproximación territorial y no Field Tilt oficial.
- `progression_summary.csv` y `defensive_summary.csv` separan zona/carril y
  tipo de acción, pero sus coordenadas siguen siendo crudas.

## Reproducción de salidas ampliadas

```bash
PYTHONPATH=. python -m jardine_analysis.pipeline \
  --database hackathon.db --output-dir outputs
```

La base `hackathon.db` no forma parte del repositorio y debe estar disponible
localmente para regenerar los agregados completos.
