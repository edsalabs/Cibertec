# =============================================================================
# PIPELINE DE INGESTA AUTOMATIZADA - ENDES 2025
# Curso: Lenguaje de Ciencia de Datos II
# Descripción: Pipeline completo para descarga, extracción y normalización
#              de datos de la ENDES 2025 desde Datos Abiertos Perú
# =============================================================================
import os
import io
import json  
import zipfile
import logging
import urllib3
import requests
import pandas as pd
from datetime import datetime

# =============================================================================
# 1. CONFIGURACIÓN DEL SISTEMA DE LOGS Y RUTA
# =============================================================================

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "ingesta_endes_2025.log")
METADATA_FILE = os.path.join(LOG_DIR, "metadata_ingesta.json")  # Archivo de control

# Limpiar handlers previos de logging
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = "https://www.datosabiertos.gob.pe/api/3/action/package_show"
DATASET_ID = "4fad669c-a13d-4398-8d6e-c4e997faa75a"
HEADERS = {"User-Agent": "Mozilla/5.0"}
OUTPUT_DIR = os.path.join("data", "datos_normalizados_parquet")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =============================================================================
# 2. FUNCIONES DE CONTROL DE VERSIÓN DE METADATOS
# =============================================================================
def existen_archivos_parquet():
    """Verifica si el directorio de salida contiene al menos un archivo Parquet."""
    if not os.path.exists(OUTPUT_DIR):
        return False
    archivos = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.parquet')]
    return len(archivos) > 0

def obtener_ultima_fecha_guardada():
    """Lee la fecha de última modificación procesada previamente."""
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("metadata_modified")
        except Exception as e:
            logging.warning(f"No se pudo leer el archivo de metadatos previo: {e}")
    return None

def guardar_metadata_actual(fecha_modificacion, titulo_dataset):
    """Guarda el estado actual del dataset tras una descarga exitosa."""
    metadata = {
        "dataset_id": DATASET_ID,
        "title": titulo_dataset,
        "metadata_modified": fecha_modificacion,
        "last_execution": pd.Timestamp.now().isoformat()
    }
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
    logging.info(f"Metadatos actualizados en: {METADATA_FILE}")

# =============================================================================
# 3. FUNCIONES AUXILIARES DE PROCESAMIENTO
# =============================================================================

def detectar_formato_archivo(nombre_archivo):
    nombre_minuscula = nombre_archivo.lower()
    if nombre_minuscula.endswith('.sav'):
        return 'spss'
    elif nombre_minuscula.endswith('.dta'):
        return 'stata'
    elif nombre_minuscula.endswith('.csv') or nombre_minuscula.endswith('.txt'):
        return 'texto'
    else:
        return 'desconocido'

def leer_archivo_datos(archivo_bytes, formato):
    if formato == 'spss':
        logging.info("   Leyendo archivo SPSS (.sav)...")
        return pd.read_spss(io.BytesIO(archivo_bytes))
    elif formato == 'stata':
        logging.info("   Leyendo archivo Stata (.dta)...")
        return pd.read_stata(io.BytesIO(archivo_bytes))
    elif formato == 'texto':
        logging.info("   Leyendo archivo de texto (.csv/.txt)...")
        try:
            return pd.read_csv(
                io.BytesIO(archivo_bytes),
                sep=None,
                engine='python',
                encoding='latin-1',
                on_bad_lines='skip'
            )
        except:
            return pd.read_csv(
                io.BytesIO(archivo_bytes),
                sep=',',
                encoding='latin-1',
                on_bad_lines='skip'
            )
    else:
        raise ValueError(f"Formato no soportado: {formato}")

def normalizar_dataframe(df, nombre_modulo):
    """
    Aplica normalización estándar a un DataFrame.
    
    Args:
        df (pd.DataFrame): DataFrame a normalizar
        nombre_modulo (str): Nombre del módulo para logging
        
    Returns:
        pd.DataFrame: DataFrame normalizado
    """
    logging.info(f"   Normalizando datos del módulo {nombre_modulo}...")
    
    # 1. Limpiar nombres de columnas
    df.columns = df.columns.str.strip().str.lower()
    logging.info(f"   Columnas encontradas: {len(df.columns)}")
    
    # 2. Eliminar filas totalmente vacías primero (Reduce el tamaño de la memoria temprano)
    df = df.dropna(how='all')
    
    # 3. Convertir categorías a string de un solo paso
    for col in df.select_dtypes(include=['category']).columns:
        df[col] = df[col].astype(str)
        
    # 4. Limpiar espacios en columnas de texto de forma vectorizada
    columnas_texto = df.select_dtypes(include=['object']).columns
    for col in columnas_texto:
        df[col] = df[col].str.strip()
    
    return df

def guardar_parquet(df, nombre_modulo):
    output_filepath = os.path.join(OUTPUT_DIR, f"{nombre_modulo}.parquet")
    df.to_parquet(output_filepath, index=False, engine='pyarrow', compression='snappy')
    return output_filepath

# =============================================================================
# 4. FUNCIÓN PRINCIPAL DEL PIPELINE
# =============================================================================

def ejecutar_pipeline_ingesta(forzar_descarga=False):
    logging.info("=" * 80)
    logging.info("=== INICIANDO PIPELINE DE INGESTA AUTOMATIZADA - ENDES 2025 ===")
    logging.info("=" * 80)
    
    # -------------------------------------------------------------------------
    # FASE 1: Consulta a la API y Verificación de Cambios y Archivos
    # -------------------------------------------------------------------------
    logging.info(f"\n FASE 1: Consultando API de Datos Abiertos")
    try:
        response = requests.get(API_URL, params={"id": DATASET_ID}, headers=HEADERS, verify=False, timeout=30)
        response.raise_for_status()
        datos_api = response.json()
        
        if not datos_api.get("success"):
            logging.error(" La API devolvió success=False.")
            return
            
        result_raw = datos_api.get("result")
        result = result_raw[0] if isinstance(result_raw, list) else result_raw
        
        fecha_modificacion_api = result.get("metadata_modified")
        titulo_dataset = result.get("title")
        recursos = result.get("resources", [])
        
        logging.info(f"    Dataset encontrado: {titulo_dataset}")
        logging.info(f"    Fecha modificación en API: {fecha_modificacion_api}")
        
    except Exception as e:
        logging.error(f" Error al conectar con la API: {e}")
        return

    # Verificación de Metadatos y existencia de archivos Parquet
    fecha_guardada = obtener_ultima_fecha_guardada()
    archivos_presentes = existen_archivos_parquet()

    # Omitir descarga solo si no es forzada, las fechas coinciden Y los archivos existen en disco
    if not forzar_descarga and (fecha_guardada == fecha_modificacion_api) and archivos_presentes:
        logging.info("==================================================================")
        logging.info("🟢 EL DATASET YA ESTÁ ACTUALIZADO Y LOS ARCHIVOS PARQUET EXISTEN.")
        logging.info(f"   Última versión procesada: {fecha_guardada}")
        logging.info(f"   Ubicación: {OUTPUT_DIR}")
        logging.info("   Se omite la descarga de datos para optimizar recursos.")
        logging.info("==================================================================")
        return

    if not archivos_presentes and (fecha_guardada == fecha_modificacion_api):
        logging.info("🟡 Los metadatos están al día, pero NO se encontraron archivos Parquet en el directorio local.")

    logging.info("🟡 Procediendo a la descarga y generación de archivos Parquet...")

    # -------------------------------------------------------------------------
    # FASE 2: Descargar el paquete ZIP
    # -------------------------------------------------------------------------
    url_zip_principal = None
    nombre_zip = None
    
    for recurso in recursos:
        if recurso.get("format", "").lower() == "zip":
            url_zip_principal = recurso.get("url")
            nombre_zip = recurso.get("name")
            break
            
    if not url_zip_principal:
        logging.error(" No se encontró el paquete ZIP en la API.")
        return

    try:
        logging.info(f"\n FASE 3: Descargando paquete de datos...")
        descarga_response = requests.get(url_zip_principal, headers=HEADERS, verify=False, stream=True, timeout=120)
        descarga_response.raise_for_status()
        
        zip_bytes_principal = io.BytesIO(descarga_response.content)
        tamaño_mb = len(descarga_response.content) / (1024 * 1024)
        logging.info(f"    Descarga completada: {tamaño_mb:.2f} MB")
        
    except Exception as e:
        logging.error(f" Error al descargar el archivo: {e}")
        return

    # -------------------------------------------------------------------------
    # FASE 4: Extracción y Procesamiento a Parquet
    # -------------------------------------------------------------------------
    logging.info(f"\n📂 FASE 4: Procesando y extrayendo módulos...")
    try:
        with zipfile.ZipFile(zip_bytes_principal) as zip_madre:
            archivos_zip_internos = [f for f in zip_madre.namelist() if f.endswith('.zip')]
            
            for idx, ruta_zip_interno in enumerate(archivos_zip_internos, 1):
                nombre_modulo = os.path.splitext(os.path.basename(ruta_zip_interno))[0]
                logging.info(f"\n   [{idx}/{len(archivos_zip_internos)}] Procesando: {nombre_modulo}")
                
                try:
                    with zip_madre.open(ruta_zip_interno) as file_interno:
                        zip_bytes_interno = io.BytesIO(file_interno.read())
                        with zipfile.ZipFile(zip_bytes_interno) as zip_hijo:
                            archivos_hijo = zip_hijo.namelist()
                            
                            archivo_datos, formato_detectado = None, None
                            for f in archivos_hijo:
                                formato = detectar_formato_archivo(f)
                                if formato != 'desconocido':
                                    archivo_datos, formato_detectado = f, formato
                                    break
                                    
                            if archivo_datos and formato_detectado:
                                with zip_hijo.open(archivo_datos) as f_datos:
                                    df = leer_archivo_datos(f_datos.read(), formato_detectado)
                                    if df is not None and not df.empty:
                                        df = normalizar_dataframe(df, nombre_modulo)
                                        ruta_parquet = guardar_parquet(df, nombre_modulo)
                                        logging.info(f"       Guardado: {ruta_parquet} ({len(df):,} filas)")
                except Exception as e_mod:
                    logging.error(f"       Error al procesar {nombre_modulo}: {e_mod}")

    except Exception as e:
        logging.error(f" Error al procesar la estructura ZIP: {e}")
        return

   # -------------------------------------------------------------------------
    # FASE 5: Guardar Metadatos y Resumen Final
    # -------------------------------------------------------------------------
    # 1. Actualizar el archivo de control JSON
    guardar_metadata_actual(fecha_modificacion_api, titulo_dataset)
    
    # 2. Imprimir informe detallado en los logs
    logging.info("\n" + "=" * 80)
    logging.info("=== RESUMEN FINAL DEL PIPELINE - ENDES 2025 ===")
    logging.info("=" * 80)
    
    # Listar y auditar archivos Parquet generados
    if os.path.exists(OUTPUT_DIR):
        archivos_generados = os.listdir(OUTPUT_DIR)
        archivos_parquet = [f for f in archivos_generados if f.endswith('.parquet')]
        
        logging.info(f"\nArchivos Parquet en '{OUTPUT_DIR}': {len(archivos_parquet)}")
        
        total_filas = 0
        total_tamaño_mb = 0.0
        
        for archivo in archivos_parquet:
            ruta = os.path.join(OUTPUT_DIR, archivo)
            tamaño_mb = os.path.getsize(ruta) / (1024 * 1024)
            total_tamaño_mb += tamaño_mb
            
            try:
                # Lectura rápida para auditoría de dimensiones
                df_audit = pd.read_parquet(ruta)
                cant_filas = len(df_audit)
                cant_cols = len(df_audit.columns)
                total_filas += cant_filas
                
                logging.info(f"   • {archivo,-30} | {tamaño_mb:6.2f} MB | {cant_filas:10,} filas | {cant_cols:4} columnas")
            except Exception as e_read:
                logging.info(f"   • {archivo,-30} | {tamaño_mb:6.2f} MB | (No se pudo leer dimensiones: {e_read})")
        
        logging.info("-" * 80)
        logging.info(f"TOTAL PROCESADO: {total_tamaño_mb:.2f} MB descargados/almacenados | {total_filas:,} filas totales")
    else:
        logging.warning(f"⚠️ El directorio de salida '{OUTPUT_DIR}' no existe.")

    logging.info("\n" + "=" * 80)
    logging.info("=== PIPELINE DE INGESTA AUTOMATIZADA FINALIZADO CON ÉXITO ===")
    logging.info("=" * 80)

# =============================================================================
# 5. PUNTO DE ENTRADA (EJECUCIÓN)
# =============================================================================

if __name__ == "__main__":
    import sys
    modo_forzado = "--force" in sys.argv
    ejecutar_pipeline_ingesta(forzar_descarga=modo_forzado)