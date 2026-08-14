# V5 Television UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear una interfaz PySide6 profesional, legible en televisión, fluida durante el análisis y completamente operable sin consola.

**Architecture:** La UI consume un `PublicState` inmutable y nunca ejecuta visión computacional. Un adaptador Qt sondea el último estado, actualiza el video y anima únicamente transiciones significativas.

**Tech Stack:** Python 3.11, PySide6, Qt Widgets, OpenCV/NumPy para conversión de imágenes, pytest-qt, Ruff, PowerShell, VBScript y Git.

## Global Constraints

- Resolución de diseño 1920 x 1080, adaptable hasta 1280 x 720.
- Modo público sin scores, nombres internos de estados ni texto técnico.
- Tamaño mínimo de texto visible a distancia: 24 px a 1920 x 1080.
- No congelar el video al mostrar un resultado.
- No usar más de una animación de atención simultánea.
- El botón X, ESC y el botón `SALIR` deben cerrar workers, cámara y ventana.
- Los launchers públicos no muestran consola.
- El modo diagnóstico se abre con `F2` y no modifica umbrales.

---

## File map

- `src/inspection_v5/ui/theme.py`: paleta, tamaños y stylesheet.
- `src/inspection_v5/ui/view_model.py`: transformación de `PublicState` a textos/colores.
- `src/inspection_v5/ui/video_view.py`: video y overlay de seguimiento.
- `src/inspection_v5/ui/result_panel.py`: resultado y mapa C01-C10.
- `src/inspection_v5/ui/main_window.py`: layout y ciclo de vida.
- `src/inspection_v5/ui/diagnostic_panel.py`: métricas técnicas.
- `src/inspection_v5/qt_app.py`: composición runtime/UI.
- `ABRIR_DEMO_V5.vbs` y `ABRIR_DEMO_V5.bat`: launchers.
- `tests_v5/ui`: pruebas de estado y screenshots.

### Task 1: Dependencias, tema y view model

**Files:**
- Modify: `pyproject.toml`
- Create: `src/inspection_v5/ui/__init__.py`
- Create: `src/inspection_v5/ui/theme.py`
- Create: `src/inspection_v5/ui/view_model.py`
- Create: `tests_v5/ui/test_view_model.py`

**Interfaces:**
- Produces: `PresentationViewModel.from_public_state(state: PublicState) -> PresentationViewModel`
- Campos: `headline`, `detail`, `instruction`, `accent`, `tracking_mode`, `component_states`, `show_result`

- [ ] **Step 1: Añadir PySide6 y pytest-qt**

Agregar `PySide6` a dependencias runtime y `pytest-qt` al extra dev. Fijar rangos compatibles
con Python 3.11 y registrar versiones resueltas en `requirements-lock.txt`.

- [ ] **Step 2: Probar textos públicos exactos**

```python
@pytest.mark.parametrize((verdict, headline), [
    ("PASS", "10/10 PRESENTES"),
    ("NO_PASS", "NO PASA"),
    ("UNRELIABLE", "CAPTURA NO CONFIABLE"),
])
def test_public_headlines(verdict, headline, public_state):
    state = dataclasses.replace(public_state, verdict=verdict)
    assert PresentationViewModel.from_public_state(state).headline == headline
```

- [ ] **Step 3: Implementar tema exacto**

Usar los colores de la especificación, `Segoe UI Variable`, paneles con radio de 18 px y
espaciado base de 8 px. No usar gradientes decorativos en texto ni sombras intensas.

- [ ] **Step 4: Probar que scores técnicos no aparecen**

Buscar en todos los textos del view model público: no deben contener `0.`, `IoU`, `px`,
`WAIT_`, `COLLECTING`, `Cámara 1` ni rutas de archivo.

- [ ] **Step 5: Commit**

Commit: `git commit -m "feat(v5-ui): define television theme and public states"`

### Task 2: Video adaptable y marco de seguimiento

**Files:**
- Create: `src/inspection_v5/ui/video_view.py`
- Create: `tests_v5/ui/test_video_view.py`

**Interfaces:**
- Produces widget: `TrackingVideoView.set_frame(bgr: np.ndarray)`
- Produces: `TrackingVideoView.set_tracking(bbox, mode: TrackingMode, label: str)`

- [ ] **Step 1: Probar conversión BGR-QImage sin copiar datos inválidos**

Exigir frame visible, proporción conservada y memoria válida después de que termine la función
de conversión.

- [ ] **Step 2: Implementar letterboxing controlado**

El video ocupa todo el espacio disponible, mantiene proporción y usa fondo `#060B14`. El
overlay transforma coordenadas ROI a coordenadas pintadas incluyendo offset del letterbox.

- [ ] **Step 3: Dibujar marco de esquinas**

Dibujar ocho segmentos de esquina, línea 4 px a 1080p, etiqueta superior y halo de 1 px. No
dibujar un rectángulo completo tembloroso. Suavizar bbox con mediana de cinco observaciones.

- [ ] **Step 4: Implementar estados de color**

Gris vacío, cian detectado, ámbar estabilizando/inspeccionando, verde locked/pass y rojo fail.
Un pulso de 250 ms sólo ocurre al entrar a PASS o NO_PASS.

- [ ] **Step 5: Commit**

Commit: `git commit -m "feat(v5-ui): add live tracking overlay"`

### Task 3: Panel de resultado y mapa de componentes

**Files:**
- Create: `src/inspection_v5/ui/result_panel.py`
- Create: `src/inspection_v5/ui/component_map.py`
- Create: `tests_v5/ui/test_result_panel.py`

**Interfaces:**
- Produces: `ResultPanel.apply(model: PresentationViewModel) -> None`
- Produces: `ComponentMap.set_states(dict[str, ComponentPublicState]) -> None`

- [ ] **Step 1: Probar los diez componentes**

La prueba exige exactamente C01-C10 y verifica que C09/C10 permanezcan dentro del widget a
1280 x 720 y 1920 x 1080.

- [ ] **Step 2: Implementar jerarquía visual**

Headline mínimo 56 px a 1080p, detalle mínimo 28 px, instrucción 24 px. El resultado ocupa la
parte superior del panel; debajo aparece el esquema y al final contadores.

- [ ] **Step 3: Implementar historial de último ciclo**

Al liberar una pieza, el resultado principal vuelve a `ÁREA LIBRE` y una tarjeta compacta
conserva ciclo, verdict y tiempo anterior sin congelar video.

- [ ] **Step 4: Commit**

Commit: `git commit -m "feat(v5-ui): present result and ten component map"`

### Task 4: Ventana principal 16:9 y ciclo de vida

**Files:**
- Create: `src/inspection_v5/ui/main_window.py`
- Create: `src/inspection_v5/qt_app.py`
- Create: `tests_v5/ui/test_main_window.py`

**Interfaces:**
- Produces: `MainWindow(runtime: InspectionRuntime)`
- Produces: `run_qt_app(root: Path, camera_index: int | None = None) -> int`

- [ ] **Step 1: Probar layout en dos resoluciones**

Renderizar 1280 x 720 y 1920 x 1080. Exigir video >= 65% del ancho, panel <= 35%, barra
superior e inferior visibles y ningún widget superpuesto.

- [ ] **Step 2: Implementar layout**

Barra superior 72 px base, cuerpo con splitter fijo 68/32 y barra inferior 56 px. Usar layouts
Qt, no posiciones absolutas.

- [ ] **Step 3: Actualizar a 60 Hz sin ejecutar análisis**

Un `QTimer` de 16 ms lee `runtime.latest_public_state()`. Si la versión no cambió, sólo
mantiene animación; no vuelve a convertir la imagen.

- [ ] **Step 4: Cierre normal**

`closeEvent`, ESC y botón `SALIR` llaman `runtime.stop()`, esperan máximo 1 s y aceptan el
evento. Una prueba con worker falso confirma que no queda ningún thread vivo.

- [ ] **Step 5: Commit**

Commit: `git commit -m "feat(v5-ui): build responsive television window"`

### Task 5: Modo diagnóstico oculto

**Files:**
- Create: `src/inspection_v5/ui/diagnostic_panel.py`
- Create: `tests_v5/ui/test_diagnostic_panel.py`

**Interfaces:**
- Produces: `DiagnosticPanel.update_metrics(metrics: RuntimeMetrics)`

- [ ] **Step 1: Implementar alternancia F2**

F2 muestra/oculta panel lateral superpuesto; el estado público no cambia. El panel nunca
acepta edición de thresholds.

- [ ] **Step 2: Mostrar métricas útiles**

FPS cámara/UI/tracking, tiempos board/presence/alignment/ONNX/fusion, enfoque pieza/marcadores,
ocupación, movimiento, ArUco, hash modelo y ruta de log.

- [ ] **Step 3: Añadir botón de exportar diagnóstico**

Guardar snapshot JSON y PNG en `data/v5/diagnostics` con fecha. No sobrescribir archivos.

- [ ] **Step 4: Commit**

Commit: `git commit -m "feat(v5-ui): add read-only engineering diagnostics"`

### Task 6: Launchers y comprobación visual

**Files:**
- Create: `ABRIR_DEMO_V5.bat`
- Create: `ABRIR_DEMO_V5.vbs`
- Create: `CAMBIAR_CAMARA_V5.bat`
- Create: `tests_v5/ui/test_launchers.py`
- Create at runtime: `data/v5/ui_review/*.png`

**Interfaces:**
- Launcher público resuelve `.venv\Scripts\pythonw.exe` y ejecuta `-m inspection_v5.qt_app`.

- [ ] **Step 1: Crear launcher sin consola**

VBScript ejecuta el BAT oculto; BAT usa rutas relativas a `%~dp0`, escribe errores de arranque
en `logs/v5_launcher.log` y devuelve código distinto de cero si falta el entorno.

- [ ] **Step 2: Capturar estados visuales**

Con runtime simulado, guardar PNG 1920 x 1080 de vacío, estabilizando, analizando, pasa, no
pasa, no confiable y diagnóstico.

- [ ] **Step 3: Revisar legibilidad**

Confirmar visualmente: sin texto cortado, sin superposiciones, C01-C10 visibles, contraste
WCAG AA para texto normal y resultado reconocible a miniatura de 25%.

- [ ] **Step 4: Ejecutar suite y snapshot**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check src\inspection_v5 tests_v5
.venv\Scripts\python.exe tools\v5_snapshot.py verify
```

Expected: pruebas completas, Ruff limpio y V4 intacta.

- [ ] **Step 5: Commit**

Commit: `git commit -m "feat(v5-ui): package fullscreen demo launchers"`
