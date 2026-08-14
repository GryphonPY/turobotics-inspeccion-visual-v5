# V5 Validation and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Demostrar con evidencia que V5 es rápida, conservadora, operable offline y recuperable antes de usarla en la presentación.

**Architecture:** Una herramienta de campaña reproduce fixtures, captura resultados físicos y genera un reporte firmado. El empaquetado sólo se habilita cuando todas las puertas automáticas y físicas pasan.

**Tech Stack:** Python 3.11, pytest, OpenCV, Psutil, JSONL/CSV, PowerShell, Git y SHA-256.

## Global Constraints

- No declarar V5 lista basándose únicamente en pruebas unitarias.
- Cero falsos `PASA` en defectos congelados.
- No modificar el conjunto holdout después de abrir su primer reporte.
- Toda corrección obliga a repetir la batería completa afectada.
- La prueba física final debe usar laptop, cámara, hoja y procedimiento de presentación.
- V4 debe conservar hashes idénticos al snapshot inicial.
- El paquete final debe arrancar sin internet y sin consola.

---

## File map

- `tools/run_v5_campaign.py`: orquestación de pruebas offline y físicas.
- `tools/soak_v5.py`: memoria, FPS y latencia durante 30 minutos.
- `tools/package_v5.ps1`: paquete offline y hashes.
- `data/v5/reports`: reportes inmutables por ejecución.
- `docs/OPERACION_DEMO_V5.md`: procedimiento de presentación y recuperación.

### Task 1: Suite automática y fixtures permanentes

**Files:**
- Create: `tests_v5/fixtures/manifest.json`
- Create: `tests_v5/test_regression_fixtures.py`
- Create: `tools/run_v5_campaign.py`

**Interfaces:**
- Produces: `CampaignResult(total, passed, failed, false_passes, latencies, artifact_hashes)`

- [ ] **Step 1: Registrar hashes y etiquetas de fixtures**

Incluir vacío, tablero incompleto, completa, faltantes conocidos, reacomodada, borrosa y mano.
Cada entrada define `expected_verdict` y `expected_reason_family`.

- [ ] **Step 2: Probar que ningún fixture se omite silenciosamente**

```python
def test_all_regression_fixtures_exist_and_match_hash(fixture_manifest):
    assert len(fixture_manifest) >= 8
    for item in fixture_manifest:
        assert item.path.exists()
        assert sha256_file(item.path) == item.sha256
```

- [ ] **Step 3: Implementar campaña reproducible**

La herramienta guarda configuración, versión Git, CPU, modelo, resultados y tiempos. Un fixture
faltante produce fallo de campaña, no skip.

- [ ] **Step 4: Ejecutar**

Run: `.venv\Scripts\python.exe tools\run_v5_campaign.py --mode fixtures`

Expected: cero falsos `PASA`, cero fixtures omitidos y reporte JSON.

- [ ] **Step 5: Commit**

Commit: `git commit -m "test(v5): add permanent regression campaign"`

### Task 2: Prueba de rendimiento y 30 minutos

**Files:**
- Create: `tools/soak_v5.py`
- Create: `tests_v5/test_metrics_summary.py`

**Interfaces:**
- Produces: `summarize_samples(samples) -> PerformanceSummary`
- Campos: FPS p50/p95, stage p50/p95, decision p50/p95, removal p50/p95, RSS inicial/final/máxima.

- [ ] **Step 1: Probar cálculo de percentiles y crecimiento**

Usar muestras sintéticas conocidas y exigir percentiles deterministas y crecimiento RSS en MB.

- [ ] **Step 2: Implementar soak con fuente real o video repetible**

Tomar una muestra por segundo, guardar heartbeat y terminar limpiamente con Ctrl+C. Marcar fallo
si UI < 24 FPS, decisión p95 > 1.5 s, retirada mediana > 0.3 s o RSS crece más de 150 MB.

- [ ] **Step 3: Ejecutar 30 minutos**

Run: `.venv\Scripts\python.exe tools\soak_v5.py --minutes 30`

Expected: `PASS` y reporte en `data/v5/reports`.

- [ ] **Step 4: Commit**

Commit: `git commit -m "test(v5): verify sustained runtime performance"`

### Task 3: Batería física de liberación

**Files:**
- Extend: `tools/run_v5_campaign.py`
- Create: `docs/V5_BATERIA_FISICA.md`
- Create at runtime: `data/v5/reports/physical_release_<timestamp>.json`

**Interfaces:**
- Modo: `--mode physical --scenario <name> --count <n>`
- Escenarios: `complete`, `single_missing`, `double_missing`, `rearranged`, `outside`, `hand`, `marker`, `blur`, `bad_light`.

- [ ] **Step 1: Implementar contador guiado y bloqueo de etiquetas**

Antes de cada lote, seleccionar escenario esperado. Cada ciclo se registra automáticamente; el
operador no puede cambiar la etiqueta después de ver el resultado.

- [ ] **Step 2: Ejecutar batería mínima**

- 100 completas.
- 20 por cada componente faltante.
- 20 dobles faltantes.
- 20 reacomodadas.
- 20 parcialmente fuera.
- 20 con mano.
- 20 con marcador cubierto.
- 20 borrosas o en movimiento.
- 20 con iluminación mala.

- [ ] **Step 3: Aplicar criterios**

Cero falsos `PASA` en defectos, al menos 99/100 completas correctas y todas las capturas
inseguras como `UNRELIABLE` o `NO_PASS`, nunca `PASS`.

- [ ] **Step 4: Congelar reporte**

Calcular SHA-256 del reporte y escribirlo en `physical_release_<timestamp>.sha256`. No editar
el JSON después.

- [ ] **Step 5: Commit de herramientas y documentación**

Commit: `git commit -m "test(v5): document physical release battery"`

### Task 4: Ensayo visible de presentación

**Files:**
- Create: `docs/OPERACION_DEMO_V5.md`
- Create at runtime: `data/v5/reports/rehearsal_<timestamp>.json`

**Interfaces:**
- Procedimiento de montaje y recuperación de máximo una página para el operador.

- [ ] **Step 1: Documentar montaje exacto**

Fijar hoja plana, conectar celular, elegir cámara en preview, verificar cuatro ArUco, activar
fullscreen y colocar pieza sólo dentro del rectángulo.

- [ ] **Step 2: Documentar recuperación**

Incluye cambio de cámara, reconexión Android, salir con ESC/X, volver a V4 y ubicación de logs.
No incluye ajustes de thresholds durante presentación.

- [ ] **Step 3: Ejecutar ensayo 30/30**

Treinta completas y treinta defectuosas alternadas, con retirada automática y sin usar espacio.
Expected: 60 decisiones correctas, cero dobles conteos y cero intervención técnica.

- [ ] **Step 4: Revisar televisión**

Confirmar desde al menos tres metros que resultado, instrucción y contadores son legibles; que
el video permanece fluido y que el tracking no parpadea.

- [ ] **Step 5: Commit**

Commit: `git commit -m "docs(v5): finalize demo operating procedure"`

### Task 5: Paquete offline, verificación V4 y rollback

**Files:**
- Create: `tools/package_v5.ps1`
- Create: `RESTaurar_V4.bat`
- Create: `docs/V5_RELEASE.md`
- Create at runtime: `release/inspeccion_visual_v5_<version>`

**Interfaces:**
- Script: `tools/package_v5.ps1 -Version 5.0.0-rc1`
- Produces: carpeta, ZIP, `MANIFEST_SHA256.txt`, reporte de pruebas y entorno bloqueado.

- [ ] **Step 1: Verificar puertas antes de empaquetar**

El script exige reportes automáticos, soak, batería física y ensayo aprobados. Si falta uno,
termina con código 2 y no crea ZIP.

- [ ] **Step 2: Crear paquete offline**

Incluir código V5, configuraciones, modelo ONNX, launchers, fuentes/licencias requeridas,
entorno o ruedas locales y manual. Excluir raw_sessions, checkpoints PyTorch y caches.

- [ ] **Step 3: Probar sin red**

Deshabilitar temporalmente red, arrancar desde `ABRIR_DEMO_V5.vbs`, completar tres ciclos y
cerrar con X. Expected: funcionamiento completo y logs locales.

- [ ] **Step 4: Verificar V4**

Run:

```powershell
.venv\Scripts\python.exe tools\v5_snapshot.py verify
.venv\Scripts\python.exe -m pytest -q
```

Expected: hashes V4 idénticos y todas las pruebas pasan.

- [ ] **Step 5: Probar rollback**

Ejecutar `RESTAURAR_V4.bat`; debe abrir el launcher V4 existente sin borrar V5 ni datos.

- [ ] **Step 6: Commit y tag de candidato**

Run:

```powershell
git add tools docs ABRIR_DEMO_V5.bat ABRIR_DEMO_V5.vbs RESTAURAR_V4.bat
git commit -m "release: package inspection visual v5 candidate"
git tag v5.0.0-rc1
```

Expected: tag local creado sólo después de todas las puertas aprobadas.
