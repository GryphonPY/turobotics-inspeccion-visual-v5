# Liberación V5

V5 sólo se empaqueta cuando existen reportes aprobados de campaña de fixtures, soak de
rendimiento, batería física y ensayo visible. El script de paquete falla con código `2` si
falta cualquiera de esas puertas; no genera un ZIP parcial.

## Puertas obligatorias

- Cero falsos `PASA` en fixtures y defectos físicos.
- Al menos 99/100 completos correctos.
- Soak de 30 minutos: UI mínima de 24 FPS, decisión p95 <= 1.5 s, retirada mediana <= 0.3 s y
  crecimiento RSS <= 150 MB.
- Ensayo visible 30/30 completos y 30/30 defectuosos, sin doble conteo.
- Hashes de V4 iguales al snapshot inicial.
- Arranque desde el paquete sin internet ni consola.

## Empaquetado

```powershell
powershell -ExecutionPolicy Bypass -File tools\package_v5.ps1 -Version 5.0.0-rc1
```

El resultado incluye código V5, configuración, ONNX verificado, documentación, launchers,
requirements bloqueados, ruedas locales si existen y `MANIFEST_SHA256.txt`. Se excluyen
`data/raw_sessions`, checkpoints PyTorch, cachés y logs de desarrollo.
