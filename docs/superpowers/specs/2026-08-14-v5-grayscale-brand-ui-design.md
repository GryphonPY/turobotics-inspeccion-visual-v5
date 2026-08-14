# Diseño visual V5: TuRobotics / Inspección Visual

## Objetivo

Hacer que la demo se lea bien en una televisión y que el panel no parezca una interfaz azul
genérica. El estilo base será negro, gris y blanco; verde, rojo y ámbar quedarán reservados
para comunicar estado.

## Decisiones

- La cabecera mostrará el logo TuRobotics local y el texto `TUROBOTICS / INSPECCIÓN VISUAL`.
- El video ocupará la mayor parte de la pantalla.
- El panel derecho conservará el resultado grande, la instrucción y los botones.
- El mapa seguirá la silueta validada en V4: C01–C02 arriba, C03–C04, C05 al centro,
  C06–C07, C08 y C09–C10 abajo.
- El mapa tendrá una altura fija suficiente para que C09 y C10 nunca queden cortados.
- Los contadores serán tres tarjetas independientes para evitar texto encimado.
- El launcher `.vbs` iniciará Python directamente y ocultará la consola; las excepciones se
  registrarán en `logs/v5_launcher.log`.

## Alcance

Sólo se modifican la interfaz y los launchers de V5. La lógica de inspección y los archivos de
V4 quedan fuera del cambio.

## Verificación

- Render offline de `ÁREA LIBRE`, `10/10 PRESENTES` y `NO PASA`.
- Los tres estados muestran C01–C10 completos sin solapamientos.
- Suite de widgets y suite completa pasan.
- `tools/v5_snapshot.py verify` confirma que V4 no cambió.
