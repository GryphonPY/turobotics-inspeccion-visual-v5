# Inspección Visual V5 Master Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Coordinar la construcción y liberación de V5 sin modificar ni poner en riesgo V4.

**Architecture:** El trabajo se divide en cuatro planes independientes y ordenados: base/live,
juez híbrido, interfaz de televisión y validación final. Cada plan debe cerrar con pruebas y
commit antes de iniciar el siguiente.

**Tech Stack:** Python 3.11, OpenCV contrib, NumPy, PySide6, ONNX Runtime, PyTorch sólo para entrenamiento, pytest, Ruff, PowerShell y Git.

## Estado de ejecución

- Paso 1 — base, rendimiento y modo live: implementado y verificado.
- Paso 2 — juez híbrido, ONNX y campaña de fixtures: implementado; la campaña local actual reporta cero falsos `PASA`.
- Paso 3 — interfaz de televisión, diagnóstico y launchers: implementado y revisado visualmente.
- Paso 4 — herramientas de validación, batería física y liberación: herramientas implementadas; el challenge físico holdout ya fue capturado y evaluado.
- Evidencia actual: sesión `challenge_20260814_054132`, 60 ciclos programados y 1 repetición; `evaluate_v5.py --split challenge-holdout` reportó `sample_count=30`, `false_passes=0`, `false_rejects=0` y `release_ready=true`.
- Siguiente puerta: ejecutar la batería física completa de liberación y el ensayo de presentación. No se debe declarar V5 liberada ni generar el paquete final antes de esas puertas.

## Global Constraints

- La especificación normativa es `docs/superpowers/specs/2026-08-13-v5-television-rebuild-design.md`.
- No modificar `src/inspection_v4`, `config/inspection_v1.json` ni artefactos V4.
- No mover ni reescribir `data/raw_sessions/session_20260813_001845`.
- V5 debe funcionar en Windows, CPU y sin internet durante la demo.
- Nunca usar color como evidencia de calidad o presencia.
- Un desacuerdo o captura insegura debe cerrarse como `CAPTURA NO CONFIABLE`.
- Ejecutar Ruff y pytest después de cada cambio de código.
- Crear commits pequeños y conservar un punto de rollback al final de cada tarea.

---

## Orden obligatorio

- [x] **Paso 1: Ejecutar el plan de base, rendimiento y modo live**

Documento: `docs/superpowers/plans/2026-08-13-v5-foundation-live.md`

Salida exigida: V5 arranca con un motor simulado, seguimiento desacoplado y ciclos automáticos
de entrada/retirada, mientras V4 conserva hashes idénticos.

- [x] **Paso 2: Ejecutar el plan del juez híbrido**

Documento: `docs/superpowers/plans/2026-08-13-v5-hybrid-judge.md`

Salida exigida: motor offline capaz de producir `PASA`, `NO PASA` y
`CAPTURA NO CONFIABLE`, con artefacto ONNX versionado y prueba adversarial congelada.

- [x] **Paso 3: Ejecutar el plan de interfaz para televisión**

Documento: `docs/superpowers/plans/2026-08-13-v5-television-ui.md`

Salida exigida: interfaz PySide6 16:9, modo público y diagnóstico, tracking visual, cierre
normal y launchers sin consola.

- [ ] **Paso 4: Ejecutar el plan de validación y liberación**

Documento: `docs/superpowers/plans/2026-08-13-v5-validation-release.md`

Salida exigida: reporte firmado de criterios, paquete offline, ensayo de 30 minutos y rollback.

## Puertas de revisión

- [ ] Después del Paso 1, ejecutar `python -m pytest tests_v5/test_live_state.py tests_v5/test_pipeline_performance.py -v` y confirmar cero fallos.
- [ ] Después del Paso 2, confirmar cero falsos `PASA` en el conjunto adversarial congelado.
- [ ] Después del Paso 3, revisar una captura 1920 x 1080 de cada estado público.
- [ ] Después del Paso 4, comparar hashes V4 contra el manifiesto inicial y confirmar igualdad.

## Regla de detención

Si una puerta falla, no avanzar al plan siguiente. Registrar la evidencia en
`data/v5/reports/blockers.jsonl`, corregir dentro del mismo plan y repetir su batería completa.
