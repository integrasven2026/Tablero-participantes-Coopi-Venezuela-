import streamlit as st
import pandas as pd
import glob
import os

# 1. Diccionario de homologación (mapea variantes de nombres de columna al estándar del tablero)
COLUMN_MAPPING = {
    'cedula': 'Documento_ID',
    'num_documento': 'Documento_ID',
    'id_participante': 'Documento_ID',
    'sexo': 'Genero',
    'genero': 'Genero',
    'edad': 'Edad',
    'proyecto': 'Proyecto',
    'fecha_atencion': 'Fecha',
    'fecha': 'Fecha',
    'estado': 'Estado',
    'municipio': 'Municipio'
}

# 2. Variables mínimas requeridas por el tablero
REQUIRED_COLUMNS = ['Documento_ID', 'Genero', 'Edad', 'Proyecto', 'Fecha', 'Estado', 'Municipio']

@st.cache_data(ttl=3600)
def cargar_y_consolidar_datos(folder_path="data"):
    """
    Escanea la carpeta de datos, lee todos los archivos .xlsx y .csv,
    normaliza las columnas y concatena la información.
    """
    # Buscar archivos .xlsx, .xls y .csv
    files = glob.glob(os.path.join(folder_path, "*.xlsx")) + \
            glob.glob(os.path.join(folder_path, "*.xls")) + \
            glob.glob(os.path.join(folder_path, "*.csv"))
    
    df_list = []
    
    if not files:
        st.warning("No se encontraron archivos de datos en la carpeta '/data'.")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    for file_path in files:
        try:
            # Lectura según el tipo de extensión
            if file_path.endswith(('.xlsx', '.xls')):
                df_temp = pd.read_excel(file_path)
            else:
                df_temp = pd.read_csv(file_path)
            
            # Limpieza básica de nombres de columnas
            df_temp.columns = df_temp.columns.astype(str).str.strip().str.lower()
            
            # Renombrar columnas según el estándar
            df_temp = df_temp.rename(columns=COLUMN_MAPPING)
            
            # Registrar el archivo de origen (útil para auditoría MEAL)
            df_temp['archivo_origen'] = os.path.basename(file_path)
            
            df_list.append(df_temp)
            
        except Exception as e:
            st.error(f"Error al procesar el archivo {file_path}: {e}")
            
    if df_list:
        # Concatenación vertical de todas las bases
        master_df = pd.concat(df_list, ignore_index=True)
        
        # Formatear fechas
        if 'Fecha' in master_df.columns:
            master_df['Fecha'] = pd.to_datetime(master_df['Fecha'], errors='coerce')
            master_df['Año'] = master_df['Fecha'].dt.year
            
        return master_df
    
    return pd.DataFrame()

# Cargar el dataset unificado en el tablero
df_historico = cargar_y_consolidar_datos()
