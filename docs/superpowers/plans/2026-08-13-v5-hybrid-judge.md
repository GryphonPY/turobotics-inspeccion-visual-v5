# V5 Hybrid Judge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir un juez conservador que combine geometría, diez salidas visuales y evidencia local sin depender del color.

**Architecture:** Los recortes alineados se convierten a tres canales: gris, máscara y bordes. Un modelo compacto ONNX predice presencia C01-C10 y ensamble global; un juez de fusión exige acuerdo con controles geométricos y temporales.

**Tech Stack:** Python 3.11, OpenCV, NumPy, PyTorch/Torchvision para entrenamiento, ONNX, ONNX Runtime para demo, scikit-learn para métricas, pytest y Ruff.

## Global Constraints

- No reutilizar las regiones deformadas de `reference_set_v1` como verdad espacial V5.
- No usar información RGB/HSV como entrada del juez.
- Separar datos por ronda o clip completo, nunca por fotograma.
- La sesión adversarial final no participa en entrenamiento ni elección de umbrales.
- PyTorch no será dependencia del ejecutable de demostración.
- Cero falsos `PASA` es condición necesaria de liberación.
- Si falta el modelo o su hash no coincide, la app debe entrar en `FAULT`, no usar fallback permisivo.

---

## File map

- `src/inspection_v5/alignment.py`: pose y recorte normalizado.
- `src/inspection_v5/features.py`: canales gris/máscara/bordes.
- `src/inspection_v5/geometry_judge.py`: controles globales y anclas locales.
- `src/inspection_v5/model_runtime.py`: ONNX Runtime y manifiesto.
- `src/inspection_v5/fusion.py`: reglas por fotograma y consenso temporal.
- `training_v5/dataset.py`: grupos por sesión/ronda/clip.
- `training_v5/model.py`: MobileNetV3 Small multietiqueta.
- `training_v5/train.py`: entrenamiento reproducible.
- `training_v5/export.py`: ONNX y hash.
- `tools/capture_challenge_v5.py`: captura adversarial corta.
- `tools/evaluate_v5.py`: reporte congelado.

### Task 1: Inventario y separación segura de datos

**Files:**
- Create: `training_v5/__init__.py`
- Create: `training_v5/dataset.py`
- Create: `tools/build_v5_dataset.py`
- Create: `tests_v5/test_dataset_split.py`
- Create at runtime: `data/v5/dataset/index.jsonl`
- Create at runtime: `data/v5/dataset/split_manifest.json`

**Interfaces:**
- Produces: `Sample(path, session_id, round_id, clip_id, labels: tuple[int, ...])`
- Produces: `group_split(samples, train_rounds, validation_rounds) -> DatasetSplit`

- [ ] **Step 1: Probar que ningún grupo cruza particiones**

```python
def test_group_split_never_leaks_round_or_clip(samples):
    split = group_split(samples, train_rounds={1,2,3,4,5}, validation_rounds={6})
    train_groups = {(x.session_id, x.round_id, x.clip_id) for x in split.train}
    val_groups = {(x.session_id, x.round_id, x.clip_id) for x in split.validation}
    assert train_groups.isdisjoint(val_groups)
```

- [ ] **Step 2: Indexar la sesión existente sin copiar ni reescribir imágenes**

Asignar etiquetas: `OK=(1,1,1,1,1,1,1,1,1,1)` y `Cxx_MISSING` con un único cero.
Usar rondas 1-5 para entrenamiento, ronda 6 para validación y conservar ronda 7 como reto
histórico, no como liberación independiente.

- [ ] **Step 3: Detectar duplicados exactos y perceptuales por grupo**

Guardar SHA-256 y dHash de 64 bits. Los duplicados exactos se indexan una vez. Los duplicados
perceptuales permanecen en su grupo original y nunca cruzan particiones.

- [ ] **Step 4: Ejecutar validación**

Run: `.venv\Scripts\python.exe tools\build_v5_dataset.py --session session_20260813_001845 --verify-only`

Expected: 11 estados presentes, rondas 1-7 identificadas y cero grupos compartidos.

- [ ] **Step 5: Commit**

Commit: `git commit -m "data(v5): create leakage-safe grouped dataset"`

### Task 2: Alineación y canales sin color

**Files:**
- Create: `src/inspection_v5/alignment.py`
- Create: `src/inspection_v5/features.py`
- Create: `tests_v5/test_v5_alignment.py`
- Create: `tests_v5/test_color_invariance.py`

**Interfaces:**
- Produces: `PoseAligner.align(mask, gray) -> AlignedCrop`
- `AlignedCrop`: `gray`, `mask`, `edges`, `matrix`, `rotation_deg`, `pose_score`, `local_focus`
- Produces: `make_model_tensor(aligned: AlignedCrop, size=224) -> np.ndarray` con shape `(3,224,224)`

- [ ] **Step 1: Probar rotación, traslación y ambigüedad de 180 grados**

La prueba debe usar la silueta completa y exigir el mismo tensor estructural a 0, 90, 180 y
270 grados con similitud media >= 0.95 después de alineación.

- [ ] **Step 2: Implementar alineación coarse-to-fine sobre recorte**

Usar PCA para dos hipótesis, correlación a 112 x 112 y refinamiento rígido a 224 x 224. No
permitir escalado mayor de 3%. El score final combina IoU y distancia de bordes.

- [ ] **Step 3: Implementar tres canales exactos**

- Canal 0: gris ecualizado con percentiles 2-98.
- Canal 1: máscara binaria 0/1.
- Canal 2: mapa de distancia de bordes normalizado 0/1.

No leer los canales BGR por separado después de convertir a gris.

- [ ] **Step 4: Ejecutar benchmark**

Run: `.venv\Scripts\python.exe tools\benchmark_v5.py --stage alignment --frames 200`

Expected: percentil 95 <= 25 ms.

- [ ] **Step 5: Commit**

Commit: `git commit -m "feat(v5): normalize pose into color-free tensors"`

### Task 3: Geometría global y anclas locales limpias

**Files:**
- Create: `config/v5/component_anchors.json`
- Create: `src/inspection_v5/geometry_judge.py`
- Create: `tools/render_v5_anchors.py`
- Create: `tests_v5/test_geometry_judge.py`
- Create at runtime: `data/v5/reports/component_anchors.png`

**Interfaces:**
- Produces: `GeometryJudge.evaluate(aligned: AlignedCrop) -> GeometryEvidence`
- `GeometryEvidence`: `usable`, `global_score`, `area_ratio`, `aspect_score`, `local_scores`, `reasons`

- [ ] **Step 1: Definir diez anclas no traslapadas**

Crear polígonos normalizados 0-1 correspondientes a las diez piezas del dibujo validado:
C01/C02 cabeza, C03/C04 primera barra, C05 columna alta, C06/C07 barra central, C08 columna
baja y C09/C10 barra inferior. Intersección entre anclas <= 2% del área menor.

- [ ] **Step 2: Renderizar y verificar anclas**

Run: `.venv\Scripts\python.exe tools\render_v5_anchors.py`

Expected: imagen 224 x 224 con diez colores y etiquetas legibles, sin regiones que atraviesen
toda la figura.

- [ ] **Step 3: Probar rechazo de reacomodo con área parecida**

```python
def test_geometry_rejects_rearranged_equal_area(judge, complete, rearranged):
    assert abs(complete.mask.sum() - rearranged.mask.sum()) / complete.mask.sum() < 0.03
    assert judge.evaluate(complete).usable
    assert judge.evaluate(rearranged).global_score < 0.85
```

- [ ] **Step 4: Implementar métricas**

Combinar IoU de silueta, Chamfer de bordes, área, proporción y ocupación de anclas. Mantener
scores continuos; no elegir umbrales finales en esta tarea.

- [ ] **Step 5: Commit**

Commit: `git commit -m "feat(v5): add clean component anchors and geometry evidence"`

### Task 4: Modelo multietiqueta y entrenamiento reproducible

**Files:**
- Create: `training_v5/model.py`
- Create: `training_v5/train.py`
- Create: `training_v5/metrics.py`
- Create: `config/v5/training.json`
- Create: `tests_v5/test_training_model.py`

**Interfaces:**
- Produces: `V5PresenceNet.forward(batch) -> logits` con shape `(N, 11)`
- Salidas 0-9: C01-C10 presentes; salida 10: ensamble global válido.
- Produces: `train_model(config_path: Path) -> TrainingReport`

- [ ] **Step 1: Añadir dependencias de entrenamiento separadas**

Agregar extra `train = ["torch", "torchvision", "onnx"]` y dependencias runtime
`onnxruntime`, manteniendo instalación demo sin PyTorch.

- [ ] **Step 2: Probar shape, rango y exportabilidad del modelo**

Crear un batch `(2,3,224,224)`, exigir logits `(2,11)` y exportación ONNX con batch dinámico.

- [ ] **Step 3: Implementar MobileNetV3 Small**

Reemplazar la última capa por 11 logits. Inicializar pesos ImageNet, congelar backbone durante
dos épocas y ajustar toda la red después. Semillas Python/NumPy/Torch en 20260813.

- [ ] **Step 4: Implementar augmentations sin color**

Usar brillo, contraste, gamma, blur, ruido, pequeñas rotaciones y borrado local. No usar hue,
saturación ni etiquetas derivadas del amarillo.

- [ ] **Step 5: Entrenar y guardar reporte**

Run: `.venv\Scripts\python.exe -m training_v5.train --config config\v5\training.json`

Expected: `data/v5/models/presence_v1.pt` y reporte JSON con métricas por componente, matrices
de confusión, grupos usados y semillas.

- [ ] **Step 6: Commit de código, no de checkpoint pesado intermedio**

Commit: `git commit -m "feat(v5): train compact multi-label presence model"`

### Task 5: Exportación ONNX y runtime offline

**Files:**
- Create: `training_v5/export.py`
- Create: `src/inspection_v5/model_runtime.py`
- Create: `tests_v5/test_onnx_parity.py`
- Create at runtime: `data/v5/models/presence_v1.onnx`
- Create at runtime: `data/v5/models/presence_v1.manifest.json`

**Interfaces:**
- Produces: `PresenceModel.predict(tensor: np.ndarray) -> ModelEvidence`
- `ModelEvidence`: `component_probabilities`, `global_probability`, `latency_ms`, `model_hash`

- [ ] **Step 1: Exportar con opset soportado por ONNX Runtime instalado**

Usar input `input`, output `logits`, batch dinámico y tensor float32.

- [ ] **Step 2: Probar paridad**

Comparar 32 muestras: diferencia absoluta máxima entre PyTorch y ONNX <= 1e-4.

- [ ] **Step 3: Validar hash antes de cargar**

El manifiesto contiene SHA-256, dimensiones, orden C01-C10, versión de datos y umbrales. Un
hash incorrecto debe lanzar `ModelIntegrityError` y poner el runtime en `FAULT`.

- [ ] **Step 4: Medir inferencia CPU**

Run: `.venv\Scripts\python.exe tools\benchmark_v5.py --stage onnx --frames 500`

Expected: percentil 95 <= 35 ms en la laptop de presentación.

- [ ] **Step 5: Commit**

Commit: `git commit -m "feat(v5): run verified onnx model offline"`

### Task 6: Fusión conservadora y voto temporal adaptativo

**Files:**
- Create: `src/inspection_v5/fusion.py`
- Create: `config/v5/decision.json`
- Create: `tests_v5/test_fusion.py`

**Interfaces:**
- Produces: `HybridJudge.evaluate(aligned) -> FrameVerdict`
- Produces: `AdaptiveVoter.add(frame: FrameVerdict) -> CycleVerdict | None`
- Verdicts: `PASS`, `NO_PASS`, `UNRELIABLE`

- [ ] **Step 1: Probar que desacuerdo nunca produce PASS**

```python
def test_geometry_model_disagreement_is_unreliable(judge):
    verdict = judge.fuse(geometry=good_geometry(), model=model_missing("C04"))
    assert verdict.verdict is Verdict.UNRELIABLE
    assert "judge_disagreement" in verdict.reasons
```

- [ ] **Step 2: Implementar zonas de decisión configurables**

`PASS` exige geometría válida, global ONNX sobre umbral alto y diez componentes sobre sus
umbrales altos. `NO_PASS` exige evidencia baja consistente. Valores intermedios o desacuerdo
son `UNRELIABLE`.

- [ ] **Step 3: Implementar voto adaptativo**

Cerrar con cinco fotogramas si son unánimes y todos tienen margen alto. Extender a nueve si
hay un voto dudoso. Al llegar a nueve sin consenso, devolver `UNRELIABLE`.

- [ ] **Step 4: Medir latencia completa offline**

Expected: análisis por frame p95 <= 80 ms y decisión mediana <= 0.9 s con secuencia estable.

- [ ] **Step 5: Commit**

Commit: `git commit -m "feat(v5): fuse geometry model and adaptive consensus"`

### Task 7: Captura adversarial corta y evaluación congelada

**Files:**
- Create: `tools/capture_challenge_v5.py`
- Create: `tools/evaluate_v5.py`
- Create: `docs/v5_challenge_capture.md`
- Create: `tests_v5/test_challenge_split.py`
- Create at runtime: `data/v5/challenge/<session_id>`
- Create at runtime: `data/v5/reports/release_candidate.json`

**Interfaces:**
- Produces clips con `cycle_id`, `condition_id`, `expected_verdict`, `missing_ids` y hashes.
- Produces reporte con `false_passes`, `false_rejects`, latencias y matriz de resultados.

- [ ] **Step 1: Construir asistente de 60 ciclos cortos**

Mostrar instrucciones grandes y permitir repetir sólo el ciclo fallido. Guardar clips, no
fotogramas sueltos etiquetados manualmente.

- [ ] **Step 2: Capturar con el usuario presente**

Ejecutar 20 correctos, 20 faltantes simples, 10 reacomodados y 10 capturas inseguras bajo dos
iluminaciones. Esta es la única tarea que requiere manipulación física.

- [ ] **Step 3: Congelar mitad final antes de calibrar**

Escribir hashes de clips de prueba en `challenge_holdout_manifest.json`; las herramientas de
entrenamiento deben rechazar esas rutas.

- [ ] **Step 4: Evaluar**

Run: `.venv\Scripts\python.exe tools\evaluate_v5.py --split challenge-holdout`

Expected: cero falsos `PASA`. Si falla, no modificar holdout ni bajar umbrales; ampliar datos
de desarrollo o corregir el juez y repetir evaluación completa.

- [ ] **Step 5: Verificar V4 y commit**

Run: `.venv\Scripts\python.exe tools\v5_snapshot.py verify`

Commit: `git commit -m "test(v5): freeze adversarial judge evaluation"`
