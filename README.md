# Observatorio Analítico de Anemia Infantil en el Perú

**Proyecto final — Lenguaje de Ciencia de Datos II · 4.º ciclo · Cibertec**

Dashboard interactivo que analiza la anemia infantil en el Perú a partir de la Encuesta Demográfica y de Salud Familiar (ENDES 2025). El proyecto cubre el ciclo completo: ingesta desde la API de Datos Abiertos, procesamiento y enriquecimiento de variables, y visualización en una aplicación Streamlit orientada a la focalización de intervenciones nutricionales.

🔗 **Aplicación desplegada:** https://cibertec-endes2025.streamlit.app/
📦 **Repositorio:** https://github.com/edsalabs/Cibertec

---

## Tabla de contenido

- [Objetivo](#objetivo)
- [Preguntas de negocio](#preguntas-de-negocio)
- [Estructura del dashboard](#estructura-del-dashboard)
- [Hallazgos principales](#hallazgos-principales)
- [Nota metodológica: el denominador](#nota-metodológica-el-denominador)
- [Arquitectura del proyecto](#arquitectura-del-proyecto)
- [Estructura de archivos](#estructura-de-archivos)
- [Instalación y ejecución](#instalación-y-ejecución)
- [Pipeline de datos y reproducibilidad](#pipeline-de-datos-y-reproducibilidad)
- [Tecnologías](#tecnologías)
- [Buenas prácticas aplicadas](#buenas-prácticas-aplicadas)
- [Limitaciones conocidas](#limitaciones-conocidas)
- [Fuente de datos](#fuente-de-datos)

---

## Objetivo

Identificar los grupos poblacionales y los territorios con mayor riesgo de anemia infantil, combinando variables sociodemográficas, económicas, geográficas y clínicas, para apoyar decisiones de focalización de programas de salud pública.

El análisis es **descriptivo**: identifica asociaciones entre variables, no relaciones de causalidad.

---

## Preguntas de negocio

Las cinco preguntas están implementadas en el dashboard y documentadas en [`notebooks/PreguntasNegocio.ipynb`](notebooks/PreguntasNegocio.ipynb).

| # | Pregunta | Variables principales | Pestaña |
|---|---|---|---|
| 1 | ¿Cómo varía la prevalencia de anemia según el orden de nacimiento del menor? | `hwidx` | 📊 Resumen Epidemiológico |
| 2 | ¿Qué departamentos concentran la mayor prevalencia y cómo se distribuye la muestra? | `ubigeo`, `nombre_departamento` | 🗺️ Impacto Geográfico |
| 3 | ¿Cómo influyen el nivel educativo de la madre y la jefatura del hogar en la prevalencia? | `v149`, `v151` | 🎓 Brecha Socioeducativa |
| 4 | ¿El nivel de riqueza del hogar actúa como factor protector ante la anemia? | `v190` | 💰 Gradiente Económico |
| 5 | ¿En qué mes de vida (0–59) se registra la mayor caída de hemoglobina y el mayor riesgo? | `edad_meses_num`, `hw56` | 📈 Trayectoria · 🧒 Etapa Pediátrica |

---

## Estructura del dashboard

La aplicación organiza el análisis en **seis pestañas**. Un panel lateral aplica filtros globales que recalculan todas las vistas.

| Pestaña | Contenido |
|---|---|
| 📊 **Resumen Epidemiológico** | KPIs generales (niños evaluados, prevalencia, hemoglobina promedio, casos) y análisis por orden de nacimiento |
| 🗺️ **Impacto Geográfico** | Ranking departamental, gráfico lollipop, treemap y semáforo de riesgo territorial |
| 📈 **Trayectoria de Hemoglobina** | Evolución mes a mes de la hemoglobina promedio entre los 0 y 59 meses |
| 🧒 **Anemia por Etapa Pediátrica** | Prevalencia agrupada por lactantes, caminadores y preescolares |
| 💰 **Gradiente Económico** | Prevalencia por quintil de riqueza y distribución de casos |
| 🎓 **Brecha Socioeducativa** | Gradiente educativo, contraste por jefatura del hogar y composición de la carga de casos |

### Filtros globales (barra lateral)

- **Departamentos**, ordenados de mayor a menor prevalencia con indicador de semáforo
- **Nivel de riesgo territorial**: crítico (≥ 40 %), alto (30–39.9 %), moderado (< 30 %)
- **Rango de edad** en meses (0–59)
- **Quintil de riqueza** del hogar

La pestaña 🎓 Brecha Socioeducativa incorpora además un **filtro local** por nivel educativo, aplicable sobre los filtros globales.

---

## Hallazgos principales

> Las cifras corresponden a la muestra ENDES procesada en este proyecto, sin filtros aplicados.

**Orden de nacimiento.** Los primogénitos presentan una prevalencia notablemente mayor que los hijos de segundo o tercer orden.

**Territorio.** Puno, Cusco y Loreto encabezan el ranking departamental de prevalencia. La brecha entre el departamento más y menos afectado supera los 30 puntos porcentuales.

**Nivel socioeducativo.** La prevalencia desciende conforme aumenta el nivel educativo de la madre: **41.6 %** cuando no tiene educación frente a **28.7 %** con educación superior, una brecha de **12.8 puntos porcentuales**. El tipo de jefatura del hogar aporta una diferencia mucho menor, de alrededor de **1.2 puntos**, lo que señala a la educación como el factor dominante de esta relación.

**Concentración de la carga.** El grupo de mayor riesgo no coincide con el de mayor volumen: las madres sin educación registran la tasa más alta pero aportan el **1 %** de los casos, mientras que el nivel secundaria concentra el **53 %** del total. La focalización eficaz requiere combinar ambos criterios.

**Nivel económico.** La prevalencia disminuye de forma monótona conforme sube el quintil de riqueza, con una brecha superior a **21 puntos porcentuales** entre el quintil más pobre y el más rico.

**Trayectoria por edad.** El punto crítico se ubica en el **mes 11**, con una hemoglobina promedio mínima de **10.40 g/dL** y la mayor prevalencia del ciclo (**69.2 %**).

---

## Nota metodológica: el denominador

La variable `hw57` del módulo 1638 codifica el nivel de anemia medido por hemoglobina. Además de los valores 1 a 4 (grave, moderada, leve, sin anemia), incluye el código **9 = no medido** y registros vacíos.

En la muestra procesada hay **2 142 niños sin medición válida** (1 590 con código 9 y 552 con valor vacío). Esto ocurre principalmente porque **ENDES no mide hemoglobina antes de los 6 meses de edad**.

La pestaña 🎓 Brecha Socioeducativa aplica el criterio de **excluir estos registros del denominador**, bajo el principio de que un niño sin medición no puede clasificarse como sano. Por eso reporta:

| Indicador | Valor |
|---|---|
| Niños con medición válida | 16 699 |
| Prevalencia sobre niños medidos | 34.5 % |
| Casos de anemia | 5 757 |

Las demás vistas calculan la prevalencia sobre el total de registros de la muestra filtrada. La diferencia entre ambos criterios es de aproximadamente **3 a 4 puntos porcentuales**.

> **Al comparar cifras entre pestañas conviene verificar cuál denominador se está usando.** La homologación de este criterio en todas las vistas está registrada en [Limitaciones conocidas](#limitaciones-conocidas).

---

## Arquitectura del proyecto

El proyecto separa responsabilidades en cuatro capas:

```
┌─────────────────────────────────────────────────────────────┐
│  CAPA DE DATOS                                              │
│  src/ingesta.py        Descarga desde la API de Datos       │
│                        Abiertos y normaliza a Parquet       │
│  src/procesamiento.py  Integra módulos, deriva variables    │
│                        y valida el esquema con Pandera      │
│  → data/processed/endes_2025_nutricion_m1638_enriquecido.parquet │
├─────────────────────────────────────────────────────────────┤
│  CAPA DE LÓGICA                                             │
│  cargar_y_preparar_datos()   Carga cacheada del Parquet     │
│  sidebar_filtros()           Aplica los filtros globales    │
│  bse_calcular_*()            Agregaciones de la pregunta 3  │
│                              (devuelven DataFrames, sin     │
│                               llamadas a Streamlit/Plotly)  │
├─────────────────────────────────────────────────────────────┤
│  CAPA DE PRESENTACIÓN                                       │
│  tab_*()                     Renderizado de cada pestaña    │
│  bse_grafico_*()             Construcción de figuras        │
│                              (no ejecutan cálculos)         │
├─────────────────────────────────────────────────────────────┤
│  CAPA MAIN                                                  │
│  main()                      Configura la página, monta     │
│                              las pestañas y orquesta        │
└─────────────────────────────────────────────────────────────┘
```

### Estrategia de caché

La carga del dataset y las agregaciones de la pregunta 3 se memorizan con `@st.cache_data`, evitando recalcular en cada interacción con los filtros:

```python
@st.cache_data(show_spinner=False)
def cargar_y_preparar_datos() -> pd.DataFrame: ...

@st.cache_data(ttl=600, show_spinner=False)
def bse_calcular_base(df_filtrado, niveles) -> pd.DataFrame: ...
```

El parámetro `ttl` se expresa **en segundos**: `ttl=600` invalida la caché cada 10 minutos.

---

## Estructura de archivos

Este árbol corresponde **exactamente** al contenido entregado en el repositorio:

```text
Cibertec/
├── .devcontainer/
│   └── devcontainer.json           # Entorno reproducible para GitHub Codespaces
├── .streamlit/
│   └── config.toml                 # Tema visual del dashboard
├── app/
│   └── app.py                      # Aplicación Streamlit (punto de entrada)
├── data/
│   └── processed/
│       └── endes_2025_nutricion_m1638_enriquecido.parquet   # Dataset final
├── notebooks/
│   ├── PreguntasNegocio.ipynb                   # Análisis de las 5 preguntas
│   ├── ingesta_endes_visible2025.ipynb          # Exploración de la ingesta
│   └── endes_2025_nutricion_enriquecido.ipynb   # Exploración del enriquecimiento
├── src/
│   ├── __init__.py
│   ├── ingesta.py                  # Descarga desde la API y conversión a Parquet
│   └── procesamiento.py            # Integración, variables derivadas y validación
├── .gitattributes                  # Normalización de fin de línea
├── .gitignore                      # Exclusiones del repositorio
├── README.md                       # Este documento
└── requirements.txt                # Dependencias del dashboard
```

### Rutas generadas en ejecución (no versionadas)

Estas carpetas se crean al ejecutar el pipeline y están excluidas mediante `.gitignore`:

```text
├── data/datos_normalizados_parquet/   # Módulos ENDES crudos (13 archivos Parquet)
├── logs/                              # Registros de ingesta y validación
└── .venv/                             # Entorno virtual local
```

---

## Instalación y ejecución

### Requisitos previos

- Python 3.13 o superior
- Git
- Conexión a internet únicamente si se desea regenerar los datos desde la fuente

### Pasos

**1. Clonar el repositorio**

```bash
git clone https://github.com/edsalabs/Cibertec.git
cd Cibertec
```

**2. Crear y activar el entorno virtual**

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

```bat
:: Windows CMD
python -m venv .venv
.venv\Scripts\activate
```

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

**3. Instalar dependencias**

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**4. Ejecutar el dashboard**

```bash
streamlit run app/app.py
```

La aplicación queda disponible en `http://localhost:8501`.

> El dataset procesado está versionado en el repositorio, por lo que **el dashboard funciona sin ejecutar el pipeline de ingesta**.

---

## Pipeline de datos y reproducibilidad

Para regenerar los datos desde la fuente pública:

```bash
python src/ingesta.py        # Descarga y normaliza los módulos ENDES a Parquet
python src/procesamiento.py  # Integra 1631 + 1638, deriva variables y valida
```

> `src/procesamiento.py` requiere **Pandera**, que no está incluido en `requirements.txt`. Instalarlo con `pip install pandera` antes de ejecutar el pipeline.

### Qué se versiona y qué no

| Ruta | ¿En Git? | Motivo |
|---|---|---|
| `src/`, `app/`, `notebooks/` | ✅ Sí | Código y análisis |
| `data/processed/*.parquet` | ✅ Sí | Dataset final ligero; permite desplegar sin servicios externos |
| `data/datos_normalizados_parquet/` | ❌ No | Archivos crudos pesados, regenerables con el pipeline |
| `logs/`, `.venv/`, `.env` | ❌ No | Salidas locales, entorno y credenciales |

Streamlit Cloud ejecuta la aplicación leyendo el Parquet directamente del repositorio desplegado.

### Variables derivadas

`src/procesamiento.py` genera, entre otras:

| Variable | Origen | Descripción |
|---|---|---|
| `tiene_anemia` | `hw57` | Indicador binario de presencia de anemia |
| `desc_anemia_nivel` | `hw57` | Grave / Moderada / Leve / Sin anemia / Sin dato |
| `hemoglobina_g_dl` | `hw56` | Hemoglobina en g/dL (`hw56` dividido entre 10) |
| `nivel_educativo_agrupado` | `v149` | Educación de la madre en 4 grupos |
| `desc_logro_educativo` | `v149` | Educación de la madre en 6 niveles |
| `es_jefatura_femenina` | `v151` | Indicador de jefatura del hogar femenina |
| `rango_edad_child` | `edad_meses_num` | Etapa pediátrica |
| `tipo_orden_nacimiento` | `hwidx` | Orden del niño en el hogar |

---

## Tecnologías

| Categoría | Herramientas |
|---|---|
| Lenguaje | Python 3.13 |
| Aplicación web | Streamlit |
| Manipulación de datos | Pandas, NumPy |
| Visualización | Plotly (dashboard) · Matplotlib, Seaborn (notebooks) |
| Formatos y E/S | PyArrow, Fastavro, Requests |
| Validación | Pandera |
| Análisis exploratorio | Jupyter Notebook |

---

## Buenas prácticas aplicadas

**Código**

- Separación de responsabilidades entre ingesta, procesamiento y presentación
- Rutas relativas calculadas dinámicamente, portables entre equipos
- Funciones tipadas y documentadas con docstrings
- Caché explícito sobre las operaciones costosas

**Visualización**

- Cada gráfico incluye título, ejes rotulados con unidad y etiquetas de datos
- Ejes de porcentaje anclados en cero, para no exagerar diferencias visuales
- Orden lógico de categorías ordinales en lugar de alfabético
- Paleta cromática consistente entre vistas
- El *tooltip* reporta siempre el tamaño de muestra junto al porcentaje
- La pregunta 3 incorpora intervalos de confianza al 95 % sobre cada barra

**Repositorio**

- Entorno virtual, cachés, logs y datos pesados excluidos vía `.gitignore`
- Dependencias declaradas en `requirements.txt`
- Dataset final versionado para garantizar un despliegue reproducible

---

## Limitaciones conocidas

Registro de puntos pendientes de homologación:

1. **Criterio de denominador no homogéneo.** La pestaña 🎓 Brecha Socioeducativa excluye del cálculo a los niños sin medición de hemoglobina; las demás vistas los incluyen. Esto produce diferencias de 3 a 4 puntos porcentuales entre pestañas. Ver [Nota metodológica](#nota-metodológica-el-denominador).

2. **Cohorte de 0 a 5 meses.** ENDES no mide hemoglobina en ese rango de edad, por lo que esos registros carecen de resultado. Su tratamiento afecta especialmente a los indicadores agrupados por etapa pediátrica.

3. **Pandera ausente de `requirements.txt`.** El pipeline de procesamiento lo requiere; el dashboard no.

4. **Versiones no fijadas.** `requirements.txt` usa restricciones `>=`, lo que puede producir resoluciones distintas entre el entorno local y Streamlit Cloud. Se recomienda fijar versiones exactas antes de la entrega final.

5. **Variable `tipo_orden_nacimiento`.** Se deriva de `hwidx`, que corresponde al índice del niño en el listado del hogar. Conviene verificar en el diccionario ENDES que su interpretación como orden de nacimiento sea correcta.

---

## Fuente de datos

- **Encuesta Demográfica y de Salud Familiar (ENDES)** — Instituto Nacional de Estadística e Informática (INEI), Perú
- Publicada en la Plataforma Nacional de Datos Abiertos
- Módulos utilizados: **1631** (características del hogar y de la entrevistada) y **1638** (antropometría y hemoglobina infantil)

Los resultados corresponden a la muestra procesada en este proyecto y deben interpretarse como un análisis descriptivo.

---

*Proyecto académico desarrollado para el curso Lenguaje de Ciencia de Datos II — Cibertec.*
