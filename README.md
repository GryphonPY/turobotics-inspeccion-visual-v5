# TuRobotics — Sistema de Inspección Visual Asistida por Computadora (V5)

![Estado](https://img.shields.io/badge/Estado-Liberado_V5.0-success?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white)
![Plataforma](https://img.shields.io/badge/Plataforma-Windows_x64-informational?style=for-the-badge&logo=windows&logoColor=white)
![Inferencia](https://img.shields.io/badge/Motor-ONNX_CPU-orange?style=for-the-badge)

Sistema industrial autónomo de visión por computadora para el control de calidad e inspección de ensambles mecánicos de 10 componentes. Diseñado para operar en tiempo real sobre hardware estándar (CPU), garantizando alta repetibilidad sin requerir GPU dedicada ni conexión a internet en piso de manufactura.

---

## 📌 Características Principales

- **Rectificación Geométrica Robusta:** Corrección de perspectiva y escalado milimétrico en tiempo real utilizando un patrón perimetral de 4 marcadores ArUco (Diccionario 4x4_50).
- **Segmentación Invariante:** Procesamiento en escala de grises y gradientes morfológicos, eliminando la dependencia crítica de la temperatura de color o cambios en la iluminación ambiental.
- **Fusión Híbrida CPU (ONNX + Geometría):** 
  - Evaluación geométrica de 10 anclas locales contra mapa de referencia espacial.
  - Modelo de red neuronal optimizado en formato ONNX (`presence_v1.onnx`) para clasificación y desempate en zonas de alta incertidumbre.
- **Votación Temporal Multi-Fotograma:** Votador por ventana deslizante (5 a 9 cuadros consecutivos estables) que elimina falsos positivos/negativos por vibración o desenfoque transitorio.
- **Detección de Manipulación y Manos:** Bloqueo preventivo automático durante la colocación y retiro de la pieza (`HOLD / EVALUANDO`).
- **HMI Industrial en PySide6 / Qt6:**
  - Interfaz gráfica moderna a pantalla completa.
  - Selector interactivo de dispositivos de video con vista previa y validación de resolución (mínimo 720p).
  - Indicadores visuales claros de estado por componente (C01 a C10) y dictamen global (`PASA / NO PASA / CAPTURA NO CONFIABLE`).
  - Panel de telemetría y diagnóstico en vivo con tecla `F2`.

---

## 📁 Estructura del Repositorio

```text
├── config/                  # Configuraciones JSON de cámara, umbrales y plantilla PDF oficial
│   ├── v5/camera.json       # Parámetros y resolución de cámara
│   ├── v5/decision.json     # Pesos y tolerancias de decisión
│   └── plantilla_inspeccion_carta_v1.pdf # Tablero de calibración ArUco para imprimir
├── data/                    # Modelos ONNX y matrices de referencia precompiladas
│   ├── v5/models/           # Red neuronal ONNX y manifiestos de integridad
│   ├── v5/references/       # Mapas de referencia geométrica (.npz / .json)
│   ├── models/              # Clasificadores auxiliares (.joblib)
│   └── references/          # Descriptores espaciales de componentes
├── docs/                    # Especificaciones técnicas, manuales de operación y presentación
│   ├── OPERACION_DEMO_V5.md # Manual de usuario en estación de trabajo
│   ├── V5_BATERIA_FISICA.md # Protocolo de pruebas físicas y validación
│   └── Presentacion_Inspeccion_Visual_V5.pdf # Deck técnico de presentación
├── src/                     # Código fuente modular
│   ├── inspection_v5/       # Motor V5: Pipeline, alineación, inferencia y GUI Qt6
│   └── inspection_v4/       # Capa base de procesamiento y utilidades de visión
├── tests/                   # Pruebas unitarias y de regresión
├── tests_v5/                # Batería de pruebas automatizadas para el pipeline V5
├── tools/                   # Herramientas de calibración, benchmarking y packaging
├── ABRIR_DEMO_V5.bat        # Lanzador principal de la aplicación con consola de logs
├── ABRIR_DEMO_V5.vbs        # Lanzador silencioso en segundo plano (para piso/demo)
├── CAMBIAR_CAMARA_V5.bat    # Selector rápido para cambiar dispositivo de video
├── INSTALAR_V5.bat          # Script de instalación automática en 1 clic
├── pyproject.toml           # Definición formal del paquete y dependencias
└── setup.ps1                # Script PowerShell de aprovisionamiento del entorno
```

---

## 🛠️ Requisitos del Sistema

1. **Hardware:**
   - Laptop o PC con Windows 10 u 11 (64 bits).
   - Procesador Intel Core i3 / AMD Ryzen 3 o superior.
   - 4 GB de memoria RAM disponibles.
   - Cámara web USB o celular conectado como cámara (ej. DroidCam, Iriun Webcam) con resolución mínima de **1280 × 720 px**.
2. **Software:**
   - Python 3.11 o superior instalado (agregado al PATH).
   - Conexión a internet **únicamente durante la primera instalación** (para descargar librerías).

---

## 🚀 Instalación Rápida (Paso a Paso en Nueva PC)

### 1. Clonar el repositorio
```bash
git clone https://github.com/TU_USUARIO/turobotics-inspeccion-visual-v5.git
cd turobotics-inspeccion-visual-v5
```

### 2. Ejecutar el instalador automático
Haz doble clic sobre el archivo **`INSTALAR_V5.bat`** (o ejecuta en PowerShell):
```powershell
.\setup.ps1
```
Este script:
- Localiza tu instalación de Python automáticamente.
- Crea el entorno virtual aislado `.venv`.
- Actualiza `pip` y descarga todas las dependencias requeridas (`PySide6`, `opencv-contrib-python`, `onnxruntime`, `scikit-learn`, `numpy`, `pillow`).
- Registra el paquete en modo editable.

---

## 🕹️ Operación del Sistema

### 1. Preparación Física de la Estación
1. Imprime el archivo `config/plantilla_inspeccion_carta_v1.pdf` en tamaño Carta al **100% de escala** (sin ajustar ni reducir márgenes).
2. Pega la hoja sobre una superficie plana y rígida.
3. Posiciona la cámara cenitalmente (desde arriba) de modo que los 4 marcadores ArUco sean completamente visibles en el encuadre.

### 2. Ejecutar la Demo
Haz doble clic en **`ABRIR_DEMO_V5.bat`** (o `ABRIR_DEMO_V5.vbs`):
1. **Selector de Cámara:** En la ventana inicial, selecciona la cámara conectada y confirma la resolución.
2. **Inspección Autónoma:**
   - Coloca el ensamble dentro del rectángulo negro delimitado en la plantilla.
   - El sistema detectará la estabilidad, evaluará los 10 componentes en tiempo real y emitirá el dictamen en pantalla:
     - 🟢 **10/10 PRESENTES (PASA):** Ensamble completo y correcto.
     - 🔴 **NO PASA (FALTANTES):** Muestra con exactitud qué componentes (C01–C10) faltan o están desalineados.
     - 🟡 **CAPTURA NO CONFIABLE / HOLD:** Si los marcadores están obstruidos, hay exceso de movimiento o desenfoque.
3. **Ciclo Siguiente:** Retira la pieza. En cuanto el área queda libre, puedes ingresar la siguiente pieza sin necesidad de presionar teclas.

### 3. Controles y Atajos de Teclado
- **`ESC` / Botón Salir:** Cierra la aplicación y libera los subprocesos de video.
- **`F2`:** Activa / desactiva la superposición de telemetría y diagnósticos de visión.
- **`CAMBIAR_CAMARA_V5.bat`:** Abre directamente el selector para cambiar de webcam.

---

## 🧪 Pruebas Automatizadas y Validación

Para ejecutar la suite de pruebas unitarias y de integración:

```powershell
# Ejecutar pruebas con pytest
.venv\Scripts\python.exe -m pytest tests tests_v5 -v

# Validación estática de código con ruff
.venv\Scripts\python.exe -m ruff check src tools tests_v5
```

---

## 📄 Licencia y Créditos

Proyecto desarrollado como parte de la solución de manufactura avanzada e inspección de calidad automatizada para **TuRobotics** (2026).
Todos los derechos reservados.
