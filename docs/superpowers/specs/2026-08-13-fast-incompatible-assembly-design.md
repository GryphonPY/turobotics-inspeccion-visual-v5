# Análisis rápido y ensamble incompatible

## Evidencia del fallo

Los registros de las 08:21–08:22 muestran tablero, calidad y segmentación válidos,
pero cero decisiones utilizables cuando varias piezas estaban separadas. La silueta
no alcanzó el umbral de alineación, por lo que el ciclo permaneció indefinidamente
en `0/9`. Una pieza completa sí alcanzó `9/9` y fue aprobada.

La medición sobre una captura real arrojó aproximadamente 805 ms por análisis:
13 ms de segmentación, 130 ms de alineación y 662 ms de evaluación. La evaluación
recalculaba bordes y normalizaciones completas dentro de cada uno de los diez
componentes. Además, la aplicación rectificaba el mismo cuadro dos veces.

## Comportamiento aprobado

- Nueve alineaciones consecutivas no utilizables producirán
  `NO PASA — ENSAMBLE DESARMADO O DEFORMADO`.
- Una alineación válida reiniciará el contador de incompatibilidad.
- Movimiento durante `COLLECTING` borrará los votos y regresará a
  `STABILIZING`, evitando mezclar dos configuraciones físicas.
- La UI mostrará votos aceptados y descartes por alineación.
- El resultado conservará la última vista rectificada válida y no cambiará el
  estado visual del tablero por cuadros posteriores.

## Optimización sin cambiar puntuaciones

- Precargar bordes, imágenes normalizadas y máscaras booleanas de referencia.
- Normalizar máscara e imagen actual una vez por fotograma.
- Reutilizar en la UI la rectificación calculada por la máquina de estados.
- Mantener exactamente los pesos, umbrales, referencia y modelo auxiliar actuales.

## Verificación

Las pruebas cubrirán el contador persistente, su reinicio y el reinicio por
movimiento. Se comparará el tiempo del evaluador antes y después, se ejecutará la
suite completa y se repetirá la evaluación congelada de la ronda 7.
