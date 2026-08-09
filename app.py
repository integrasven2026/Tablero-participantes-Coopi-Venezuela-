import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Tablero Automatizado Kobo",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 Tablero de Monitoreo en Tiempo Real")
st.caption("Conexión directa con KoboToolbox (Servidor Europeo)")

# ---------------------------------------------------------
# CREDENCIALES Y CONFIGURACIÓN DE PROYECTOS
# ---------------------------------------------------------
# Se obtienen las credenciales desde los Secrets de Streamlit
TOKEN_KOBO = st.secrets.get(
    "KOBO_TOKEN", "a18c017a2e697f4ea1272375dae261ccec6b19d7"
)

HEADERS = {"Authorization": f"Token {TOKEN_KOBO}"}

# Agrega aquí tus proyectos con su correspondiente ASSET_ID
PROYECTOS = {
    "Agua para la Vida": "agSTXreJaqyWNZCMkLBiAD",
    "Eco Resiliencia Costera": "aDT97q2nGcREipjSMeekrL",
}


# ---------------------------------------------------------
# FUNCIÓN PARA CONSULTAR LA API DE KOBO
# ---------------------------------------------------------
@st.cache_data(ttl=600)  # Se actualiza en caché cada 10 minutos
def obtener_datos_kobo(asset_id, nombre_proyecto):
    url = f"https://eu.kobotoolbox.org/api/v2/assets/{asset_id}/data.json"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            registros = response.json().get("results", [])
            df = pd.DataFrame(registros)
            if not df.empty:
                df["Proyecto_MEAL"] = nombre_proyecto
            return df
        else:
            st.error(
                f"Error al consultar '{nombre_proyecto}'. Código HTTP: {response.status_code}"
            )
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Excepción al conectar con Kobo: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------
# CARGA Y VISUALIZACIÓN DE DATOS
# ---------------------------------------------------------
df_lista = []
for nombre, asset_id in PROYECTOS.items():
    df_temp = obtener_datos_kobo(asset_id, nombre)
    if not df_temp.empty:
        df_lista.append(df_temp)

if df_lista:
    df_consolidado = pd.concat(df_lista, ignore_index=True)

    # Tarjetas de resumen
    c1, c2 = st.columns(2)
    c1.metric("Total Registros Recaudados", len(df_consolidado))
    c2.metric("Proyectos Activos", len(PROYECTOS))

    st.markdown("---")
    st.subheader("📋 Registro Consolidado")
    st.dataframe(df_consolidado, use_container_width=True)
else:
    st.info("Cargando datos o no se encontraron registros disponibles.")
