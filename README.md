# Inspección Visual V4

V4 es la versión paralela de la demo de inspección del ensamble LEGO. La V3 original permanece en la carpeta `inspeccion_visual`; no se mezclan sus registros, modelos ni datasets con V4.

## Requisitos físicos

1. Pega la plantilla `config/plantilla_inspeccion_carta_v1.pdf` sobre una base rígida y plana.
2. Imprime siempre al 100%, sin “ajustar a página”.
3. Coloca la cámara del celular desde arriba, de forma que se vean los cuatro marcadores.
4. Conecta el celular como webcam y cierra aplicaciones que puedan cambiar la exposición.
5. Coloca el ensamble dentro del rectángulo central de 8 × 14 cm.

## Instalación

En PowerShell:

```powershell
Set-Location 'C:\Users\axel2\Desktop\quinto cuatri\proyecto_manufactura-integradora\inspeccion_visual_v4'
.\setup.ps1
```

El sistema funciona en CPU y no necesita internet después de instalar las dependencias.

## Diagnóstico

```powershell
.\diagnostic.ps1
```

El diagnóstico enumera cámaras y comprueba los valores de tablero. Si una cámara entrega menos de 1280 × 720, se rechaza para la demo.

## Captura de referencias

```powershell
.\run_capture.ps1
```

El asistente solicita once estados: `OK` y `C01_MISSING` a `C10_MISSING`. Pulsa ENTER para iniciar cada grabación de 10 segundos. Repite siete rondas cambiando posición y orientación: las rondas 1–6 calibran y la ronda 7 queda reservada como prueba independiente. Los datos se guardan en `data/raw_sessions/<session_id>` como ROI rectificado en gris, muestreado y limitado a 30 fotogramas por estado para mantener el consumo de memoria estable.

Cuando exista una sesión completa, puedes construir la referencia explícitamente:

```powershell
$env:PYTHONPATH = '.\src'
$python = & .\resolve_python.ps1
& $python .\tools\validate_session.py session_YYYYMMDD_HHMMSS
& $python .\tools\build_reference.py session_YYYYMMDD_HHMMSS --training-rounds 1 2 3 4 5 6
```

La referencia congelada queda en `data/references/reference_set_v1.{json,npz}`.

Después de generarla, evalúa la ronda 7 reservada:

```powershell
& $python .\tools\evaluate_session.py session_YYYYMMDD_HHMMSS
```

La evaluación debe terminar con `all_correct: true` antes de usar la demo.

La sesión física es el único insumo que todavía no está incluido en este paquete:
`data/references/reference_set_v1.{json,npz}` no se crea con imágenes sintéticas ni con
la V3. Durante la captura, conserva la cabeza amarilla arriba y retira únicamente el
componente que indique el asistente. La numeración C01–C10 es posicional y debe
confirmarse físicamente contra el esquema mostrado en pantalla; si una región no se
separa con evidencia suficiente, la calibración queda bloqueada como `UNRESOLVED`.

## Demo

```powershell
.\run_demo.ps1
```

La demo usa varios fotogramas. `PASA` exige que los diez componentes pasen el voto temporal. Si la hoja, la cámara, el enfoque o la pieza no son confiables, muestra `NO PASA` con la causa y no inventa una aprobación.

## Teclas

- `R`: reiniciar el ciclo actual.
- `Z`: reiniciar contadores de demostración.
- `C`: buscar y cambiar a la cámara elegible de mayor resolución.
- `ESPACIO`: repetir el ciclo sin borrar contadores.
- `Q` o `ESC`: salir.

## Verificación

```powershell
$python = '.\.venv\Scripts\python.exe'
& $python -m compileall -q .\src
& $python -m pytest -q
```

Si `python` apunta al alias de Microsoft Store, los scripts usan automáticamente el
intérprete ejecutable localizado por `resolve_python.ps1`.

La V4 no se libera como demo final hasta probar piezas completas, cada estado faltante, desplazamientos, rotaciones, mala calidad de captura y desconexión de cámara.
