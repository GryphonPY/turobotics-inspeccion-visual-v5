# Captura challenge V5

Esta es la única captura física que falta para liberar V5. No repite las siete rondas de calibración.

## Procedimiento

1. Conecta el Android como webcam y deja la hoja plana.
2. Abre una terminal en la carpeta del proyecto y ejecuta:

```powershell
.venv\Scripts\python.exe tools\capture_challenge_v5.py --camera 1
```

Usa el índice que corresponda al celular. En cada ciclo la ventana muestra una instrucción grande. Pulsa ENTER sólo cuando la escena esté lista; ESC detiene y permite continuar con `--start N`.

## Qué pide

- Ciclos 1–20: ensamble completo, variando posición y giro.
- Ciclos 21–40: falta C01, C02, …, C10; dos ciclos por componente.
- Ciclos 41–50: ensambles reacomodados para conservar una silueta parecida pero incorrecta.
- Ciclos 51–60: movimiento, mano, reflejo o desenfoque controlado.

La mitad 31–60 queda marcada como `holdout` y no debe entrar a entrenamiento ni a calibración. Si una captura salió mal, no edites el video: repite el ciclo con `--start` después de borrar sólo la sesión incompleta.

Después se evalúa con:

```powershell
.venv\Scripts\python.exe tools\evaluate_v5.py --session challenge_YYYYMMDD_HHMMSS
```

La liberación exige cero falsos PASA. Si aparece alguno, V5 se conserva como candidata y V4 continúa siendo el respaldo.
