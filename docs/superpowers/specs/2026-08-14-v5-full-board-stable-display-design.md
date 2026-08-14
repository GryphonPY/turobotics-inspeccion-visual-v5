# V5: Vista completa y estabilidad del tablero

## Problema

La V5 está mostrando únicamente el recorte interno de inspección de 320 × 560 px. Esto oculta el contexto de la hoja y hace más evidente cualquier variación pequeña de la homografía. La estimación de movimiento del recorte puede cambiar aunque la cámara y la pieza estén quietas, por lo que el estado permanece en `ESTABILIZANDO`.

Además, el texto `ESTABILIZANDO` puede rebasar el ancho disponible del panel de resultados.

## Decisiones aprobadas

- La vista principal volverá a mostrar la hoja completa rectificada, como la V4.
- El recorte de 8 × 14 cm seguirá existiendo únicamente como entrada interna del analizador.
- Si aún no se detectan los cuatro ArUco, se mostrará la cámara completa sin fingir que es una cámara desconectada.
- La homografía usada para presentación y análisis tendrá una retención temporal para evitar saltos entre fotogramas válidos.
- La medición de movimiento se hará sobre una versión suavizada y con tolerancia a ruido de captura.
- El cambio no modifica las referencias, los componentes C01–C10 ni la calibración ya capturada.
- El titular de estabilidad debe caber completo en el panel y en la vista de video.

## Diseño técnico

`BoardTracker.observe` conservará dos imágenes conceptualmente separadas:

1. tablero completo canónico, usado para la vista de usuario;
2. ROI de 8 × 14 cm, usado por `PresenceAnalyzer` y `V5Inspector`.

El runtime publicará el tablero completo cuando exista una homografía válida y usará el fotograma bruto sólo cuando el tablero todavía no sea confiable. La ROI no se eliminará ni cambiará de escala para el motor.

La estabilidad de la homografía se resolverá conservando la última transformación aceptada durante una ventana corta y rechazando cambios bruscos que no estén respaldados por una reproyección válida. La presencia aplicará suavizado mínimo antes de calcular movimiento; no se usará color ni se alterará la lógica de componentes.

La UI ajustará el tamaño y el ancho disponible del titular, y conservará los colores semánticos actuales.

## Verificación

- Prueba unitaria: la vista pública usa tablero completo con homografía válida y fotograma bruto cuando no hay tablero.
- Prueba de estabilidad: pequeños cambios sintéticos de homografía no fuerzan reinicio continuo del estado live.
- Prueba visual: la hoja completa, los cuatro ArUco y el rectángulo central son visibles; `ESTABILIZANDO` no se corta.
- Suite completa de V4/V5, Ruff y verificación de archivos protegidos.
