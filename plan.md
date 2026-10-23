# Plan de ampliación del análisis táctico de Jardine

## Progreso

- [x] Pipeline con métricas por partido, etapa y contexto.
- [x] Variabilidad con `n`, media, desviación y cuantiles.
- [x] Progresión por zona/carril y perfil defensivo observable.
- [x] Proxy territorial etiquetado, sin presentarlo como Field Tilt.
- [x] Exportaciones CSV/JSON y contrato `report_data.json`.
- [x] Dashboard con variabilidad, territorio, defensa y progresión.
- [x] Pruebas dirigidas y validación de sintaxis.
- [ ] Regenerar con la base real cuando `hackathon.db` esté disponible.

## Problema y enfoque

Completar los componentes faltantes de la rúbrica usando únicamente la
información disponible en `hackathon.db`, sin implementar OBV por ahora. El
trabajo ampliará el pipeline reproducible, documentará qué métricas son
oficiales y cuáles son proxies operativos, y hará visibles los resultados en el
dashboard.

La regla central será no inventar información ausente: Field Tilt se reportará
como proxy territorial si no puede normalizarse la dirección de ataque; el
balón parado defensivo se analizará mediante acciones y resultados observables,
no mediante asignaciones de marca que la base no contiene.

## Alcance

### Incluido

- Variabilidad y consistencia por partido, etapa, marcador, localía y rival.
- Organización defensiva mediante volumen, zonas y tipo de acciones defensivas.
- Roles y uso de jugadores mediante ventanas, posiciones, formaciones y
  sustituciones.
- Balón parado ofensivo y defensivo observable.
- Construcción y progresión por zonas, carriles y patrones de pase.
- Proxy de control territorial documentado, sin llamarlo Field Tilt oficial.
- Cambios posteriores a sustituciones y cambios de sistema cuando exista
  suficiente información.
- Nuevas exportaciones CSV/JSON, documentación, dashboard y pruebas.

### Excluido

- OBV o cualquier modelo de valor de posesión.
- Asignaciones individuales de marcaje en balón parado.
- Afirmaciones de causalidad o de intención del entrenador no observables.
- Modificación de los datos crudos de SQLite.

## Enfoque técnico

1. Auditar las columnas y cobertura ya disponibles para evitar duplicar
   métricas existentes.
2. Añadir funciones pequeñas y testeables al pipeline de Pandas:
   progresión zonal, control territorial proxy, perfil defensivo, balón parado,
   consistencia/variabilidad y respuesta posterior a decisiones.
3. Exportar cada agregado con denominadores, tamaño de muestra y etiquetas de
   limitación cuando corresponda.
4. Actualizar `docs/data_dictionary.md`, `docs/analysis_report.md` y `plan.md`
   del repositorio con definiciones y límites.
5. Mostrar en el dashboard las nuevas salidas, manteniendo la interfaz sencilla
   y sin dependencias externas.
6. Ejecutar pruebas unitarias, regenerar salidas con la base real y verificar
   que los conteos y llaves sean consistentes.

## Entregables esperados

- Pipeline ampliado en `jardine_analysis/pipeline.py`.
- Exportaciones nuevas o ampliadas en `outputs/`.
- Pruebas de cada métrica nueva y de sus casos límite.
- Diccionario de datos y reporte narrativo actualizados.
- Dashboard con secciones para variabilidad, control territorial proxy,
  organización defensiva y balón parado.
- Plan del repositorio actualizado con progreso y limitaciones.

## Decisiones técnicas iniciales

- Los promedios se acompañarán de `matches` y, cuando sea útil, dispersión
  (`std` o rango intercuartílico) para no ocultar tamaños de muestra.
- La consistencia se medirá como estabilidad entre partidos dentro de una
  etapa; la variabilidad se medirá como dispersión y cambios por contexto.
- El proxy territorial usará eventos espaciales comparables y se etiquetará
  explícitamente como aproximación por la falta de orientación normalizada.
- El balón parado defensivo usará presiones, despejes, bloqueos, intercepciones,
  recuperaciones, tiros y goles asociados a patrones de reanudación.
- Si una métrica no tiene cobertura suficiente, se exportará como no disponible
  con la razón documentada, no como cero.

## Validación

- Pruebas dirigidas y suite completa.
- Regeneración de todos los outputs desde `hackathon.db`.
- Comprobación de que no se pierdan los 183 partidos focales.
- Revisión de valores nulos, denominadores cero, rangos espaciales y
  duplicados.
- Smoke test del dashboard mediante servidor HTTP local.
# Plan de implementación: análisis longitudinal de Jardine

## Problema y enfoque

Implementar todo lo que pueda sostenerse con la base actual `hackathon.db` para
explicar la evolución táctica de André Jardine a través de múltiples partidos,
no de un encuentro aislado. El análisis debe identificar patrones recurrentes,
tendencias del entrenador, ajustes según rival/marcador/localía y diferencias
entre partidos o momentos del juego.

La solución conservará el pipeline reproducible en Pandas/SQLite, usará
métricas observables y proxies claramente etiquetados, y entregará datos
tabulados para la interfaz. No se modificarán los datos crudos ni se afirmará
causalidad cuando la base solo permita asociaciones antes/después.

## Límites acordados

- Incluir toda la muestra disponible y comparar etapas, equipos y contextos.
- Mantener como eje narrativo la evolución de Jardine, con América como etapa
  principal y Atlético de San Luis como referencia previa.
- Analizar rival, marcador, localía, periodo del partido, formación y cambios
  observables cuando exista cobertura.
- Excluir OBV.
- No presentar el proxy territorial como Field Tilt oficial.
- No inferir marcaje individual, defensa zonal/man-to-man, intención interna ni
  causalidad de una sustitución.
- No modificar `hackathon.db`.
- Tratar `partidos.fecha` y `partidos.competencia` como datos incompletos y
  conservar la clasificación de etapas como contexto documentado.

## Todos de implementación

1. **Consolidar la fuente oficial**
   - Integrar la ampliación analítica en la rama de trabajo principal.
   - Revisar cambios existentes y conservar solo artefactos relacionados.
   - Decidir que `dist/` es la interfaz disponible mientras no exista el
     proyecto fuente Angular.

2. **Auditar y normalizar la muestra**
   - Validar los 183 partidos focales, equipos, identificadores y duplicados.
   - Documentar cobertura, campos ausentes, periodo y reglas de etapas.
   - Validar rangos espaciales y declarar la limitación de orientación.

3. **Completar métricas longitudinales por partido**
   - Mantener pases, progresión, tiros, goles, xG, PPDA, presión,
     recuperaciones y transiciones.
   - Añadir o reforzar denominadores, tamaños de muestra, medias, dispersión y
     valores no disponibles.
   - Exportar métricas por partido, etapa y contexto.

4. **Medir patrones ofensivos recurrentes**
   - Comparar construcción, progresión por zonas/carriles, cambios de
     orientación, creación de ocasiones y secuencias de tiro.
   - Separar volumen de eficiencia y evitar interpretar zonas brutas como
     tercios ofensivos sin normalización.

5. **Medir patrones defensivos y transiciones**
   - Analizar PPDA operativo, presiones, recuperaciones, intercepciones,
     despejes, bloqueos, duelos y riesgo observable.
   - Relacionar recuperaciones con tiros/xG posteriores.
   - Comparar comportamientos por marcador y tramo del partido.

6. **Analizar ajustes contextuales**
   - Cruzar métricas con rival, localía, resultado, estado del marcador,
     periodo y formación cuando estén disponibles.
   - Medir diferencias entre partidos y dentro del partido mediante ventanas.
   - Reportar tamaños de muestra para cada comparación y marcar celdas
     insuficientes como no disponibles.

7. **Analizar decisiones observables**
   - Resumir formaciones iniciales, cambios de sistema y sustituciones.
   - Implementar comparación descriptiva antes/después de sustituciones y
     cambios, controlando ventana, marcador y duración.
   - Etiquetar el resultado como asociación descriptiva, no efecto causal.

8. **Completar roles, balón parado y consistencia**
   - Usar posiciones, ventanas de cinco minutos, participación y formaciones
     para describir uso de jugadores.
   - Resumir balón parado ofensivo/defensivo mediante acciones y resultados
     observables, sin asignaciones de marca.
   - Presentar consistencia con n, media, desviación o cuantiles cuando sea
     posible, sin ocultar variabilidad entre partidos.

9. **Actualizar contrato de datos y documentación**
   - Mantener CSV/JSON reproducibles y `report_data.json` consistente.
   - Actualizar `docs/data_dictionary.md`, `docs/analysis_report.md`,
     `GLOSSARY.md` y `plan.md`.
   - Para cada hallazgo documentar población, periodo, denominador, baseline,
     incertidumbre, limitación y comando de reproducción.

10. **Actualizar la interfaz oficial**
    - Mostrar la historia por etapas y contextos, no solo una tabla de
      partidos.
    - Integrar visualizaciones/tablas de ofensiva, defensa, transiciones,
      decisiones, variabilidad y balón parado.
    - Migrar las pruebas que aún apuntan al dashboard borrador para validar
      `dist/`, o restaurar explícitamente el dashboard solo si se decide que
      sigue siendo una interfaz soportada.
    - Evitar edición manual del bundle Angular sin fuente.

11. **Validar y preparar la presentación**
    - Ejecutar pruebas unitarias y contrato de salidas.
    - Regenerar outputs desde `hackathon.db`.
    - Comprobar 183 partidos únicos, llaves, rangos, nulos y denominadores.
    - Ejecutar smoke test HTTP de `dist/` y revisar que las secciones sean
      visibles y no estén ocultas por caché o por una carga parcial.
    - Seleccionar tres a cinco hallazgos longitudinales defendibles para el
      jurado, cada uno con evidencia y limitación explícita.

## Entregables

- Pipeline reproducible ampliado.
- CSV/JSON por partido, etapa y contexto.
- `report_data.json` como contrato de consumo.
- Documentación metodológica y glosario actualizado.
- Interfaz `dist/` con la historia longitudinal visible.
- Suite de pruebas verde y comandos de reproducción.
- Catálogo final de hallazgos con población, denominador y límites.

## Decisiones técnicas del implementador

- Se usará el checkout principal como destino de integración, confirmado por el
  usuario.
- Se tratará el worktree `expanded-tactical-analysis` como referencia de
  cambios ya realizados, no como motivo para duplicar funciones.
- Los valores faltantes se mostrarán como `—`/no disponible, nunca como cero
  implícito.
- La interfaz priorizará tablas y comparaciones honestas sobre efectos
  decorativos.
- Si una dimensión no tiene evidencia suficiente, se conservará como brecha
  documentada en lugar de fabricar una métrica.
- Se mantienen las exclusiones confirmadas: OBV, Field Tilt oficial,
  marcaje individual y causalidad no observable.

## Riesgos y controles

- **Orientación del ataque:** no convertir coordenadas brutas en zonas
  direccionales sin una regla validada.
- **Etapas históricas:** no llamar campeonato a una etapa inferida solo por
  año/equipo.
- **Muestras pequeñas:** mostrar `n` y no generalizar desde pocos partidos.
- **Causalidad:** describir asociaciones antes/después y ajustar por marcador
  cuando sea posible.
- **Interfaz compilada:** no prometer una integración Angular mantenible sin
  recuperar `src/`, `angular.json` y `package.json`.
