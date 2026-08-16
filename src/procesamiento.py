import sys
import subprocess

# 1. VERIFICACIÓN E INSTALACIÓN AUTOMÁTICA DE PANDERA
try:
    import pandera as pa_main
    import pandera.pandas as pa
except ImportError:
    print("Pandera no detectado. Instalando automáticamente...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pandera", "-q"])
    import pandera as pa_main
    import pandera.pandas as pa
    print("Pandera instalado e importado con éxito.")

# 2. IMPORTACIONES GENERALES DEL PROYECTO
import pandas as pd
import numpy as np
from pandera.pandas import Column, Check, DataFrameSchema
import os
import logging
from datetime import datetime

print(f"Entorno listo. Pandera v{pa_main.__version__} cargado correctamente.")

# -----------------------------------------------------------------------------
# Carga, Limpieza, Diccionarios e Integración 
# =============================================================================
# 0. CONFIGURACIÓN DINÁMICA DE RUTAS
# =============================================================================
# 1. Obtener la ruta absoluta de la carpeta 'src/' (donde se encuentra este archivo .py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Subir un nivel a la raíz del proyecto y apuntar a 'data/datos_normalizados_parquet'
DIR_PARQUET = os.path.abspath(os.path.join(BASE_DIR, "..", "data", "datos_normalizados_parquet"))

# 3. Verificación de existencia del directorio
if not os.path.exists(DIR_PARQUET):
    raise FileNotFoundError(
        f"No se encontró el directorio de datos en: {DIR_PARQUET}\n"
        f"Asegúrate de que la carpeta 'data/datos_normalizados_parquet' exista en la raíz del proyecto."
    )

#=============================================================================
# 1. CARGA Y LIMPIEZA DE ENCABEZADOS
# =============================================================================
ruta_1631 = os.path.join(DIR_PARQUET, "1036-Modulo1631.parquet")
ruta_1638 = os.path.join(DIR_PARQUET, "1036-Modulo1638.parquet")

df_1631 = pd.read_parquet(ruta_1631)
df_1638 = pd.read_parquet(ruta_1638)

# Limpieza estandarizada de columnas
df_1631.columns = df_1631.columns.str.replace('ï»¿', '', regex=False).str.strip().str.lower()
df_1638.columns = df_1638.columns.str.replace('ï»¿', '', regex=False).str.strip().str.lower()

print(f" Filas Módulo 1631 (Hogar/Madre): {len(df_1631):,}")
print(f" Filas Módulo 1638 (Antropometría/HW): {len(df_1638):,}")

# =============================================================================
# 2. DICCIONARIOS DE DATOS
# =============================================================================
dicc_anemia_nivel = {
    1: '1. Grave', 2: '2. Moderada', 3: '3. Leve', 4: '4. Sin Anemia'
}

dicc_logro_educativo = {
    0: '0. Sin educación', 1: '1. Primaria incompleta', 2: '2. Primaria completa',
    3: '3. Secundaria incompleta', 4: '4. Secundaria completa', 5: '5. Superior'
}

dicc_relacion_jefe = {
    1: '1. Jefe del hogar', 2: '2. Esposa/Esposo', 3: '3. Hijo/Hija', 4: '4. Yerno/Nuera',
    5: '5. Nieto/Nieta', 6: '6. Padre/Madre', 7: '7. Suegro/Suegra', 8: '8. Hermano/a',
    9: '9. Conviviente', 10: '10. Otro pariente', 11: '11. Hijo adoptado/de crianza',
    12: '12. Sin parentesco', 15: '15. Empleada doméstica', 98: '98. No sabe'
}

dicc_sexo_jefe = {1: '1. Hombre', 2: '2. Mujer'}

# =============================================================================
# 3. EXTRACCIÓN Y PREPARACIÓN EN MÓDULO 1631
# =============================================================================
df_1631['caseid'] = df_1631['caseid'].astype(str)
df_1638['caseid'] = df_1638['caseid'].astype(str)

# Lista de variables sociodemográficas y de educación a incorporar
cols_deseadas_1631 = ['caseid', 'ubigeo', 'v190', 'v149', 'v150', 'v151', 'v152']
cols_1631 = [col for col in cols_deseadas_1631 if col in df_1631.columns]

# Extraemos solo las columnas necesarias sin duplicados por llave 'caseid'
df_1631_subset = df_1631[cols_1631].drop_duplicates(subset=['caseid'])

# =============================================================================
# 4. CRUCE (INTEGRACIÓN DE TABLAS)
# =============================================================================
df_merged = pd.merge(df_1638, df_1631_subset, on='caseid', how='inner')

# =============================================================================
# 5. MAPEADO Y CREACIÓN DE CAMPOS ENRIQUECIDOS (Mapeos base)
# =============================================================================
# Orden del niño
if 'hwidx' in df_merged.columns:
    df_merged['orden_niño'] = pd.to_numeric(df_merged['hwidx'], errors='coerce')

# Logro Educativo de la Madre/Entrevistada
if 'v149' in df_merged.columns:
    df_merged['v149_num'] = pd.to_numeric(df_merged['v149'], errors='coerce')
    df_merged['desc_logro_educativo'] = df_merged['v149_num'].map(dicc_logro_educativo).fillna('No Especificado')

# Relación con el Jefe del Hogar
if 'v150' in df_merged.columns:
    df_merged['v150_num'] = pd.to_numeric(df_merged['v150'], errors='coerce')
    df_merged['desc_relacion_jefe'] = df_merged['v150_num'].map(dicc_relacion_jefe).fillna('Otro/Desconocido')

# Sexo del Jefe del Hogar
if 'v151' in df_merged.columns:
    df_merged['v151_num'] = pd.to_numeric(df_merged['v151'], errors='coerce')
    df_merged['desc_sexo_jefe'] = df_merged['v151_num'].map(dicc_sexo_jefe).fillna('No Especificado')

# Edad del Jefe del Hogar
if 'v152' in df_merged.columns:
    df_merged['edad_jefe_hogar'] = pd.to_numeric(df_merged['v152'], errors='coerce')

print(f" Cruce exitoso. Registros vinculados: {len(df_merged):,}")
print(f" Nuevas variables integradas: {[c for c in ['desc_logro_educativo', 'desc_relacion_jefe', 'desc_sexo_jefe', 'edad_jefe_hogar'] if c in df_merged.columns]}")

# =============================================================================
# TÉCNICA 1 - VARIABLES DERIVADAS
# =============================================================================
# -----------------------------------------------------------------------------
# a) Presencia y Nivel de Anemia (Módulo 1638 - REC44)
# -----------------------------------------------------------------------------
if 'hw57' in df_merged.columns:
    hw57_num = pd.to_numeric(df_merged['hw57'], errors='coerce')
    df_merged['tiene_anemia'] = np.where(hw57_num.isin([1, 2, 3]), 1, 0)
    df_merged['desc_anemia_nivel'] = hw57_num.map(dicc_anemia_nivel).fillna('Sin dato')
else:
    df_merged['tiene_anemia'] = 0
    df_merged['desc_anemia_nivel'] = 'Sin dato'
    
# -----------------------------------------------------------------------------
# b) Orden de Nacimiento Categorizado (Basado en hwidx del Módulo 1638)
# -----------------------------------------------------------------------------
orden_num = df_merged['orden_niño']
df_merged['tipo_orden_nacimiento'] = np.where(
    orden_num == 1, 
    '1. Primogénito', 
    np.where(orden_num <= 3, '2. Segundo/Tercer Hijo', '3. Cuarto a más')
)

# -----------------------------------------------------------------------------
# c) Nivel Educativo Agrupado de la Madre (v149)
# -----------------------------------------------------------------------------
# Mapeo descriptivo original detallado (0 a 5)
if 'v149_num' in df_merged.columns:
    condiciones_educacion = [
        (df_merged['v149_num'] == 0),
        (df_merged['v149_num'].isin([1, 2])),
        (df_merged['v149_num'].isin([3, 4])),
        (df_merged['v149_num'] == 5)
    ]
    etiquetas_educacion = [
        '1. Sin Educación',
        '2. Primaria (Completa e Incompleta)',
        '3. Secundaria (Completa e Incompleta)',
        '4. Superior'
    ]
    df_merged['nivel_educativo_agrupado'] = np.select(
        condiciones_educacion, etiquetas_educacion, default='No Especificado'
    )

# -----------------------------------------------------------------------------
# d) Jefatura del Hogar Femenina (v151)
# -----------------------------------------------------------------------------
if 'v151_num' in df_merged.columns:
    df_merged['es_jefatura_femenina'] = np.where(df_merged['v151_num'] == 2, 1, 0)

# -----------------------------------------------------------------------------
# e) Rango de Edad del Jefe de Hogar (v152)
# -----------------------------------------------------------------------------
if 'edad_jefe_hogar' in df_merged.columns:
    edad_jefe = df_merged['edad_jefe_hogar']
    conditions = [
        (edad_jefe < 20),
        (edad_jefe >= 20) & (edad_jefe < 30),
        (edad_jefe >= 30) & (edad_jefe < 60),
        (edad_jefe >= 60)
    ]
    choices = [
        '1. Muy Joven (<20 años)',
        '2. Joven (20-29 años)',
        '3. Adulto (30-59 años)',
        '4. Adulto Mayor (60+ años)'
    ]
    df_merged['rango_edad_jefe_hogar'] = np.select(conditions, choices, default='No Especificado')


print(" Aplicación de Técnica 1 (Variables Derivadas) completada exitosamente.")

# =============================================================================
# TÉCNICA 3: TRANSFORMACIÓN POR RANGOS (BINNING / DISCRETIZACIÓN)
# =============================================================================

# -----------------------------------------------------------------------------
# a) CASO 1: Rangos de Edad en Meses del Niño (hw1)
# -----------------------------------------------------------------------------
if 'hw1' in df_merged.columns:
    hw1_num = pd.to_numeric(df_merged['hw1'], errors='coerce')
    df_merged['edad_meses_num'] = hw1_num  # Reutilizable para agregaciones
    rangos_edad = [0, 11, 23, 59]
    etiquetas_edad = [
        '1. 0-11 meses (Lactantes)', 
        '2. 12-23 meses (Caminadores)', 
        '3. 24-59 meses (Preescolares)'
    ]
    df_merged['rango_edad_child'] = pd.cut(
        hw1_num, bins=rangos_edad, labels=etiquetas_edad, include_lowest=True
    )

# -----------------------------------------------------------------------------
# b) CASO 2: Hemoglobina Ajustada por Altitud (hw56: g/dL x 10)
# -----------------------------------------------------------------------------
if 'hw56' in df_merged.columns:
    df_merged['hemoglobina_g_dl'] = pd.to_numeric(df_merged['hw56'], errors='coerce') / 10.0
    rangos_hb = [0.0, 6.9, 9.9, 10.9, 25.0]
    etiquetas_hb = [
        '1. Anemia Severa (<7.0 g/dL)', 
        '2. Anemia Moderada (7.0-9.9 g/dL)', 
        '3. Anemia Leve (10.0-10.9 g/dL)', 
        '4. Sin Anemia (>=11.0 g/dL)'
    ]
    df_merged['rango_hemoglobina'] = pd.cut(
        df_merged['hemoglobina_g_dl'], bins=rangos_hb, labels=etiquetas_hb, include_lowest=True
    )

# -----------------------------------------------------------------------------
# c) CASO 3: Estado Nutricional Talla/Edad - Desnutrición Crónica (hw70)
# -----------------------------------------------------------------------------
if 'hw70' in df_merged.columns:
    z_talla_edad = pd.to_numeric(df_merged['hw70'], errors='coerce') / 100.0
    rangos_z = [-6.0, -3.01, -2.01, 2.0, 6.0]
    etiquetas_z = [
        '1. Desnutrición Crónica Severa (<-3 DE)',
        '2. Desnutrición Crónica Moderada (-3 a -2 DE)',
        '3. Talla Normal (-2 a +2 DE)',
        '4. Talla Alta (>+2 DE)'
    ]
    df_merged['rango_desnutricion_cronica'] = pd.cut(z_talla_edad, bins=rangos_z, labels=etiquetas_z)
    
# -----------------------------------------------------------------------------
# d) CASO 4: Estado Nutricional Peso/Talla - Emaciación / Sobrepeso (hw72)
# -----------------------------------------------------------------------------
if 'hw72' in df_merged.columns:
    z_peso_talla = pd.to_numeric(df_merged['hw72'], errors='coerce') / 100.0
    rangos_pt = [-6.0, -2.01, 2.0, 3.0, 6.0]
    etiquetas_pt = [
        '1. Desnutrición Aguda / Emaciación (<-2 DE)',
        '2. Peso Normal (-2 a +2 DE)',
        '3. Sobrepeso (+2 a +3 DE)',
        '4. Obesidad Infantil (>+3 DE)'
    ]
    df_merged['rango_peso_talla_oms'] = pd.cut(z_peso_talla, bins=rangos_pt, labels=etiquetas_pt) 

print(" Transformación por Rangos (Binning / Discretización) calculadas con éxito.")

# =============================================================================
# TÉCNICA 2 - AGREGACIONES HISTORICAS 
# =============================================================================

# -----------------------------------------------------------------------------
# 1. BASE TERRITORIAL (Código y Nombre de Departamento)
# -----------------------------------------------------------------------------
if 'ubigeo' in df_merged.columns:
    df_merged['codigo_dep'] = df_merged['ubigeo'].astype(str).str.zfill(6).str[:2]
else:
    df_merged['codigo_dep'] = '15'

dicc_departamentos = {
    '01': 'Amazonas', '02': 'Áncash', '03': 'Apurímac', '04': 'Arequipa', '05': 'Ayacucho',
    '06': 'Cajamarca', '07': 'Callao', '08': 'Cusco', '09': 'Huancavelica', '10': 'Huánuco',
    '11': 'Ica', '12': 'Junín', '13': 'La Libertad', '14': 'Lambayeque', '15': 'Lima',
    '16': 'Loreto', '17': 'Madre de Dios', '18': 'Moquegua', '19': 'Pasco', '20': 'Piura',
    '21': 'Puno', '22': 'San Martín', '23': 'Tacna', '24': 'Tumbes', '25': 'Ucayali'
}

df_merged['nombre_departamento'] = df_merged['codigo_dep'].map(dicc_departamentos).fillna('Otros/Desconocido')

# -----------------------------------------------------------------------------
# 2. Agregación Territorial Departamental
# -----------------------------------------------------------------------------
df_merged['total_evaluados_dep'] = df_merged.groupby('codigo_dep')['caseid'].transform('count')
df_merged['total_anemia_dep'] = df_merged.groupby('codigo_dep')['tiene_anemia'].transform('sum')
df_merged['pct_anemia_dep'] = (df_merged['total_anemia_dep'] / df_merged['total_evaluados_dep']) * 100

# -----------------------------------------------------------------------------
# 3. Agregación Socioeducativa por Departamento
# -----------------------------------------------------------------------------
if 'nivel_educativo_agrupado' in df_merged.columns:
    group_dep_edu = df_merged.groupby(['codigo_dep', 'nivel_educativo_agrupado'])
    df_merged['evaluados_dep_edu'] = group_dep_edu['caseid'].transform('count')
    df_merged['anemia_dep_edu'] = group_dep_edu['tiene_anemia'].transform('sum')
    df_merged['pct_anemia_dep_edu'] = (df_merged['anemia_dep_edu'] / df_merged['evaluados_dep_edu']) * 100

# -----------------------------------------------------------------------------
# 4. Agregación por Quintil de Riqueza (v190)
# -----------------------------------------------------------------------------
if 'v190' in df_merged.columns:
    group_riqueza = df_merged.groupby('v190')
    df_merged['pct_anemia_quintil_riqueza'] = group_riqueza['tiene_anemia'].transform('mean') * 100

# -----------------------------------------------------------------------------
# 5. Promedio de Hemoglobina por Edad en Meses
# -----------------------------------------------------------------------------
if 'edad_meses_num' in df_merged.columns and 'hemoglobina_g_dl' in df_merged.columns:
    df_merged['prom_hb_edad_meses'] = df_merged.groupby('edad_meses_num')['hemoglobina_g_dl'].transform('mean')

print(" Agregaciones históricas y contextuales calculadas con éxito.")

# =============================================================================
# 4. NORMALIZACIÓN Y ESTANDARIZACIÓN (ESCALADO DE VARIABLES CONTINUAS)
# =============================================================================

# 1. Asegurar limpieza de nulos/outliers en Hemoglobina (reutilizando columna previa)
if 'hemoglobina_g_dl' in df_merged.columns:
    df_merged['hemoglobina_g_dl'] = np.where(
        df_merged['hemoglobina_g_dl'] <= 25.0, 
        df_merged['hemoglobina_g_dl'], 
        np.nan
    )

# 2. Asegurar tipo numérico en Edad del Niño
if 'hw1' in df_merged.columns:
    df_merged['hw1_num'] = pd.to_numeric(df_merged['hw1'], errors='coerce')

# -----------------------------------------------------------------------------
# A) NORMALIZACIÓN (Min-Max Scaling -> Intervalo [0, 1])
# -----------------------------------------------------------------------------
# Edad del Niño
if 'hw1_num' in df_merged.columns:
    min_edad = df_merged['hw1_num'].min()
    max_edad = df_merged['hw1_num'].max()
    df_merged['edad_norm_minmax'] = (df_merged['hw1_num'] - min_edad) / (max_edad - min_edad)

# Hemoglobina (Solo datos válidos)
if 'hemoglobina_g_dl' in df_merged.columns:
    min_hb = df_merged['hemoglobina_g_dl'].min()
    max_hb = df_merged['hemoglobina_g_dl'].max()
    df_merged['hb_norm_minmax'] = (df_merged['hemoglobina_g_dl'] - min_hb) / (max_hb - min_hb)

# Edad del Jefe de Hogar (NUEVO)
if 'edad_jefe_hogar' in df_merged.columns:
    min_jefe = df_merged['edad_jefe_hogar'].min()
    max_jefe = df_merged['edad_jefe_hogar'].max()
    df_merged['edad_jefe_norm_minmax'] = (df_merged['edad_jefe_hogar'] - min_jefe) / (max_jefe - min_jefe)

# -----------------------------------------------------------------------------
# B) ESTANDARIZACIÓN (Z-Score Scaling -> Media = 0, Std = 1)
# -----------------------------------------------------------------------------
# Edad del Niño
if 'hw1_num' in df_merged.columns:
    mean_edad = df_merged['hw1_num'].mean()
    std_edad = df_merged['hw1_num'].std()
    df_merged['edad_zscore'] = (df_merged['hw1_num'] - mean_edad) / std_edad

# Hemoglobina
if 'hemoglobina_g_dl' in df_merged.columns:
    mean_hb = df_merged['hemoglobina_g_dl'].mean()
    std_hb = df_merged['hemoglobina_g_dl'].std()
    df_merged['hb_zscore'] = (df_merged['hemoglobina_g_dl'] - mean_hb) / std_hb

# Edad del Jefe de Hogar (NUEVO)
if 'edad_jefe_hogar' in df_merged.columns:
    mean_jefe = df_merged['edad_jefe_hogar'].mean()
    std_jefe = df_merged['edad_jefe_hogar'].std()
    df_merged['edad_jefe_zscore'] = (df_merged['edad_jefe_hogar'] - mean_jefe) / std_jefe

print(" Datos normalizados y estandarizados con éxito.")

# =============================================================================
# CONFIGURACIÓN DE LOGS (DATA GOVERNANCE & AUDITORÍA)
# =============================================================================
# Creación dinámica de la carpeta 'logs' en la raíz del proyecto
DIR_LOGS = os.path.abspath(os.path.join(BASE_DIR, "..", "logs"))
os.makedirs(DIR_LOGS, exist_ok=True)
archivo_log = os.path.join(DIR_LOGS, "autocorreccion_calidad.log")

# Configuración centralizada de logging
logging.basicConfig(
    filename=archivo_log,
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8',
    force=True  # Reinicia handlers previos si existieran
)

logger = logging.getLogger("DataGovernanceLogger")
logger.info("Sistema de Logging activado en la fase de Normalización y Gobernanza de Datos.")
print(f" Sistema de Logging activo. Registrando en: {archivo_log}")

# =============================================================================
# GUARDADO Y CARGA DEL DATASET ENRIQUECIDO PARA VALIDACIÓN PANDERA
# =============================================================================

# 1. Definir la ruta dinámica absoluta
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
DIR_PARQUET = os.path.abspath(os.path.join(BASE_DIR, "..", "data", "processed"))
os.makedirs(DIR_PARQUET, exist_ok=True)  # Crea el directorio si aún no existe

path_parquet = os.path.join(DIR_PARQUET, "endes_2025_nutricion_m1638_enriquecido.parquet")

# 2. ALMACENAR EL DATASET ENRIQUECIDO (df_merged contiene todas tus 4 técnicas)
df_merged.to_parquet(path_parquet, index=False, engine='pyarrow', compression='snappy')
print(f" Dataset enriquecido guardado exitosamente en:\n   {path_parquet}")

# 3. Cargar el dataset para validación con Pandera
df_enriquecido = pd.read_parquet(path_parquet)

# 4. Definición del Esquema Pandera Completo e Integrado
esquema_endes = DataFrameSchema(
    columns={
        "id1": Column(pa.Int64, nullable=True, checks=Check.greater_than_or_equal_to(2000)),
        "caseid": Column(pa.String, nullable=False, checks=Check.str_length(min_value=1)),
        "hwidx": Column(pa.Int64, nullable=False, checks=Check.greater_than_or_equal_to(1)),
        "ubigeo": Column(pa.Int64, nullable=True),
        "v190": Column(pa.Int64, nullable=True, checks=Check.in_range(1, 5)), 
        "orden_niño": Column(pa.Int64, nullable=True, checks=Check.greater_than_or_equal_to(1)),

        # Variables de Anemia
        "tiene_anemia": Column(pa.Int64, nullable=False, checks=Check.isin([0, 1])),
        "desc_anemia_nivel": Column(
            pa.String, 
            nullable=True, 
            checks=Check.isin(['1. Grave', '2. Moderada', '3. Leve', '4. Sin Anemia', 'Sin dato'])
        ),
        "tipo_orden_nacimiento": Column(
            pa.String, 
            nullable=True, 
            checks=Check.isin(['1. Primogénito', '2. Segundo/Tercer Hijo', '3. Cuarto a más'])
        ),

        # Variables Territoriales y Agregadas
        "codigo_dep": Column(pa.String, nullable=False, checks=Check.str_length(min_value=2, max_value=2)),
        "nombre_departamento": Column(pa.String, nullable=False),
        "total_evaluados_dep": Column(pa.Int64, nullable=True, checks=Check.greater_than(0)),
        "total_anemia_dep": Column(pa.Int64, nullable=True, checks=Check.greater_than_or_equal_to(0)),
        "pct_anemia_dep": Column(pa.Float64, nullable=True, checks=Check.in_range(min_value=0.0, max_value=100.0)),

        # Variables Clínicas y Discretizaciones OMS
        "hemoglobina_g_dl": Column(
            pa.Float64, 
            nullable=True, 
            checks=Check.in_range(min_value=2.0, max_value=25.0)
        ),
        "rango_edad_child": Column(
            pa.Object, 
            nullable=True, 
            checks=Check.isin([
                '1. 0-11 meses (Lactantes)', 
                '2. 12-23 meses (Caminadores)', 
                '3. 24-59 meses (Preescolares)'
            ])
        ),
        "rango_hemoglobina": Column(
            pa.Object, 
            nullable=True, 
            checks=Check.isin([
                '1. Anemia Severa (<7.0 g/dL)', 
                '2. Anemia Moderada (7.0-9.9 g/dL)', 
                '3. Anemia Leve (10.0-10.9 g/dL)', 
                '4. Sin Anemia (>=11.0 g/dL)'
            ])
        ),
        # Nuevas variables integradas
        "nivel_educativo_agrupado": Column(pa.Object, nullable=True),
        "es_jefatura_femenina": Column(pa.Int64, nullable=True, checks=Check.isin([0, 1]))
    },
    strict=False, 
    coerce=True   
)

print(f"Dataset cargado ({len(df_enriquecido):,} filas) y esquema Pandera configurado.")

# =============================================================================
# EJECUCIÓN, REMEDIACIÓN VECTORIZADA Y AUDITORÍA
# =============================================================================

# Definición de ruta de logs
DIR_LOGS = os.path.abspath(os.path.join(BASE_DIR, "..", "logs")) if '__file__' in globals() else "logs"
archivo_log = os.path.join(DIR_LOGS, "autocorreccion_calidad.log")

try:
    df_validado = esquema_endes.validate(df_enriquecido, lazy=True)
    print("=" * 85)
    print("VALIDACIÓN EXITOSA: El dataset no presentó inconsistencias de calidad.")
    print("=" * 85)
    logger.info("VALIDACION_OK | El dataset paso las reglas de calidad sin inconsistencias.")

except pa.errors.SchemaErrors as err:
    print("=" * 85)
    print("WARNING: INCONSISTENCIAS DETECTADAS POR PANDERA")
    print("=" * 85)
    
    # 1. Reporte visual
    resumen_errores = err.failure_cases[['column', 'check', 'failure_case']].drop_duplicates()
    print(resumen_errores)
    print("-" * 85)
    
    logger.warning(f"INCONSISTENCIA_DETECTADA | Columnas: {resumen_errores['column'].tolist()}")
    
    # 2. Corrección vectorizada
    registros_afectados = (df_enriquecido['hemoglobina_g_dl'] > 25.0).sum()
    
    if registros_afectados > 0:
        df_enriquecido['hemoglobina_g_dl'] = np.where(
            df_enriquecido['hemoglobina_g_dl'] <= 25.0, 
            df_enriquecido['hemoglobina_g_dl'], 
            np.nan
        )
        
        # Guardar cambios
        df_enriquecido.to_parquet(path_parquet, index=False)
        
        mensaje_log = (
            f"REMEDIACION_EXITOSA | Campo: 'hemoglobina_g_dl' | "
            f"Registros corregidos: {registros_afectados:,} | "
            f"Accion: Conversion de codigo '99.9' a 'NaN'"
        )
        logger.info(mensaje_log)
        
        print(" ACCIÓN CORRECTIVA APLICADA Y LOGGEADA:")
        print(f"   ✔ Se corrigieron {registros_afectados:,} registros con código '99.9' en 'hemoglobina_g_dl'.")
        print(f"   ✔ Evento registrado en: '{archivo_log}'")
        print("-" * 85)
        
        # Re-validar
        df_validado = esquema_endes.validate(df_enriquecido, lazy=True)
        print("RE-VALIDACIÓN EXITOSA: Dataset 100% consistente y limpio.")
        print("=" * 85)
        logger.info("REVALIDACION_OK | Dataset 100% limpio y validado con exito tras la remediacion.")

# 3. Mostrar bitácora
print("\n ÚLTIMAS ENTRADAS DE BITÁCORA (logs/autocorreccion_calidad.log):")
print("-" * 85)
if os.path.exists(archivo_log):
    with open(archivo_log, "r", encoding="utf-8") as f:
        for linea in f.readlines()[-4:]:
            print(linea.strip())

# =============================================================================
# OPTIMIZACIÓN DE MEMORIA RAM: DOWNCASTING Y VECTORIZACIÓN
# =============================================================================

df_optimizado = df_enriquecido.copy()
memoria_inicial_mb = df_enriquecido.memory_usage(deep=True).sum() / (1024 ** 2)

# -----------------------------------------------------------------------------
# A) DOWNCASTING NUMÉRICO SEGURO Y CORREGIDO
# -----------------------------------------------------------------------------
# int8: -128 a 127
cols_int8 = ['tiene_anemia', 'v190', 'hwidx', 'orden_niño', 'es_jefatura_femenina']

# int16: -32,768 a 32,767
cols_int16 = ['id1', 'total_evaluados_dep', 'total_anemia_dep', 'evaluados_dep_edu', 'anemia_dep_edu']

# int32: Hasta 2,147,483,647 (UBIGEO corregido aquí para evitar overflow)
cols_int32 = ['ubigeo', 'edad_jefe_hogar']

for col in cols_int8:
    if col in df_optimizado.columns:
        df_optimizado[col] = pd.to_numeric(df_optimizado[col], errors='coerce').astype('Int8')

for col in cols_int16:
    if col in df_optimizado.columns:
        df_optimizado[col] = pd.to_numeric(df_optimizado[col], errors='coerce').astype('Int16')

for col in cols_int32:
    if col in df_optimizado.columns:
        df_optimizado[col] = pd.to_numeric(df_optimizado[col], errors='coerce').astype('Int32')

# Downcasting de Flotantes (float64 -> float32)
cols_float32 = [
    'pct_anemia_dep', 'hemoglobina_g_dl', 'prom_hb_edad_meses', 
    'pct_anemia_dep_edu', 'pct_anemia_quintil_riqueza'
]
for col in cols_float32:
    if col in df_optimizado.columns:
        df_optimizado[col] = pd.to_numeric(df_optimizado[col], errors='coerce').astype('float32')

# -----------------------------------------------------------------------------
# B) CONVERSIÓN DE CADENAS / TEXTO A 'CATEGORY'
# -----------------------------------------------------------------------------
cols_categoricas = [
    'codigo_dep', 'nombre_departamento', 'desc_anemia_nivel', 
    'tipo_orden_nacimiento', 'rango_edad_child', 'rango_hemoglobina',
    'desc_logro_educativo', 'desc_relacion_jefe', 'desc_sexo_jefe',
    'nivel_educativo_agrupado', 'rango_edad_jefe_hogar',
    'rango_desnutricion_cronica', 'rango_peso_talla_oms'
]

for col in cols_categoricas:
    if col in df_optimizado.columns:
        df_optimizado[col] = df_optimizado[col].astype('category')

memoria_final_mb = df_optimizado.memory_usage(deep=True).sum() / (1024 ** 2)

# =============================================================================
# COMPARACIÓN DE MEMORIA Y RENDIMIENTO
# =============================================================================

reduccion_mb = memoria_inicial_mb - memoria_final_mb
porcentaje_ahorro = (reduccion_mb / memoria_inicial_mb) * 100

print("=" * 85)
print(" RESUMEN EJECUTIVO DE OPTIMIZACIÓN DE MEMORIA RAM")
print("=" * 85)
print(f" Memoria consumida ANTES de optimizar: {memoria_inicial_mb:.2f} MB")
print(f" Memoria consumida DESPUÉS de optimizar: {memoria_final_mb:.2f} MB")
print(f" Reducción Total de Memoria:              {reduccion_mb:.2f} MB")
print(f" Eficiencia Lograda:                       {porcentaje_ahorro:.2f}% de Ahorro")
print("=" * 85 + "\n")

# Matriz por columna evaluada
comparativa_cols = []
cols_evaluadas = cols_int8 + cols_int16 + cols_int32 + cols_float32 + cols_categoricas

for col in cols_evaluadas:
    if col in df_enriquecido.columns:
        mem_antes_kb = df_enriquecido[col].memory_usage(deep=True) / 1024
        mem_despues_kb = df_optimizado[col].memory_usage(deep=True) / 1024
        ahorro_col_pct = ((mem_antes_kb - mem_despues_kb) / mem_antes_kb) * 100
        
        comparativa_cols.append({
            'Campo / Columna': col,
            'Tipo Original': str(df_enriquecido[col].dtype),
            'Tipo Optimizado': str(df_optimizado[col].dtype),
            'Memoria Antes (KB)': round(mem_antes_kb, 2),
            'Memoria Después (KB)': round(mem_despues_kb, 2),
            '% Ahorro Memoria': f"{ahorro_col_pct:.1f}%"
        })

df_reporte_memoria = pd.DataFrame(comparativa_cols)

print("DETALLE DE OPTIMIZACIÓN POR CAMPO:")
print(df_reporte_memoria)

# =============================================================================
# ALMACENAMIENTO FINAL DEL DATASET OPTIMIZADO Y LIMPIO
# =============================================================================

# 1. Garantizar ruta dinámica hacia 'data/processed' desde 'src/'
if 'path_parquet' not in locals():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
    DIR_PROCESSED = os.path.abspath(os.path.join(BASE_DIR, "..", "data", "processed"))
    os.makedirs(DIR_PROCESSED, exist_ok=True)
    path_parquet = os.path.join(DIR_PROCESSED, "endes_2025_nutricion_m1638_enriquecido.parquet")

# 2. Guardar el DataFrame optimizado (df_optimizado) sobrescribiendo el Parquet en data/processed/
df_optimizado.to_parquet(
    path_parquet, 
    index=False, 
    engine='pyarrow', 
    compression='snappy'
)

# 3. Recuperar métricas de memoria de forma segura
mem_mb = memoria_final_mb if 'memoria_final_mb' in locals() else df_optimizado.memory_usage(deep=True).sum() / (1024 ** 2)
ahorro_pct = porcentaje_ahorro if 'porcentaje_ahorro' in locals() else 0.0

# 4. Registrar evento en el LOG de Gobernanza
if 'logger' in locals():
    logger.info(
        f"GUARDADO_FINAL_OK | Archivo: '{os.path.basename(path_parquet)}' | "
        f"Ubicacion: 'data/processed/' | "
        f"Filas: {len(df_optimizado):,} | Columnas: {len(df_optimizado.columns)} | "
        f"Tamaño en memoria: {mem_mb:.2f} MB ({ahorro_pct:.1f}% ahorro)"
    )

# 5. Salida en consola de ejecución
print("=" * 85)
print(" PROCESO COMPLETADO Y PIPELINE CONCLUIDO CON ÉXITO")
print("=" * 85)
print(f" Dataset final optimizado guardado en:\n   {path_parquet}")
print(f" Consumo de RAM optimizado a: {mem_mb:.2f} MB")
if 'archivo_log' in locals() and os.path.exists(archivo_log):
    print(f" Eventos de auditoría registrados en: '{archivo_log}'")
print("=" * 85)