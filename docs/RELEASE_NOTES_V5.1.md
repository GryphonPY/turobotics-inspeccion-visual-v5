# TuRobotics — Inspección Visual V5.1.0

V5.1 es una versión de **hardening y mantenibilidad**. El objetivo fue hacer el sistema más predecible para operación y demo sin cambiar a ciegas los umbrales de decisión que ya estaban calibrados.

## Qué se mejoró

### Configuración centralizada

- El inspector dejó de depender de tamaños y parámetros ocultos en código.
- `roi_output_px`, configuración de presencia de inspección, score mínimo de alineación y ventana del votador salen de `config/v5/runtime.json`.
- El pipeline de entrenamiento reutiliza la misma configuración de ROI, presencia y alineación que inferencia.
- Se eliminaron dimensiones fijas de `PoseAligner`; ahora trabaja con el tamaño real de la máscara de entrada.

### Runtime más seguro entre hilos

- Se agregó serialización explícita del estado compartido entre tracking e inspección.
- Resultados, contadores, transición de ciclo y publicación de estado ya no pueden modificarse simultáneamente desde dos workers.
- Se conserva el comportamiento de descarte de resultados tardíos.
- El reset de contadores publica inmediatamente el estado actualizado.

### Menos I/O durante operación

- La telemetría `tracking_frame` dejó de escribirse en cada cuadro.
- Por defecto se registra a 2 Hz (`tracking_interval_seconds = 0.5`).
- Errores, resultados y cambios de estado continúan registrándose inmediatamente.

### Cámara más tolerante a desconexiones

- Resolución, FPS y número de fallos permitidos antes de reconectar están en `runtime.json`.
- Si una webcam o celular deja de entregar cuadros repetidamente, el worker libera el dispositivo e intenta abrirlo nuevamente.
- La HMI muestra estado de reconexión y vuelve a verde al recuperar la cámara.

### HMI más eficiente

- La UI ya no reconstruye `QImage/QPixmap` cuando el estado público no ha cambiado.
- Esto evita trabajo duplicado cuando el timer de Qt corre más rápido que la cámara.

### Contrato ONNX más estricto

- Se sigue verificando SHA-256 del modelo contra su manifiesto.
- Ahora también se valida que exista exactamente una entrada `input` y una salida `logits`.
- Se valida que la salida tenga exactamente 11 logits (C01–C10 + salida global).
- El sigmoid limita logits extremos para evitar overflow numérico.

### Entrenamiento corregido

- El extractor de entrenamiento usa la misma configuración de runtime que inferencia.
- Las augmentations deterministas ahora cambian entre épocas, manteniendo reproducibilidad por seed.
- Al descongelar MobileNet se conservan el optimizador y sus hiperparámetros; el backbone se agrega como nuevo grupo de parámetros en vez de recrear AdamW con defaults distintos.
- Las rondas `holdout_rounds` ahora sí se evalúan después del entrenamiento.
- La métrica antes llamada `validation_false_passes` pasa a llamarse `validation_label_false_positives`, porque mide falsos positivos a nivel de etiquetas y **no** el false-PASS final del sistema híbrido.
- El reporte nuevo incluye accuracy y falsos positivos de etiquetas para holdout.

### CI y release

- CI mantiene la suite completa en Ubuntu con Qt offscreen.
- Se agregó compilación de fuentes antes de tests.
- Se agregó un smoke test nativo en `windows-latest` para board tracking, presencia, inspector y runtime.
- El workflow de Release también ejecuta smoke tests en Windows antes de construir el portable.
- La publicación ahora toma la versión desde `RELEASE_VERSION`.
- Al cambiar `RELEASE_VERSION` en `main`, GitHub puede construir y publicar automáticamente el Release.
- El release usa `softprops/action-gh-release@v3`, notas externas y falla si el ZIP esperado no fue generado.

## Qué NO se cambió

- No se reemplazó ni reentrenó `presence_v1.onnx`.
- No se modificaron los pesos del modelo.
- No se cambiaron los umbrales actuales de PASS / NO_PASS.
- No se sustituyó el esquema ArUco ni la plantilla física.
- No se introdujo una nueva segmentación experimental de doble polaridad, porque requeriría validación física antes de usarla en una demo o estación real.

## Compatibilidad

- Windows 10/11 x64.
- Python 3.11+ para instalación desde código fuente.
- El ZIP portable no requiere una instalación independiente de Python.
- Se mantiene operación CPU-only con ONNX Runtime.

## Validación de esta versión

La versión debe fusionarse únicamente después de que CI pase en Linux y Windows. El workflow de Release vuelve a ejecutar smoke tests de Windows antes de crear el paquete portable.

La validación física documentada del proyecto sigue siendo la referencia para afirmar desempeño real en piso. Esta versión mejora ingeniería de software y robustez operacional, pero no inventa nuevas métricas físicas ni declara resultados que no hayan sido medidos.
