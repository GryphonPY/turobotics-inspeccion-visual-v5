# Batería física de liberación V5

Esta prueba se ejecuta con la laptop, el Android, la hoja plana y el procedimiento de la
presentación. Las etiquetas se fijan antes de iniciar cada lote y el operador no puede
cambiarlas después de ver el resultado.

## Lotes mínimos

- `complete`: 100 ensambles completos.
- `single_missing`: 20 por cada C01–C10.
- `double_missing`: 20 con dos componentes faltantes.
- `rearranged`: 20 ensambles reacomodados.
- `outside`: 20 piezas parcialmente fuera del rectángulo.
- `hand`: 20 con mano u objeto invadiendo el área.
- `marker`: 20 con un ArUco cubierto.
- `blur`: 20 con desenfoque o movimiento.
- `bad_light`: 20 con iluminación intencionalmente mala.

La herramienta puede ejecutar toda la batería en un solo flujo guiado —440 ciclos— y mostrar
en pantalla qué debe prepararse en cada uno:

```powershell
.venv\Scripts\python.exe tools\run_v5_campaign.py --mode release --camera 1
```

El operador sólo pulsa ENTER cuando la escena indicada esté lista. El programa fija el caso,
guarda el identificador y no permite cambiar la etiqueta después de ver el resultado. ESC sale
guardando los ciclos ya terminados. El reporte se firma después de cada ciclo terminado: si la
ventana se cierra o la cámara falla, al volver a ejecutar el mismo comando se retoma el último
caso válido sin repetirlo. El programa sólo reanuda si coinciden el hash del reporte, la versión
del código y el orden de la batería.

Para comenzar una batería nueva desde cero, aunque exista un reporte parcial, añade `--fresh`:

```powershell
.venv\Scripts\python.exe tools\run_v5_campaign.py --mode release --camera 1 --fresh
```

Para repetir únicamente un lote, ejecuta desde la raíz del proyecto:

```powershell
.venv\Scripts\python.exe tools\run_v5_campaign.py --mode physical --scenario complete --count 100 --camera 1
```

En el flujo completo, la herramienta indica automáticamente el componente que debe retirarse.
En un lote manual, cambia `complete` por el escenario correspondiente y `1` por el índice real del Android.
Pulsa ENTER cuando la escena esté lista; ESC detiene sin alterar las etiquetas ya guardadas.
Cada reporte queda en `data/v5/reports/physical_release_<fecha>.json` y su SHA-256 se guarda
al lado. No se edita un reporte congelado.

## Criterios

- Cero falsos `PASA` en cualquier defecto.
- Al menos 99 de 100 completos correctos.
- Capturas inseguras: `CAPTURA NO CONFIABLE` o `NO PASA`, nunca `PASA`.
- Cero dobles conteos y retirada automática.

Un fallo bloquea la liberación. No se bajan umbrales; se conserva el reporte, se corrige la
causa y se repite la batería afectada completa.

## Ensayo de resistencia ya ejecutado

La prueba offline de 30 minutos terminó correctamente en `data/v5/reports/soak_20260814_065528.json`:

- 40,980 muestras procesadas.
- Previsualización estable de 24 FPS.
- Tiempo de procesamiento p95: 53.25 ms.
- Tiempo de decisión p95: 53.23 ms.
- Retirada detectada p95: 220 ms.
- Sin errores en `soak_30m_stderr.log`.
- El reporte conserva `release_ready=true` y no sustituye la batería física.

Esta evidencia demuestra estabilidad del motor bajo una fuente repetible. La liberación final
sigue bloqueada hasta terminar los 440 casos físicos y el ensayo de presentación.
