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

Para un lote, ejecuta desde la raíz del proyecto:

```powershell
.venv\Scripts\python.exe tools\run_v5_campaign.py --mode physical --scenario complete --count 100 --camera 1
```

Cambia `complete` por el escenario correspondiente y `1` por el índice real del Android.
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
