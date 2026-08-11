import streamlit as st
import pandas as pd
import glob
import os

# -----------------------------------------------------------------------------
# 1. ESTO SIEMPRE DEBE SER LA PRIMERA INSTRUCCIÓN DE STREAMLIT
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Tablero Participantes Coopi Venezuela",
    layout="wide"
)

st.title("📊 Tablero de Participantes Coopi Venezuela")

# -----------------------------------------------------------------------------
# 2. CARGA Y CONSOLIDACIÓN AUTOMÁTICA DESDE LA CARPETA 'data'
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def cargar_y_consolidar_datos():
    folder_path = "data"
    
    if not os.path.exists(folder_path):
        return pd.DataFrame()
        
    # Buscar archivos .xlsx, .xls y .csv
    files = glob.glob(os.path.join(folder_path, "*.xlsx")) + \
            glob.glob(os.path.join(folder_path, "*.xls")) + \
            glob.glob(os.path.join(folder_path, "*.csv"))
            
    df_list = []
    for file_path in files:
        try:
            if file_path.endswith(('.xlsx', '.xls')):
                df_temp = pd.read_excel(file_path)
            else:
                df_temp = pd.read_csv(file_path)
            df_list.append(df_temp)
        except Exception as e:
            st.error(f"Error cargando {file_path}: {e}")
            
    if df_list:
        return pd.concat(df_list, ignore_index=True)
    return pd.DataFrame()

# Muestra un mensaje mientras Python procesa los archivos Excel
with st.spinner("Cargando y actualizando las bases de datos históricas..."):
    df_historico = cargar_y_consolidar_datos()

# -----------------------------------------------------------------------------
# 3. VERIFICACIÓN DE DATOS Y RESTO DE TU TABLERO
# -----------------------------------------------------------------------------
if df_historico.empty:
    st.warning("No se encontraron bases de datos en la carpeta 'data/'. Por favor sube los archivos .xlsx o .csv a la carpeta 'data' en GitHub.")
else:
    st.success(f"¡Bases de datos consolidadas con éxito! Total de registros: {len(df_historico)}")
    
    # Aquí abajo continúa el resto de tu código del tablero (filtros, gráficos, tablas)...
    st.dataframe(df_historico.head())
