# Adaptive Frame Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evitar resultados de captura insuficiente causados únicamente por el rendimiento de la laptop, esperando hasta reunir nueve decisiones válidas.

**Architecture:** La máquina de estados usará el conteo de decisiones válidas como única condición de finalización de `COLLECTING`. La interfaz leerá ese mismo conteo para mostrar progreso sin crear estado duplicado.

**Tech Stack:** Python 3.11+, OpenCV, NumPy, pytest, Ruff.

## Global Constraints

- Conservar `min_valid_frames = 9` y `frame_vote_fraction = 0.80`.
- No modificar referencias, modelos ni datos de calibración.
- El operador puede cancelar una espera mediante `R`, `Q` o `ESC`.

---

### Task 1: Finalización basada en conteo

**Files:**
- Modify: `src/inspection_v4/workflow.py`
- Create: `tests/test_workflow_collection.py`

**Interfaces:**
- Consumes: `InspectionConfig.min_valid_frames` y `InspectionWorkflow.frame_decisions`.
- Produces: `InspectionWorkflow._collection_ready() -> bool`.

- [ ] **Step 1: Escribir la prueba de regresión**

Crear un flujo mínimo con ocho decisiones utilizables y comprobar que el tiempo no
lo finaliza; agregar una novena y comprobar que `_collection_ready()` cambia a
verdadero.

- [ ] **Step 2: Ejecutar la prueba para verificar que falla**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_workflow_collection.py -q`

Expected: FAIL porque `_collection_ready` todavía no existe.

- [ ] **Step 3: Implementar la condición mínima**

Sustituir las salidas basadas en `collection_seconds` por una condición que sólo sea
verdadera cuando `len(frame_decisions) >= config.min_valid_frames`.

- [ ] **Step 4: Ejecutar la prueba dirigida**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_workflow_collection.py -q`

Expected: PASS.

### Task 2: Progreso visible y verificación integral

**Files:**
- Modify: `src/inspection_v4/app.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `workflow.state`, `len(workflow.frame_decisions)` y `workflow.config.min_valid_frames`.
- Produces: texto visible `ANALIZANDO X/9`.

- [ ] **Step 1: Mostrar el avance durante `COLLECTING`**

Agregar el texto en el panel principal cuando todavía no existe un resultado.

- [ ] **Step 2: Documentar la espera adaptativa**

Explicar que la duración depende de la CPU y que `R` reinicia si las condiciones no
permiten completar nueve decisiones.

- [ ] **Step 3: Ejecutar verificación completa**

Run: `.\.venv\Scripts\python.exe -m ruff check src tools tests`

Run: `.\.venv\Scripts\python.exe -m pytest -q`

Run: `.\.venv\Scripts\python.exe -m compileall -q src tools tests`

Run: `.\.venv\Scripts\python.exe tools\evaluate_session.py session_20260813_001845`

Expected: lint limpio, todas las pruebas pasan y `all_correct: true`.
