# Observatorio Analitico de Anemia Infantil en el Peru

Proyecto final del curso **Lenguaje de Ciencia de Datos II** - 4to ciclo, Cibertec.

Este proyecto analiza la anemia infantil a partir de datos de la Encuesta Demografica y de Salud Familiar (ENDES). El resultado principal es un dashboard en Streamlit que permite revisar indicadores, comparar departamentos y aplicar filtros para apoyar la focalizacion de intervenciones nutricionales.

## Objetivo

Identificar grupos y territorios con mayor riesgo de anemia infantil para responder preguntas de negocio relacionadas con el orden de nacimiento, la ubicacion geografica, las condiciones socioeducativas, el nivel de riqueza y la edad del menor.

## Preguntas de negocio

1. **Prevalencia por orden de nacimiento:** Como varia la prevalencia de anemia infantil segun el orden de nacimiento del menor?
2. **Impacto geografico:** Que departamentos concentran la mayor prevalencia de anemia y como se distribuye la muestra evaluada en cada uno?
3. **Brecha socioeducativa y vulnerabilidad del hogar:** Como influyen el nivel educativo de la madre y la jefatura del hogar en la prevalencia de anemia infantil?
4. **Gradiente economico:** El nivel de riqueza del hogar (variable `v190`) actua como un factor protector ante la anemia infantil en las regiones del Peru?
5. **Trayectoria clinica por edad:** En que mes de vida del menor, entre 0 y 59 meses, se registra la mayor caida de hemoglobina y el mayor riesgo de anemia?

El detalle del analisis, los graficos y las conclusiones de las cinco preguntas se encuentran en [`notebooks/PreguntasNegocio.ipynb`](notebooks/PreguntasNegocio.ipynb). En la version actual del dashboard se visualizan las preguntas 1 y 2; las preguntas 3, 4 y 5 quedan documentadas en el notebook como soporte del analisis y como siguiente ampliacion de la aplicacion.

## Hallazgos destacados

- Los primogenitos registran una prevalencia de anemia de 31.62%, frente a 21.07% en los segundos o terceros hijos de la muestra analizada.
- Puno, Cusco y Loreto aparecen como los departamentos con mayor prevalencia en el analisis territorial.
- La prevalencia disminuye conforme aumenta el nivel educativo y el quintil de riqueza del hogar.
- El punto mas critico de hemoglobina se identifica a los 11 meses de edad, con 10.40 g/dL en promedio y una prevalencia de anemia de 69.2% en el analisis por edad.

Los resultados deben interpretarse como un analisis descriptivo de la muestra ENDES utilizada en el proyecto; no establecen causalidad por si solos.

## Dashboard

El dashboard presenta:

- Indicadores generales: ninos evaluados, prevalencia, hemoglobina promedio y casos detectados.
- Analisis de anemia por orden de nacimiento.
- Analisis territorial con grafico lollipop y treemap.
- Sidebar con filtros por departamento, nivel de riesgo, rango de edad y quintil de riqueza.

Aplicacion desplegada: https://cibertec-endes2025.streamlit.app/

## Tecnologias utilizadas

- Python 3.13
- Streamlit
- Pandas y NumPy
- Plotly
- PyArrow y Fastavro
- Requests
- Jupyter Notebook para el analisis exploratorio

## Requisitos previos

- Python 3.13 o una version compatible.
- Git instalado para clonar el repositorio.
- Acceso a internet si se desea descargar y procesar nuevamente la fuente ENDES.

## Instalacion y ejecucion

1. Clonar el repositorio:

   ```bash
   git clone https://github.com/edsalabs/Cibertec.git
   cd Cibertec
   ```

2. Crear y activar un entorno virtual:

   **Windows PowerShell**

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **Windows CMD**

   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Instalar las dependencias del dashboard:

   ```bash
   pip install -r requirements.txt
   ```

4. Ejecutar la aplicacion:

   ```bash
   streamlit run app/app.py
   ```

5. Abrir la direccion que muestre Streamlit en el navegador, normalmente `http://localhost:8501`.

## Datos y reproducibilidad

Los archivos Parquet y los logs no se incluyen en GitHub para evitar publicar archivos pesados y resultados locales. Estas rutas estan excluidas en `.gitignore`:

- `data/datos_normalizados_parquet/`
- `data/processed/`
- `logs/`
- `.venv/`
- `.env`

Para generar los datos procesados desde la fuente publica ENDES, ejecutar los siguientes comandos despues de instalar las dependencias:

```bash
python src/ingesta.py
python src/procesamiento.py
```

El primer comando descarga y normaliza los modulos requeridos; el segundo integra, transforma y genera el archivo `data/processed/endes_2025_nutricion_m1638_enriquecido.parquet` usado por el dashboard.

### Arquitectura de datos para el despliegue

El proyecto separa codigo, datos y ejecucion:

- **GitHub** conserva codigo, dependencias, documentacion y el pipeline reproducible.
- **GitHub** incluye el Parquet procesado que consume el dashboard. Su tamano reducido permite que la presentacion sea reproducible sin depender de servicios externos.
- **Streamlit Cloud** ejecuta la aplicacion y lee ese Parquet directamente desde el repositorio desplegado.

Los Parquet crudos, logs y entornos locales permanecen excluidos para mantener el repositorio ligero. La fuente original es ENDES 2025 de Datos Abiertos del Peru y el pipeline incluido permite reconstruir el Parquet.

Para conservar trazabilidad, los cambios del dataset se validan antes de publicarse y se registran con fecha, responsable y descripcion. Para esta presentacion se versiona solo el Parquet final, no los datos crudos.

Para revisar los notebooks se requieren tambien Jupyter, Matplotlib, Seaborn, Squarify y Pandera.

## Estructura del proyecto

```text
Cibertec/
|-- .streamlit/                 # Configuracion visual de Streamlit
|-- app/
|   `-- app.py                  # Punto de entrada del dashboard
|-- data/                       # Datos locales, excluidos del repositorio
|-- notebooks/
|   |-- PreguntasNegocio.ipynb  # Analisis de las cinco preguntas de negocio
|   |-- ingesta_endes_visible2025.ipynb
|   `-- endes_2025_nutricion_enriquecido.ipynb
|-- src/
|   |-- ingesta.py              # Descarga y normalizacion de datos ENDES
|   `-- procesamiento.py        # Integracion y transformacion de datos
|-- .gitignore
`-- requirements.txt
```

## Buenas practicas aplicadas

- El entorno virtual, archivos `.env`, caches, logs y datos pesados estan excluidos del repositorio.
- Las dependencias necesarias para el dashboard se registran en `requirements.txt`.
- El codigo de la aplicacion, la ingesta y el procesamiento se encuentra separado por responsabilidad.
- Se utilizan rutas relativas para facilitar la ejecucion del proyecto en otra computadora.

## Fuente de datos

- Encuesta Demografica y de Salud Familiar (ENDES), Datos Abiertos del Peru.
- Modulos utilizados en el procesamiento: 1631 y 1638.

## Repositorio

https://github.com/edsalabs/Cibertec
