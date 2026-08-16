#  Despliegue y Evaluación de Dashboard - ENDES 2025

Este proyecto realiza la ingesta, procesamiento, normalización y visualización de los datos del módulo ENDES 2025 provenientes de la API de Datos Abiertos del Perú.

##  Estructura del Proyecto

- `src/`: Scripts de ingesta de API y procesamiento/enriquecimiento de datos.
- `data/`: Almacenamiento local de archivos Parquet e intermedios.
- `app/`: Aplicación interactiva construida con Streamlit.
- `notebooks/`: Exploración inicial e ingesta de datos en Jupyter Notebook.

   PROYECTO-AVANCE/
│
├── .venv/                          # Entorno virtual (no subir a GitHub)
├── .gitignore                      # Archivos excluidos de Git (.venv, __pycache__, data/)
├── README.md                       # Documentación general y pasos de ejecución
├── requirements.txt                # Librerías necesarias para ejecutar el proyecto
│
├── data/                           # Almacenamiento de datos (no subir a GitHub si son pesados)
│   ├── datos_normalizados_parquet/ # Archivos Parquet post-ingesta (Paso 1)
│   └── processed/                  # Datos finales enriquecidos y optimizados para el Dashboard
│
├── logs/                           # Carpeta dedicada para registros/logs
│   └── ingesta_endes_2025.log
├── notebooks/                      # Exploración inicial e ingesta interactiva
│   └── ingesta_endes_visible2025.ipynb
│
├── src/                            # Código fuente modular (Pipelines de datos)
│   ├── __init__.py
│   ├── ingesta.py                  # Descarga de la API y conversión inicial a Parquet
│   ├── procesamiento.py            # Enriquecimiento, reglas de negocio y validaciones
│   └── utils.py                    # Funciones auxiliares (configuraciones, conectores)
│
└── app/                            # Aplicación para el Despliegue en Streamlit
    ├── app.py                      # Punto de entrada principal (Main de Streamlit)
    └── components/                 # Componentes visuales del Dashboard
        ├── __init__.py
        ├── sidebar.py              # Filtros y navegación
        ├── charts.py               # Gráficos e indicadores (Plotly/Altair)
        └── kpis.py                 # Tarjetas de métricas y resumen
── .streamlit/                 # Configuración de temas/layout de Streamlit
   └── config.toml


##  Instrucciones de Ejecución
1. Crear y activar el entorno virtual:
python -m venv .venv
.\.venv\Scripts\Activate.ps1

2. Instalar dependencias:
pip install -r requirements.txt
python -m pip install --upgrade pip

3. Ejecutar la ingesta y procesamiento:
python src/ingesta.py
python src/procesamiento.py

4. Lanzar el Dashboard en Streamlit:
python -m streamlit run app/app.py



# Crear el archivo .gitignore
New-Item -Path .gitignore -ItemType File

# Crear el archivo README.md
New-Item -Path README.md -ItemType File
