import pandas as pd
import requests
import streamlit as st

# 1. Configuración de la página
st.set_page_config(
    page_title="Tablero Integras MEAL - COOPI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. Configuración API KoboToolbox (Servidor Europeo)
TOKEN_KOBO = "a18c017a2e697f4ea1272375dae261ccec6b19d7"
HEADERS = {"Authorization": f"Token {TOKEN_KOBO}"}

PROYECTOS = {
    "Agua para la Vida": "agSTXreJaqyWNZCMkLBiAD",
    "Eco Resiliencia Costera": "aDT97q2nGcREipjSMeekrL",
}


# 3. Función para descargar y normalizar los datos desde Kobo
@st.cache_data(ttl=600)
def cargar_datos_kobo():
    lista_dfs = []

    for nombre_proy, asset_id in PROYECTOS.items():
        url = f"https://eu.kobotoolbox.org/api/v2/assets/{asset_id}/data.json"
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            if res.status_code == 200:
                data = res.json().get("results", [])
                df = pd.DataFrame(data)

                if not df.empty:
                    df["Proyecto"] = nombre_proy

                    # Asegurar columnas numéricas
                    for col in [
                        "suma_hombres",
                        "suma_mujeres",
                        "suma_intersexuales",
                        "suma_total",
                        "calculo_con_dicapacidad",
                    ]:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                        else:
                            df[col] = 0

                    lista_dfs.append(df)
        except Exception as e:
            st.error(f"Error al cargar {nombre_proy}: {e}")

    if lista_dfs:
        return pd.concat(lista_dfs, ignore_index=True)
    return pd.DataFrame()


# Cargar los datos
df_raw = cargar_datos_kobo()

if df_raw.empty:
    st.warning(
        "No se pudieron cargar los datos desde KoboToolbox. Verifique las credenciales."
    )
    st.stop()

# ---------------------------------------------------------
# BARRA LATERAL (FILTROS)
# ---------------------------------------------------------
st.sidebar.header("🔍 Filtros de Consulta")

# Filtro de Proyecto
proyectos_disponibles = ["Todos"] + list(PROYECTOS.keys())
proy_seleccionado = st.sidebar.selectbox("Selecciona Proyecto", proyectos_disponibles)

df_filtrado = df_raw.copy()
if proy_seleccionado != "Todos":
    df_filtrado = df_filtrado[df_filtrado["Proyecto"] == proy_seleccionado]

# Filtro de Estado (si existe la columna)
col_estado = [c for c in df_filtrado.columns if "Estado" in c or "group" in c]
if col_estado:
    estados = ["Todos"] + sorted(
        [str(x) for x in df_filtrado[col_estado[0]].dropna().unique()]
    )
    est_seleccionado = st.sidebar.selectbox("Estado / Región", estados)
    if est_seleccionado != "Todos":
        df_filtrado = df_filtrado[df_filtrado[col_estado[0]] == est_seleccionado]

# ---------------------------------------------------------
# ENCABEZADO Y TÍTULO
# ---------------------------------------------------------
st.title("📊 Tablero Integras MEAL - COOPI Venezuela")
st.markdown(
    "**Monitoreo y Consolidación de Participantes Beneficiados en Tiempo Real**"
)
st.markdown("---")

# ---------------------------------------------------------
# TARJETAS DE MÉTRICAS CLAVE (KPIs)
# ---------------------------------------------------------
total_actividades = len(df_filtrado)
total_participantes = int(df_filtrado["suma_total"].sum())
total_hombres = int(df_filtrado["suma_hombres"].sum())
total_mujeres = int(df_filtrado["suma_mujeres"].sum())
total_discapacidad = int(df_filtrado["calculo_con_dicapacidad"].sum())

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("📌 Total Actividades", f"{total_actividades:,}")
m2.metric("👥 Total Participantes", f"{total_participantes:,}")
m3.metric("👨 Hombres", f"{total_hombres:,}")
m4.metric("👩 Mujeres", f"{total_mujeres:,}")
m5.metric("♿ Con Discapacidad", f"{total_discapacidad:,}")

st.markdown("---")

# ---------------------------------------------------------
# GRÁFICOS Y DESGLOSE
# ---------------------------------------------------------
col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("📊 Participantes por Proyecto")
    df_proy = (
        df_filtrado.groupby("Proyecto")["suma_total"]
        .sum()
        .reset_index()
        .rename(columns={"suma_total": "Participantes"})
    )
    st.bar_chart(df_proy.set_index("Proyecto"))

with col_g2:
    st.subheader("⚖️ Desglose por Género")
    df_genero = pd.DataFrame(
        {
            "Género": ["Hombres", "Mujeres", "Intersexuales"],
            "Cantidad": [
                total_hombres,
                total_mujeres,
                int(df_filtrado["suma_intersexuales"].sum()),
            ],
        }
    )
    st.bar_chart(df_genero.set_index("Género"))

st.markdown("---")

# ---------------------------------------------------------
# TABLA DE REGISTROS CONSOLIDADOS
# ---------------------------------------------------------
st.subheader("📋 Registro de Actividades en Vivo")
st.dataframe(df_filtrado, use_container_width=True)
