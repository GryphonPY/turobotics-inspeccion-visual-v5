# Fast Incompatible Assembly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evitar el atasco `0/9`, rechazar ensambles físicamente incompatibles y reducir el tiempo por fotograma sin alterar la calibración.

**Architecture:** `InspectionWorkflow` separará votos válidos de fallos consecutivos de alineación y emitirá un rechazo global conservador al alcanzar nueve fallos. `ComponentEvaluator` conservará artefactos inmutables precalculados y `app.py` reutilizará la observación producida por el flujo.

**Tech Stack:** Python 3.11+, OpenCV, NumPy, scikit-learn, pytest, Ruff.

## Global Constraints

- Conservar nueve votos y 80% de presencia por componente.
- No cambiar datos, referencias, modelo C08 ni umbrales.
- Nunca convertir una alineación insegura en `PASA`.

---

### Task 1: Pruebas de estado conservador

**Files:**
- Modify: `tests/test_workflow_collection.py`
- Modify: `src/inspection_v4/workflow.py`

- [ ] Crear pruebas para nueve fallos consecutivos, reinicio tras éxito y limpieza por movimiento.
- [ ] Ejecutarlas y comprobar que fallan con el flujo actual.
- [ ] Implementar contadores y resultado `shape_incompatible`.
- [ ] Ejecutar las pruebas dirigidas hasta que pasen.

### Task 2: Optimización matemática equivalente

**Files:**
- Modify: `src/inspection_v4/components.py`
- Modify: `tests/test_components_performance.py`

- [ ] Comparar evidencia del evaluador optimizado contra los cálculos existentes.
- [ ] Precargar bordes, normalizaciones y regiones en `ComponentEvaluator.__init__`.
- [ ] Normalizar la entrada una vez dentro de `evaluate`.
- [ ] Medir una captura real y registrar el tiempo nuevo.

### Task 3: Rectificación única y estado visible

**Files:**
- Modify: `src/inspection_v4/workflow.py`
- Modify: `src/inspection_v4/app.py`
- Modify: `README.md`

- [ ] Exponer `last_canonical` desde el flujo.
- [ ] Eliminar la segunda llamada a `rectifier.warp` en la aplicación.
- [ ] Mostrar descartes de alineación y el texto de ensamble incompatible.
- [ ] Mantener congelados imagen, tablero y resultado durante `WAIT_REMOVAL`.

### Task 4: Verificación integral

**Files:**
- Test: `tests/`
- Verify: `data/golden_test/session_20260813_001845_holdout_report.json`

- [ ] Ejecutar Ruff, pytest, compileall y `git diff --check`.
- [ ] Ejecutar `tools/evaluate_session.py session_20260813_001845`.
- [ ] Confirmar `all_correct: true` y comparar el benchmark final.
