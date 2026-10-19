# Plan: historia táctica de André Jardine con datos

## Problema y enfoque

Construir una narrativa basada en eventos de StatsBomb que explique cómo evolucionó
el equipo de André Jardine antes de llegar al América, durante la etapa de los
tres campeonatos consecutivos y después de ellos. El foco será explicar las
decisiones y principios de juego que ayudaron a ganar, no solo describir
resultados.

La base disponible es `hackathon.db`, una SQLite con 183 partidos y eventos
detallados. La ventana temporal identificada va de 2022 a 2026; América aparece
en 134 partidos, pero la tabla `partidos` tiene `competencia` y `fecha` sin
información útil para separar automáticamente los torneos. El análisis deberá
usar el identificador del partido y reglas documentadas para definir etapas,
validando cualquier fecha o campeonato contra una fuente confiable o una tabla
de configuración explícita.

## Alcance acordado

- Usar toda la ventana disponible como contexto de evolución.
- Dar prioridad narrativa a la etapa del América y sus campeonatos.
- Tratar el periodo previo y el posterior como comparación breve, no como
  historias independientes.
- No afirmar causalidad absoluta; presentar asociaciones medibles entre
  decisiones tácticas, patrones de juego y rendimiento.
- Usar Atlético de San Luis como línea base previa y América como etapa
  principal; el periodo posterior será contexto exploratorio.
- Explicar el esquema de juego como estructura, principios ofensivos,
  principios defensivos y adaptación al contexto, no como una sola formación.
- Dirigir la presentación a un jurado mixto, traduciendo cada métrica a una
  idea futbolística clara.
- Priorizar tres a cinco hallazgos respaldados por varias métricas y una
  cantidad suficiente de partidos.
- Usar fuentes externas solo para validar fechas, campeonatos y contexto
  histórico mínimo; las conclusiones tácticas deben salir de `hackathon.db`.
- Explorar las distribuciones antes de fijar umbrales como presión alta o
  recuperación alta.

## Plan de trabajo

1. **Auditar y normalizar la base**
   - Documentar tablas, llaves, cobertura temporal, equipos y calidad.
   - Relacionar `eventos`, `pases`, `acciones_defensivas`, `transiciones`,
     `remates`, `estado_partido`, `formaciones_tacticas` y
     `features_jugador_ventana`.
   - Resolver nombres de equipos, partidos duplicados, partidos sin torneo y
     reglas de orientación del campo.
   - Crear una tabla o archivo de configuración de etapas y torneos, sin
     modificar los datos crudos.

2. **Definir la unidad de análisis y los contextos**
   - Nivel partido para comparar tendencias.
   - Nivel posesión para estudiar progresión, recuperación y transición.
   - Nivel ventana de cinco minutos para observar ajustes según marcador.
   - Etiquetar rival, localía, estado del marcador, periodo del partido,
     formación inicial y cambios de formación.

3. **Medir la fase ofensiva**
   - Volumen y dirección de la posesión: pases, progresivos, longitud,
     cambios de orientación, pases clave y entradas al último tercio.
   - Progresión por zonas y carriles; identificar si el equipo construye por
     dentro, por fuera o mediante cambios de orientación.
   - Producción y calidad de ocasiones: tiros, xG, xG por tiro, secuencias
     previas al tiro y recuperaciones que terminan en tiro.
   - Medir la variación de estos patrones cuando el equipo va ganando,
     empatando o perdiendo.

4. **Medir la fase defensiva y las transiciones**
   - PPDA con una definición reproducible y explícita.
   - Altura y distribución territorial de presiones, recuperaciones,
     intercepciones, duelos y despejes.
   - Recuperaciones altas y su conversión en tiros o xG.
   - Velocidad y resultado de transiciones después de recuperar o perder el
     balón.
   - Comparar presión, bloque y riesgo defensivo por estado del partido.

5. **Analizar las decisiones de Jardine**
   - Cambios de sistema y estructura usando `formaciones_tacticas`.
   - Sustituciones, minuto de ajuste y respuesta posterior en volumen,
     territorio, ocasiones y control del partido.
   - Identificar patrones recurrentes: por ejemplo, pasar de 4-2-3-1 a otra
     estructura, proteger una ventaja o aumentar presencia ofensiva.
   - Separar decisiones planificadas de reacciones al resultado para no
     interpretar cualquier cambio como una intención táctica.

6. **Construir comparaciones y controles**
   - Comparar etapas pre-América, América durante campeonatos y post-América.
   - Comparar partidos ganados, empatados y perdidos, además de rivales de
     distinto nivel cuando sea posible.
   - Reportar tamaños de muestra y evitar promedios engañosos por diferencias
     de partidos disponibles.
   - Calcular intervalos o medidas de dispersión simples para mostrar si una
     diferencia es estable o depende de pocos partidos.

7. **Convertir métricas en una historia**
   - Elegir tres a cinco hallazgos defendibles, cada uno con pregunta,
     métrica, visualización, evidencia y conclusión.
   - Proponer una secuencia narrativa: punto de partida, transformación,
     decisiones durante los campeonatos y legado/evolución posterior.
   - Preparar tablas limpias en CSV/JSON y un dataset agregado para consumo de
     la interfaz de Joel.
   - Documentar definiciones, filtros, limitaciones y trazabilidad de cada
     hallazgo.

8. **Validar**
   - Ejecutar pruebas de conteos, llaves, rangos espaciales y ausencia de
     duplicados.
   - Revisar manualmente partidos representativos de cada etapa.
   - Contrastar que las visualizaciones y conclusiones coincidan con los
     registros subyacentes.

## Modelo de dominio acordado

- **Hipótesis:** el tricampeonato se explica mejor por la combinación de
  flexibilidad estructural, control territorial y adaptación al marcador que
  por una formación única.
- **Decisión observable:** cambio medible en formación, sustitución, presión,
  progresión, transición o comportamiento según el marcador; no equivale a una
  intención interna del entrenador.
- **Partido representativo:** partido seleccionado mediante reglas transparentes
  por su evidencia de cambio o patrón táctico, no solo por atractivo visual.
- **Salida analítica:** agregados por etapa, métricas por partido y acciones
  destacadas para consumo de la interfaz.

## Primeros entregables técnicos

- `data_dictionary.md` o equivalente con tablas, columnas y definiciones.
- Configuración de etapas/torneos y reglas de inclusión.
- Pipeline reproducible de Pandas que lea SQLite y genere métricas.
- CSV/JSON de métricas por partido, etapa y contexto.
- Notebook o reporte exploratorio con las primeras comparaciones.
- Catálogo de visualizaciones y hallazgos candidatos para la presentación.

## Progreso de implementación

- Auditoría inicial completada: 183 partidos, 610390 eventos y tablas tácticas
  disponibles.
- Pipeline inicial implementado en `jardine_analysis/pipeline.py`.
- Pruebas unitarias para clasificación, PPDA, métricas de partido y
  exportaciones.
- Exportaciones generadas en `outputs/`: CSV, JSON, reglas de etapas y
  resumen por formación y contexto.
- Reporte inicial en `docs/analysis_report.md` y diccionario de datos en
  `docs/data_dictionary.md`.
- Pendiente: validar torneos con una fuente histórica, conectar decisiones con
  cambios posteriores en el comportamiento del equipo, y construir
  visualizaciones finales.

## Revisión final de esta primera iteración

- Sin problemas importantes en el pipeline después de corregir la resolución
  del rival en partidos de visita y el conteo de cambios reales de formación.
- Riesgo menor pendiente: si dos formaciones distintas aparecen exactamente al
  mismo minuto y segundo, la formación inicial se toma por orden de origen;
  debe marcarse como ambigua en una iteración posterior.

## Riesgos y decisiones pendientes del implementador

- La competencia no está poblada en `partidos`; no se debe inferir el torneo
  únicamente del año.
- La etiqueta de “tres campeonatos consecutivos” debe quedar respaldada por
  una asignación de partidos verificable.
- Las coordenadas parecen estar en una escala de 120x80 en las tablas
  derivadas; se debe comprobar orientación y normalización antes de calcular
  altura de bloque o recuperación alta.
- PPDA y métricas de transición requieren declarar denominadores, exclusiones y
  manejo de eventos sin resultado.
- xG ya existe por remate; el plan debe usarlo como variable disponible y no
  presentar un modelo nuevo como si fuera oficial de StatsBomb.
