# V5 Foundation, Performance and Live Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear la base paralela de V5, eliminar trabajo duplicado y lograr ciclos automáticos rápidos de entrada, estabilidad y retirada.

**Architecture:** V5 usa almacenes de último valor y tres trabajadores independientes para cámara, seguimiento e inspección. La rectificación del ROI se ejecuta una vez por observación y la máquina live se alimenta con ocupación y movimiento con histéresis.

**Tech Stack:** Python 3.11, OpenCV contrib, NumPy, dataclasses, threading, pytest, Ruff, PowerShell y Git.

## Global Constraints

- No modificar archivos dentro de `src/inspection_v4`.
- No modificar `config/inspection_v1.json`, `data/references` ni `data/models`.
- Crear todo código funcional nuevo dentro de `src/inspection_v5`.
- Conservar sólo el último fotograma o estado; no usar colas ilimitadas.
- El tablero y el ROI deben rectificarse una sola vez por observación.
- El seguimiento debe ser independiente del color.
- Ejecutar pruebas V4 y V5 al final de cada tarea.

---

## File map

- `src/inspection_v5/contracts.py`: contratos inmutables entre trabajadores.
- `src/inspection_v5/latest_value.py`: almacén thread-safe de último valor.
- `src/inspection_v5/board_tracker.py`: ArUco reducido, homografía cacheada y warp directo.
- `src/inspection_v5/presence.py`: ocupación, movimiento y enfoque local.
- `src/inspection_v5/live_state.py`: máquina de estados automática.
- `src/inspection_v5/runtime.py`: coordinación de trabajadores y métricas.
- `src/inspection_v5/diagnostics.py`: JSONL rotativo y tiempos por etapa.
- `config/v5/runtime.json`: frecuencias, resoluciones e histéresis.
- `tests_v5`: pruebas aisladas de V5.

### Task 1: Snapshot recuperable de V4

**Files:**
- Create: `tools/v5_snapshot.py`
- Create: `tests_v5/test_snapshot.py`
- Create at runtime: `data/v5/manifests/v4_protected_files.json`

**Interfaces:**
- Produces: `build_manifest(root: Path) -> dict[str, str]`
- Produces: `verify_manifest(root: Path, manifest: Mapping[str, str]) -> list[str]`

- [ ] **Step 1: Escribir una prueba que detecte cambios protegidos**

```python
def test_verify_manifest_reports_changed_file(tmp_path):
    protected = tmp_path / "src" / "inspection_v4"
    protected.mkdir(parents=True)
    target = protected / "engine.py"
    target.write_text("before", encoding="utf-8")
    manifest = build_manifest(tmp_path)
    target.write_text("after", encoding="utf-8")
    assert verify_manifest(tmp_path, manifest) == ["src/inspection_v4/engine.py"]
```

- [ ] **Step 2: Ejecutar la prueba y observar el fallo inicial**

Run: `.venv\Scripts\python.exe -m pytest tests_v5/test_snapshot.py -v`

Expected: FAIL porque `tools.v5_snapshot` todavía no existe.

- [ ] **Step 3: Implementar hashes deterministas**

El manifiesto debe incluir archivos de `src/inspection_v4`, `config/inspection_v1.json`,
`config/board_letter_v1.json`, `data/references` y `data/models`. Debe excluir logs,
`__pycache__` y `.gitkeep`. Las rutas se guardan con `/` y SHA-256 hexadecimal.

- [ ] **Step 4: Guardar el manifiesto real y el estado Git**

Run:

```powershell
.venv\Scripts\python.exe tools\v5_snapshot.py create
git status --short > data\v5\manifests\git_status_before_v5.txt
git diff --binary > data\v5\manifests\working_tree_before_v5.patch
```

Expected: manifiesto JSON no vacío y patch recuperable.

- [ ] **Step 5: Ejecutar pruebas y crear commit de rescate**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: las 46 pruebas V4 y la prueba nueva pasan.

Commit: `git commit -m "chore: checkpoint v4 before v5 rebuild"`

### Task 2: Contratos V5 y almacén de último valor

**Files:**
- Create: `src/inspection_v5/__init__.py`
- Create: `src/inspection_v5/contracts.py`
- Create: `src/inspection_v5/latest_value.py`
- Create: `tests_v5/test_latest_value.py`

**Interfaces:**
- Produces: `FramePacket(sequence: int, captured_at: float, bgr: np.ndarray)`
- Produces: `TrackingSnapshot(sequence, captured_at, board_ok, roi, bbox, occupied_ratio, motion, piece_focus, reason)`
- Produces enum: `TrackingMode.EMPTY, DETECTED, STABILIZING, INSPECTING, LOCKED, PASS, FAIL`
- Produces enum: `ComponentPublicState.UNKNOWN, PRESENT, MISSING, UNRELIABLE`
- Produces: `RuntimeMetrics(camera_fps, ui_fps, tracking_fps, stage_ms, piece_focus, marker_focus, occupied_ratio, motion, model_hash, log_path)`
- Produces: `PublicState(version, frame, tracking_bbox, tracking_mode, headline, detail, instruction, verdict, component_states, counters, metrics)`
- Produces: `LatestValue[T].publish(value: T) -> int`
- Produces: `LatestValue[T].read(after_version: int = -1) -> tuple[int, T | None]`

- [ ] **Step 1: Probar que publicaciones intermedias se descartan**

```python
def test_latest_value_returns_only_newest_item():
    store = LatestValue[str]()
    store.publish("old")
    version = store.publish("new")
    assert store.read()[1] == "new"
    assert store.read(after_version=version) == (version, None)
```

- [ ] **Step 2: Implementar dataclasses congeladas y bloqueo corto**

`LatestValue` debe copiar únicamente referencias, incrementar una versión entera y no esperar
condiciones. Los arrays publicados se tratan como inmutables.

- [ ] **Step 3: Ejecutar pruebas y Ruff**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests_v5/test_latest_value.py -v
.venv\Scripts\python.exe -m ruff check src\inspection_v5 tests_v5
```

Expected: PASS y `All checks passed`.

- [ ] **Step 4: Commit**

Commit: `git commit -m "feat(v5): add immutable runtime contracts"`

### Task 3: Rectificación única y homografía cacheada

**Files:**
- Create: `src/inspection_v5/board_tracker.py`
- Create: `config/v5/runtime.json`
- Create: `tools/benchmark_v5.py`
- Create: `tests_v5/test_board_tracker.py`
- Copy fixtures into: `tests_v5/fixtures/board_complete.png`

**Interfaces:**
- Produces: `BoardTracker.observe(frame: FramePacket, now: float) -> TrackingSnapshot`
- Produces: `BoardTracker.warp_roi(frame: np.ndarray, homography: np.ndarray, size=(320, 560)) -> np.ndarray`
- Produces metric: `homography_age_ms`

- [ ] **Step 1: Copiar una imagen real al repositorio**

Copiar la imagen temporal de tablero completo usada por las pruebas actuales a
`tests_v5/fixtures/board_complete.png` y actualizar pruebas para no depender de `%TEMP%`.

- [ ] **Step 2: Probar un solo `warpPerspective` por observación**

```python
def test_tracker_warps_roi_once(monkeypatch, tracker, frame_packet):
    calls = 0
    original = cv2.warpPerspective
    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(cv2, "warpPerspective", counted)
    result = tracker.observe(frame_packet, now=1.0)
    assert result.board_ok
    assert calls == 1
```

- [ ] **Step 3: Implementar detección reducida y transformación directa al ROI**

Detectar en ancho 960, reescalar esquinas a la imagen original, calcular homografía con las 16
esquinas y componerla con traslación/escala del ROI. El resultado de seguimiento debe medir
320 x 560; no crear el tablero 1728 x 2235.

- [ ] **Step 4: Implementar caché conservadora**

Reutilizar homografía hasta 300 ms sólo si la última reproyección fue <= 3 px. Renovarla a
10 Hz. Si expira o faltan marcadores durante más de 300 ms, `board_ok=False`.

- [ ] **Step 5: Medir rendimiento**

Run: `.venv\Scripts\python.exe tools\benchmark_v5.py --stage board --frames 200`

Expected: percentil 95 <= 35 ms y exactamente un warp por observación.

- [ ] **Step 6: Commit**

Commit: `git commit -m "perf(v5): rectify roi once with cached homography"`

### Task 4: Presencia, movimiento y enfoque local

**Files:**
- Create: `src/inspection_v5/presence.py`
- Create: `tests_v5/test_presence.py`
- Create: `tests_v5/fixtures/roi_empty.png`
- Create: `tests_v5/fixtures/roi_complete.png`

**Interfaces:**
- Produces: `PresenceAnalyzer.measure(roi: np.ndarray, previous_roi: np.ndarray | None) -> PresenceMetrics`
- `PresenceMetrics`: `occupied_ratio`, `motion`, `piece_focus`, `bbox`, `mask`, `reason`

- [ ] **Step 1: Probar histéresis medible e independencia del color**

```python
def test_presence_is_equal_after_hue_change(analyzer, complete_roi):
    shifted = cv2.cvtColor(complete_roi, cv2.COLOR_BGR2HSV)
    shifted[..., 0] = (shifted[..., 0] + 70) % 180
    shifted = cv2.cvtColor(shifted, cv2.COLOR_HSV2BGR)
    a = analyzer.measure(complete_roi, None)
    b = analyzer.measure(shifted, None)
    assert abs(a.occupied_ratio - b.occupied_ratio) < 0.02
```

- [ ] **Step 2: Implementar máscara luminancia-fondo y componentes cercanos**

Usar mediana/MAD del borde, Otsu con piso de 18 niveles, morfología a escala 4 px/mm y
componentes conectados cercanos. Calcular ocupación contra área de referencia, no contra el ROI.

- [ ] **Step 3: Separar enfoque de pieza y marcadores**

Calcular Laplaciano únicamente dentro de `bbox` erosionado de la pieza. Un marcador nítido no
puede elevar `piece_focus`. Guardar ambos valores por separado en diagnóstico.

- [ ] **Step 4: Ejecutar pruebas**

Run: `.venv\Scripts\python.exe -m pytest tests_v5/test_presence.py -v`

Expected: vacío, pieza, cambio de color, desenfoque y movimiento pasan sus casos.

- [ ] **Step 5: Commit**

Commit: `git commit -m "feat(v5): add color-independent presence metrics"`

### Task 5: Máquina live automática

**Files:**
- Create: `src/inspection_v5/live_state.py`
- Create: `tests_v5/test_live_state.py`

**Interfaces:**
- Produces enum: `LiveState.EMPTY, ENTERING, STABILIZING, READY, INSPECTING, RESULT, REMOVING`
- Produces: `LiveController.update(metrics: PresenceMetrics, board_ok: bool, now: float) -> LiveEvent`
- `LiveEvent`: `state`, `start_inspection`, `cancel_inspection`, `cycle_released`, `message`

- [ ] **Step 1: Probar un ciclo completo sin teclas**

```python
def test_complete_live_cycle_releases_after_fast_empty(controller):
    feed(controller, occupied=0.50, motion=3.0, at=0.00)
    feed(controller, occupied=0.50, motion=0.2, at=0.10)
    event = feed(controller, occupied=0.50, motion=0.2, at=0.46)
    assert event.start_inspection
    controller.result_ready()
    feed(controller, occupied=0.08, motion=2.0, at=0.60)
    feed(controller, occupied=0.08, motion=0.1, at=0.72)
    event = feed(controller, occupied=0.08, motion=0.1, at=0.82)
    assert event.cycle_released
    assert event.state is LiveState.EMPTY
```

- [ ] **Step 2: Implementar histéresis exacta**

Usar entrada `>=0.35`, vacío `<=0.12`, estabilidad 350 ms y liberación vacía de tres
observaciones más 200 ms. No liberar ciclo si `board_ok=False`.

- [ ] **Step 3: Probar manos, marcador cubierto y sustitución rápida**

Las pruebas deben confirmar que una mano cancela estabilización, que marcadores cubiertos no
cuentan como retirada y que una nueva pieza inicia otro ciclo sin espacio ni doble conteo.

- [ ] **Step 4: Commit**

Commit: `git commit -m "feat(v5): automate live entry and removal cycle"`

### Task 6: Runtime desacoplado y telemetría

**Files:**
- Create: `src/inspection_v5/runtime.py`
- Create: `src/inspection_v5/diagnostics.py`
- Modify: `tools/benchmark_v5.py`
- Create: `tests_v5/test_runtime.py`
- Create: `tests_v5/test_pipeline_performance.py`

**Interfaces:**
- Produces: `InspectionRuntime.start()`, `stop()`, `latest_public_state()`
- Consumes: `LatestValue[FramePacket]`, `BoardTracker`, `PresenceAnalyzer`, `LiveController`
- Produces JSONL fields: `stage_ms`, `state_from`, `state_to`, `sequence`, `dropped_sequences`

- [ ] **Step 1: Probar que un inspector lento no congela seguimiento**

Usar un juez falso que tarde 300 ms. Publicar 30 frames y confirmar que tracking procesa el
último sequence y que no se almacenan 30 trabajos pendientes.

- [ ] **Step 2: Implementar tres workers con apagado limpio**

Cada worker debe ser daemon, observar `threading.Event`, capturar excepciones en diagnóstico y
terminar en máximo 1 s. El inspector sólo consume snapshots con `start_inspection=True`.

- [ ] **Step 3: Implementar JSONL rotativo**

Rotar a 10 MB, conservar cinco archivos y ejecutar `flush` en resultados o fallos. No guardar
imágenes de aprobaciones salvo modo diagnóstico.

- [ ] **Step 4: Ejecutar batería completa**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check src\inspection_v5 tests_v5 tools\benchmark_v5.py
.venv\Scripts\python.exe tools\v5_snapshot.py verify
```

Expected: todas las pruebas pasan, Ruff limpio y `protected files unchanged`.

- [ ] **Step 5: Commit**

Commit: `git commit -m "feat(v5): decouple tracking inspection and diagnostics"`
