import streamlit as st
import pandas as pd

# 1. Configuración de la página
st.set_page_config(
    page_title="Consolidación Histórica - COOPI",
    page_icon="📊",
    layout="wide"
)

# 2. Carga de datos (Ajusta la ruta a tu archivo)
@st.cache_data
def load_data():
    df = pd.read_excel("datos_coopi.xlsx")  # Cambia por la ruta/nombre de tu archivo (.csv o .xlsx)
    return df

try:
    df = load_data()
except Exception as e:
    st.error(f"Error al cargar la base de datos: {e}")
    st.stop()

# 3. Barra Lateral - Filtros de Navegación
st.sidebar.header("Filtros de Navegación")

# Filtro Proyecto
proyectos_opts = sorted(df["Proyecto"].dropna().unique().tolist()) if "Proyecto" in df.columns else []
selected_proyecto = st.sidebar.multiselect("Proyecto:", proyectos_opts, default=proyectos_opts)

# Filtro Año
anios_opts = sorted(df["Año"].dropna().unique().tolist()) if "Año" in df.columns else []
selected_anio = st.sidebar.multiselect("Año:", anios_opts, default=anios_opts)

# Filtro Estado
estados_opts = sorted(df["Estado"].dropna().unique().tolist()) if "Estado" in df.columns else []
selected_estado = st.sidebar.multiselect("Estado:", estados_opts, default=estados_opts)

# Filtro Municipio
municipios_opts = sorted(df["Municipio"].dropna().unique().tolist()) if "Municipio" in df.columns else []
selected_municipio = st.sidebar.multiselect("Municipio:", municipios_opts, default=municipios_opts)

# Filtro Sector de Implementación
col_sector_nombre = next((c for c in df.columns if "sector" in c.lower()), None)
if col_sector_nombre:
    sectores_opts = sorted(df[col_sector_nombre].dropna().unique().tolist())
    selected_sector = st.sidebar.multiselect("Sector de Implementación:", sectores_opts, default=sectores_opts)
else:
    selected_sector = []

# 4. Aplicación de Filtros al DataFrame
df_filtered = df.copy()

if selected_proyecto and "Proyecto" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["Proyecto"].isin(selected_proyecto)]

if selected_anio and "Año" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["Año"].isin(selected_anio)]

if selected_estado and "Estado" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["Estado"].isin(selected_estado)]

if selected_municipio and "Municipio" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["Municipio"].isin(selected_municipio)]

if selected_sector and col_sector_nombre:
    df_filtered = df_filtered[df_filtered[col_sector_nombre].isin(selected_sector)]

# 5. Encabezado Principal
st.title("Consolidación Histórica de Participantes y Atenciones")
st.caption("COOPI - Cooperazione Internazionale | Misión Venezuela")
st.markdown("---")

# 6. Sección de Tarjetas KPI (General de Atenciones y Cobertura)
st.subheader("General de Atenciones y Cobertura")

c1, c2, c3, c4, c5 = st.columns(5)

# Métricas directas
atenciones = df_filtered["Atenciones"].sum() if "Atenciones" in df_filtered.columns else len(df_filtered)
participantes = df_filtered["ID_Participante"].nunique() if "ID_Participante" in df_filtered.columns else 0
estados = df_filtered["Estado"].nunique() if "Estado" in df_filtered.columns else 0
municipios = df_filtered["Municipio"].nunique() if "Municipio" in df_filtered.columns else 0

# Búsqueda segura del sector para la columna 5
cant_sectores = df_filtered[col_sector_nombre].dropna().nunique() if col_sector_nombre else 0

c1.metric("Total Atenciones", f"{atenciones:,}")
c2.metric("Participantes Únicos", f"{participantes:,}")
c3.metric("Estados Atendidos", estados)
c4.metric("Municipios Atendidos", municipios)
c5.metric("Sector", cant_sectores)

st.markdown("---")

# 7. Visualizaciones adicionales / Tablas (Agrega tus gráficos aquí abajo)
