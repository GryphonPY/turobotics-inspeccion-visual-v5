# Recolección adaptativa de fotogramas

## Problema comprobado

En la laptop de presentación, el análisis geométrico y el auxiliar C08 producen
aproximadamente dos decisiones utilizables por segundo. El ciclo actual termina a
los tres segundos, por lo que conserva sólo cinco o seis decisiones, aunque exige
nueve para votar. El resultado inevitable es `CAPTURA NO CONFIABLE — CAPTURA
INSUFICIENTE`.

## Comportamiento aprobado

- `COLLECTING` no finalizará por tiempo.
- Cada fotograma inválido se descartará sin cancelar los ya aceptados.
- El ciclo finalizará inmediatamente al reunir `min_valid_frames` decisiones
  utilizables; actualmente son nueve.
- La pantalla mostrará `ANALIZANDO X/9` durante la recolección.
- `R` seguirá permitiendo reiniciar manualmente un ciclo que no progresa.
- No cambiarán referencias, modelos, umbrales de componentes, votación temporal,
  captura de calibración ni la V3.

## Seguridad y recuperación

La corrección no reduce el número de votos: conserva los nueve requeridos. Si la
hoja, la pieza o el enfoque dejan de ser válidos, el flujo continuará mostrando la
causa correspondiente y no emitirá `PASA`. Si no puede obtener nueve decisiones,
esperará hasta que las condiciones mejoren o el operador pulse `R`.

## Verificación

Una prueba de regresión simulará que transcurrieron más de tres segundos con sólo
ocho decisiones y comprobará que el ciclo sigue recolectando. Al agregar la novena,
deberá producir el resultado temporal. La suite completa, el análisis estático y la
evaluación congelada de la ronda 7 deberán continuar pasando.
