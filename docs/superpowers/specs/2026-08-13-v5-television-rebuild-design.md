# Inspección Visual V5 — Diseño aprobado para demo en televisión

## Resultado buscado

Construir una V5 paralela que conserve V4 como respaldo y convierta la demo en una
aplicación automática, rápida, conservadora y visualmente presentable en una televisión
1920 x 1080. La pieza se inspeccionará sobre la hoja ArUco existente, con el celular como
webcam, sin depender de internet, GPU ni del color de los LEGO.

La prioridad de decisión es evitar falsos `PASA`. Cuando la captura o los clasificadores no
sean concluyentes, el resultado será `CAPTURA NO CONFIABLE`, nunca una aprobación por
omisión.

## Hallazgos que justifican V5

- V4 rectifica dos veces el tablero completo por fotograma.
- La calidad permite aprobar el enfoque usando los ArUco aunque la pieza esté borrosa.
- La alineación cuesta aproximadamente 68 ms y se ejecuta en el mismo hilo de la interfaz.
- El percentil 95 observado de decisión es 6.56 s.
- La retirada depende de que `PieceObservation.valid` sea falso durante 700 ms.
- Las regiones aprendidas C01-C10 no son locales: C01 abarca 419 px de alto y C09/C10 se
  traslapan aproximadamente 30%.
- El holdout 66/66 procede de una ronda de la misma sesión de captura y no contiene una
  batería independiente de ensambles reacomodados.
- La interfaz actual está dibujada con OpenCV en un lienzo fijo de 1280 x 800.
- El repositorio sólo tiene un commit base y la mayor parte del trabajo actual no está
  consolidado en Git.

## Límites y preservación

- No modificar algoritmos, referencias, modelos ni launchers de V4 durante el desarrollo.
- Crear `src/inspection_v5`, `config/v5`, `data/v5` y launchers V5 nuevos.
- Conservar las 2171 capturas de `session_20260813_001845` sin moverlas ni reescribirlas.
- Crear un snapshot Git recuperable antes del primer cambio funcional.
- No exigir repetir las siete rondas de calibración.
- Permitir una captura adversarial corta de 10-15 minutos; la liberación del juez nuevo
  depende de esa prueba independiente.
- No usar amarillo, gris ni ningún otro color como regla de calidad o presencia.
- El modo demo debe funcionar sin consola visible y cerrarse con el botón de la ventana.

## Arquitectura de ejecución

La aplicación se separará en cuatro responsabilidades concurrentes:

1. `CameraWorker`: mantiene únicamente el fotograma más reciente.
2. `TrackingWorker`: detecta tablero, ocupación, movimiento y retirada a baja resolución.
3. `InspectionWorker`: analiza recortes estables sin bloquear cámara ni interfaz.
4. `QtPresentation`: renderiza a 60 Hz y consume estados inmutables del motor.

No se utilizarán colas ilimitadas. Cada canal conservará el dato más reciente y descartará
trabajo obsoleto.

## Flujo de procesamiento

1. Detectar ArUco en una copia reducida del fotograma.
2. Escalar las esquinas a resolución original y calcular una homografía.
3. Reutilizar la homografía hasta 300 ms mientras el tablero permanezca estable.
4. Rectificar directamente el ROI a 320 x 560 para seguimiento.
5. Detectar `EMPTY`, `ENTERING`, `STABILIZING`, `READY`, `INSPECTING`, `RESULT` y
   `REMOVING` mediante ocupación y movimiento con histéresis.
6. Cuando la pieza esté estable, producir recortes de análisis de 320 x 560.
7. Verificar enfoque local de la pieza; la nitidez de los marcadores no puede sustituirlo.
8. Normalizar pose sin escalado libre.
9. Ejecutar geometría, modelo visual y evidencia local.
10. Fusionar cinco fotogramas de alta confianza; extender hasta nueve cuando haya duda.
11. Emitir `PASA`, `NO PASA` o `CAPTURA NO CONFIABLE`.
12. Liberar el ciclo al detectar área vacía durante 200 ms.

## Juez híbrido

El juez tendrá tres votos independientes:

- Geometría global: área, proporción, silueta, pose y compatibilidad estructural.
- Modelo visual: clasificador multietiqueta pequeño con diez salidas C01-C10 y una salida
  global de ensamble válido.
- Evidencia local: ocupación, bordes y uniones dentro de diez anclas geométricas limpias.

El modelo recibirá tres canales sin color: gris normalizado, máscara y bordes. Se entrenará
con transferencia sobre una red compacta y se exportará a ONNX. PyTorch será dependencia
de entrenamiento, no de la demo. La demo sólo cargará `onnxruntime`.

Reglas de liberación:

- `PASA`: todos los controles duros válidos, geometría aceptada, salida global aceptada,
  C01-C10 presentes y consenso temporal.
- `NO PASA`: defecto consistente y localizado, o geometría incompatible consistente.
- `CAPTURA NO CONFIABLE`: enfoque insuficiente, desacuerdo entre jueces, probabilidad en
  zona gris, tablero inestable o menos de cinco análisis utilizables.

Los umbrales se congelarán usando una sesión de desarrollo y se evaluarán en una sesión
independiente. Ningún umbral se ajustará observando el resultado final de liberación.

## Modo live

La retirada se basará en ocupación, no en validez completa de segmentación.

- `occupied_ratio >= 0.35`: pieza presente.
- `occupied_ratio <= 0.12`: área vacía.
- Los valores intermedios conservan el estado anterior.
- Vacío confirmado: tres observaciones consecutivas y al menos 200 ms.
- Estabilidad: movimiento bajo durante 350 ms.
- Si una mano cubre marcadores, se conserva el ciclo sin declararlo vacío.
- Al retirar la pieza, el video vuelve inmediatamente a live y la tarjeta del último
  resultado pasa al historial lateral.

## Rendimiento objetivo

- Previsualización: 30 FPS capturados y mínimo 24 FPS visibles.
- Interfaz: objetivo 60 Hz; nunca menos de 30 Hz por análisis.
- Seguimiento ligero: percentil 95 <= 35 ms.
- Análisis por recorte: percentil 95 <= 80 ms.
- Decisión desde estabilidad: mediana <= 0.9 s y percentil 95 <= 1.5 s.
- Retirada reconocida: mediana <= 0.3 s.
- Sin cola acumulativa ni crecimiento continuo de memoria durante 30 minutos.

## Interfaz para televisión

Tecnología: PySide6, ventana adaptable 16:9, fullscreen opcional y fuente del sistema
`Segoe UI Variable` con respaldo `Segoe UI`.

Identidad visual:

- Fondo `#09111F`.
- Paneles `#111C2E`.
- Texto principal `#F4F7FB`.
- Texto secundario `#9FB0C7`.
- Seguimiento cian `#35C2FF`.
- Aprobación verde `#35E36F`.
- Advertencia ámbar `#FFBF3F`.
- Defecto rojo `#FF4D5E`.

Composición:

- Barra superior: `TUROBOTICS | INSPECCION OPTICA`, cámara y estado del sistema.
- 68% izquierdo: video rectificado grande.
- 32% derecho: resultado, conteo C01-C10 y contadores.
- Barra inferior: instrucción operativa y latencia del último ciclo.
- Sobre el video: marco de seguimiento con esquinas, sin cajas temblorosas.
- Modo público: no muestra scores, reproyección ni nombres internos de estados.
- Modo diagnóstico con `F2`: FPS, tiempos por etapa, enfoque local, ArUco, pose, votos y
  archivo de log.

Estados del marco:

- Cian: pieza encontrada.
- Ámbar: estabilizando o capturando.
- Verde: seguimiento bloqueado o aprobación.
- Rojo: defecto confirmado.
- Gris: área vacía.

## Datos y captura adicional

Los datos existentes se reutilizarán como entrenamiento inicial, agrupados por ronda. No se
mezclarán fotogramas de la misma ronda entre entrenamiento y validación.

La captura adversarial corta debe contener:

- 20 ciclos completos correctos con rotaciones y posiciones distintas.
- 2 ciclos por cada componente faltante: 20 ciclos.
- 10 ensambles reacomodados que conserven una silueta parecida.
- 10 ciclos con desenfoque, reflejo o movimiento.
- Dos condiciones de iluminación.

Los clips completos, no los fotogramas, forman la unidad de separación. La última mitad de
la sesión se congela como prueba final y no participa en entrenamiento ni calibración.

## Registros

Cada ciclo guardará JSONL con:

- tiempos por etapa;
- transición de estados;
- ocupación y movimiento;
- enfoque local de pieza y enfoque de marcadores por separado;
- salida geométrica, salida ONNX y evidencia local;
- votos por fotograma y motivo final;
- cámara, resolución y versión/hash de configuración, referencia y modelo.

Se guardará imagen únicamente para `NO PASA`, `CAPTURA NO CONFIABLE` o modo diagnóstico.
Los archivos rotarán por tamaño para no llenar el disco.

## Criterios de liberación

- Cero falsos `PASA` en faltantes simples, dobles y ensambles reacomodados del conjunto final.
- Al menos 29/30 aprobaciones correctas controladas.
- 30/30 defectuosas rechazadas en ensayo de presentación.
- Ninguna decisión se basa en color.
- Percentil 95 de decisión <= 1.5 s.
- Retirada mediana <= 0.3 s.
- Previsualización >= 24 FPS durante análisis.
- Prueba continua de 30 minutos sin bloqueo ni atraso acumulativo.
- Operación offline desde launchers sin consola visible.
- V4 continúa arrancando y sus hashes de archivos protegidos no cambian.

Si cualquier criterio falla, V5 no sustituye a V4 y se conserva el paquete anterior.
