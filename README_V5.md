# V5 — demo para televisión

V5 es la aplicación nueva y paralela. V4 queda intacta como respaldo.

## Abrir la demo

1. Conecta el Android como webcam antes de abrirla.
2. Abre `ABRIR_DEMO_V5.vbs`.
3. Elige la cámara en la ventana de vista previa y pulsa aceptar.
4. Coloca el ensamble dentro del rectángulo negro. La app espera estabilidad, analiza sola y muestra `10/10 PRESENTES`, `NO PASA` o `CAPTURA NO CONFIABLE`.
5. Retira la pieza; después de que el área quede libre puedes colocar la siguiente. No hay que pulsar Espacio.

`CAMBIAR_CAMARA_V5.bat` vuelve a abrir el selector. `ESC` o el botón `Salir` cierran la cámara y los trabajadores. `F2` muestra diagnóstico técnico.

## Qué procesa

- Rectifica la hoja con los cuatro ArUco.
- Segmenta en escala de grises; no usa amarillo ni ningún color como regla.
- Alinea posición y giro.
- Combina silueta global, diez anclas locales y un modelo ONNX CPU.
- Vota cinco fotogramas claros y extiende hasta nueve si existe duda.
- Registra transiciones y errores en `logs/v5_runtime.jsonl`.

## Desarrollo

La referencia V5 se construye con `tools/build_v5_reference.py`. El entrenamiento usa el extra `train`; la demo sólo necesita ONNX Runtime. Los archivos `data/v5/models` contienen el checkpoint y el ONNX con manifiesto SHA-256.

Antes de entregar:

```powershell
.venv\Scripts\python.exe -m pytest tests tests_v5 -q
.venv\Scripts\python.exe -m ruff check src\inspection_v5 src\training_v5 tools tests_v5
.venv\Scripts\python.exe tools\v5_snapshot.py verify
```
