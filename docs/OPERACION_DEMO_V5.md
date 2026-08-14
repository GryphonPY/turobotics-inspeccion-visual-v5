# Operación de demo V5

1. Fija la hoja completamente plana sobre cartón rígido y conecta el Android como webcam.
2. Abre `ABRIR_DEMO_V5.vbs`, elige la cámara en la vista previa y pulsa aceptar.
3. Confirma que los cuatro ArUco aparezcan en verde y coloca la pieza dentro del rectángulo.
4. Espera el resultado. La app detecta entrada, estabilidad, inspección y retirada sin pulsar
   Espacio. Retira la pieza y coloca la siguiente cuando aparezca `ÁREA LIBRE`.
5. Para la presentación usa pantalla completa. `F2` sólo muestra diagnóstico técnico; no cambia
   umbrales. `ESC`, `X` o `SALIR` cierran cámara y trabajadores.

## Recuperación

- Android no aparece: ejecuta `CAMBIAR_CAMARA_V5.bat`, selecciona el índice en la vista previa y
  acepta.
- Cámara desconectada: reconecta el teléfono, vuelve a abrir el selector y reinicia la demo.
- Tablero no disponible: endereza la hoja y verifica los cuatro ArUco.
- Resultado no confiable: no muevas la pieza, espera estabilidad y repite.
- Fallo persistente: cierra V5 y ejecuta `RESTaurar_V4.bat` para volver a la demo de respaldo.

Los logs se guardan en `logs/v5_runtime.jsonl` y los lanzadores en `logs/v5_launcher.log`.
Durante la presentación no se ajustan thresholds ni se entrena el modelo.
