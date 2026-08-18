# TuRobotics — Sistema de Inspección Visual Asistida por Computadora (V5.1)

![Estado](https://img.shields.io/badge/Estado-V5.1.0-success?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white)
![Plataforma](https://img.shields.io/badge/Plataforma-Windows_x64-informational?style=for-the-badge&logo=windows&logoColor=white)
![Inferencia](https://img.shields.io/badge/Motor-ONNX_CPU-orange?style=for-the-badge)
![CI](https://github.com/GryphonPY/turobotics-inspeccion-visual-v5/actions/workflows/ci.yml/badge.svg)

Sistema de visión por computadora para control de calidad e inspección de ensambles mecánicos de 10 componentes. El pipeline combina rectificación geométrica con ArUco, evaluación geométrica local, inferencia ONNX y votación temporal para emitir un dictamen robusto en tiempo real sobre CPU.

---

## 📌 Características principales

- **Rectificación geométrica robusta:** corrección de perspectiva mediante 4 marcadores ArUco (`DICT_4X4_50`).
- **Procesamiento robusto a variaciones visuales:** uso de escala de grises, gradientes y criterios geométricos para reducir sensibilidad a cambios de color e iluminación.
- **Fusión híbrida CPU (ONNX + geometría):**
  - evaluación geométrica de 10 anclas locales;
  - modelo ONNX (`presence_v1.onnx`) como apoyo a la decisión.
- **Votación temporal multi-fotograma:** estabiliza la decisión ante vibración, movimiento o desenfoque transitorio.
- **Estados de seguridad de captura:** el sistema puede bloquear la evaluación cuando la captura no es confiable.
- **HMI en PySide6 / Qt6:** interfaz de operación con selección de cámara, visualización de estados y telemetría.
- **Reconexión automática de cámara:** recupera webcam o celular después de fallos consecutivos de captura.
- **Configuración centralizada:** ROI, parámetros de inspección, cámara y telemetría se controlan desde `config/v5/runtime.json`.
- **Runtime endurecido:** las transiciones compartidas entre tracking e inspección se serializan para evitar carreras entre hilos.

---

## 🧠 Arquitectura general

```text
Cámara
  ↓
Detección ArUco + homografía
  ↓
Rectificación del ROI
  ↓
Evaluación geométrica + inferencia ONNX
  ↓
Fusión de decisiones
  ↓
Votación temporal
  ↓
Dictamen global: PASA / NO PASA / CAPTURA NO CONFIABLE
```

---

## 📁 Estructura del repositorio

```text
├── .github/workflows/       # CI y automatización de releases
├── assets/                  # Recursos visuales
├── config/                  # Configuración del sistema y plantilla de inspección
│   └── v5/                  # Cámara, decisión y parámetros V5
├── data/                    # Modelos y referencias precomputadas
│   └── v5/
│       ├── models/          # Modelos ONNX y manifiestos
│       └── references/      # Referencias geométricas
├── docs/                    # Manuales, protocolos y notas de versión
├── src/
│   ├── inspection_v5/       # Pipeline principal, geometría, inferencia y GUI
│   └── training_v5/         # Código de entrenamiento y preparación de modelos
├── tests/                   # Pruebas unitarias, integración, rendimiento y fixtures
├── tools/                   # Utilidades de calibración, benchmarking y empaquetado
├── RELEASE_VERSION          # Versión utilizada por el workflow de Release
├── ABRIR_DEMO_V5.bat        # Lanzador principal de la demo
├── ABRIR_DEMO_V5.vbs        # Lanzador silencioso
├── CAMBIAR_CAMARA_V5.bat    # Selector rápido de cámara
├── INSTALAR_V5.bat          # Instalación automatizada
├── pyproject.toml           # Metadatos, dependencias y configuración del proyecto
└── setup.ps1                # Aprovisionamiento del entorno
```

---

## 🛠️ Requisitos del sistema

### Hardware

- Windows 10 u 11 de 64 bits.
- CPU Intel Core i3 / AMD Ryzen 3 o superior recomendada.
- 4 GB de RAM disponibles.
- Cámara USB o celular usado como webcam con resolución mínima recomendada de `1280 × 720`.

### Software

- Python 3.11 o superior.
- Conexión a internet durante la instalación inicial de dependencias.

---

## 🚀 Instalación rápida

### 1. Clonar el repositorio

```bash
git clone https://github.com/GryphonPY/turobotics-inspeccion-visual-v5.git
cd turobotics-inspeccion-visual-v5
```

### 2. Ejecutar el instalador automático

En Windows puedes ejecutar:

```powershell
.\setup.ps1
```

O utilizar `INSTALAR_V5.bat`.

El instalador crea el entorno virtual, instala dependencias y registra el paquete en modo editable.

---

## 🕹️ Operación del sistema

### Preparación física

1. Imprime `config/plantilla_inspeccion_carta_v1.pdf` al 100% de escala.
2. Fija la plantilla sobre una superficie plana y rígida.
3. Coloca la cámara de forma que los cuatro marcadores ArUco sean visibles.

### Ejecutar la demo

Ejecuta `ABRIR_DEMO_V5.bat` o `ABRIR_DEMO_V5.vbs`.

El flujo de operación es:

1. seleccionar la cámara;
2. colocar el ensamble dentro de la zona de inspección;
3. esperar a que la captura sea estable;
4. recibir el dictamen global y por componente;
5. retirar la pieza y repetir el ciclo.

### Estados principales

- **PASA:** los 10 componentes cumplen el criterio esperado.
- **NO PASA:** uno o más componentes son detectados como faltantes o fuera de criterio.
- **CAPTURA NO CONFIABLE / HOLD:** la imagen no cumple las condiciones necesarias para emitir un resultado confiable.

---

## ⚙️ Configuración V5.1

`config/v5/runtime.json` concentra la geometría del tablero, tamaño del ROI, detección ArUco, presencia para ciclo, presencia para inspección, calidad mínima, cámara y frecuencia de telemetría.

Los valores de decisión por componente permanecen en `config/v5/decision.json`.

---

## 🧪 Pruebas y calidad de código

Instala las dependencias de desarrollo:

```bash
python -m pip install -e ".[dev]"
```

Ejecuta la suite principal:

```bash
python -m pytest -v
```

Los tests de entrenamiento y paridad PyTorch/ONNX son opcionales. Para incluirlos instala también:

```bash
python -m pip install -e ".[dev,train]"
python -m pytest -v
```

Ejecuta análisis estático:

```bash
python -m ruff check src tools tests
```

GitHub Actions valida la suite completa en Ubuntu y añade smoke tests nativos en Windows para board tracking, presencia, inspector y runtime.

El workflow de Release vuelve a ejecutar smoke tests en Windows antes de construir el portable.

---

## 📊 Validación

El proyecto incluye documentación y pruebas orientadas a validar el sistema frente a escenarios de piezas completas, componentes faltantes, variaciones de colocación y condiciones de captura. Los resultados de validación física deben reportarse únicamente con mediciones obtenidas durante las pruebas reales del sistema.

V5.1 mejora robustez de software, concurrencia, cámara, entrenamiento y empaquetado, pero no sustituye la batería física de validación ni modifica silenciosamente los umbrales calibrados de PASS / NO PASS.

---

## 📄 Licencia y créditos

Proyecto desarrollado como parte de una solución de manufactura avanzada e inspección de calidad automatizada para **TuRobotics** (2026).

Todos los derechos reservados.
