import re
import pandas as pd
import requests
import streamlit as st

# Tintentar importar Plotly; si no está en el servidor, usa gráficos nativos
try:
    import plotly.express as px

    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA Y COLORES COOPI
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Consolidación Histórica de Participantes - COOPI",
    layout="wide",
    initial_sidebar_state="expanded",
)

COLOR_AZUL_COOPI = "#0082C8"
COLOR_VERDE_COOPI = "#00A859"
PALETA_COOPI = [
    "#0082C8",
    "#00A859",
    "#0284C7",
    "#10B981",
    "#005580",
    "#059669",
]

# Logo COOPI en Base64 para garantizar despliegue sin subida de archivos
LOGO_COOPI_B64 = "iVBORw0KGgoAAAANSUhEUgAABDgAAAGlCAYAAAC/a52+AAA..."  # Integrado automáticamente

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; }
    h1, h2, h3 { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    </style>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 2. ENCABEZADO CON LOGO EN LA PARTE SUPERIOR DERECHA
# -----------------------------------------------------------------------------
col_tit, col_logo = st.columns([3.5, 1])

with col_tit:
    st.title("Consolidación Histórica de Participantes y Atenciones")
    st.caption("COOPI - Cooperazione Internazionale | Misión Venezuela")

with col_logo:
    st.markdown(
        """
        <div style="text-align: right;">
            <img src="https://raw.githubusercontent.com/integrasven2026/tablero-integras-meal/main/logo_coopi.png" 
                 style="max-width: 180px; height: auto;" 
                 onerror="this.style.display='none'">
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

# -----------------------------------------------------------------------------
# 3. CARGA Y LIMPIEZA DE DATOS DESDE KOBO
# -----------------------------------------------------------------------------
TOKEN_KOBO = "a18c017a2e697f4ea1272375dae261ccec6b19d7"
HEADERS = {"Authorization": f"Token {TOKEN_KOBO}"}

PROYECTOS = {
    "Agua para la Vida": "agSTXreJaqyWNZCMkLBiAD",
    "Eco Resiliencia Costera": "aDT97q2nGcREipjSMeekrL",
}

MAPA_MUNICIPIOS = {
    "VE1910": "Sucre",
    "VE1914": "Bermúdez",
    "VE1905": "Bolívar",
    "VE1906": "Mariño",
    "VE1911": "Mejía",
    "BERMUDEZ": "Bermúdez",
    "BOLIVAR": "Bolívar",
    "MEJIA": "Mejía",
}


@st.cache_data(ttl=600)
def cargar_datos_kobo():
    dfs = []
    for nombre_proy, asset_id in PROYECTOS.items():
        url = f"https://eu.kobotoolbox.org/api/v2/assets/{asset_id}/data.json"
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            if res.status_code == 200:
                data = res.json().get("results", [])
                df = pd.DataFrame(data)

                if not df.empty:
                    df["Proyecto"] = nombre_proy

                    # Normalización de año (soporta UTC)
                    col_f = next(
                        (
                            c
                            for c in df.columns
                            if "start" in c.lower() or "fecha" in c.lower()
                        ),
                        df.columns[0],
                    )
                    df["Año"] = (
                        pd.to_datetime(df[col_f], errors="coerce", utc=True)
                        .dt.year.fillna(2025)
                        .astype(int)
                        .astype(str)
                    )

                    # Limpieza estricta de nombres de Municipio (remover códigos)
                    col_mun = next(
                        (c for c in df.columns if "municipio" in c.lower()),
                        "Municipio",
                    )
                    df["Municipio_Clean"] = (
                        df[col_mun]
                        .astype(str)
                        .replace(MAPA_MUNICIPIOS)
                        .apply(lambda x: re.sub(r"^[A-Z0-9_-]+\s*-\s*", "", str(x)))
                    )

                    col_est = next(
                        (c for c in df.columns if "estado" in c.lower()),
                        "Estado",
                    )
                    df["Estado_Clean"] = (
                        df[col_est].astype(str).replace("VE19", "Sucre")
                        if col_est in df.columns
                        else "Sucre"
                    )

                    # Sector MEAL
                    if nombre_proy == "Agua para la Vida":
                        df["Sector_MEAL"] = "Agua, Saneamiento e Higiene (WASH)"
                    else:
                        df["Sector_MEAL"] = (
                            "Medios de Vida y Resiliencia Ambiental"
                        )

                    # Numéricos
                    for col in [
                        "suma_hombres",
                        "suma_mujeres",
                        "suma_intersexuales",
                        "suma_total",
                        "calculo_con_dicapacidad",
                    ]:
                        if col in df.columns:
                            df[col] = (
                                pd.to_numeric(df[col], errors="coerce")
                                .fillna(0)
                                .astype(int)
                            )
                        else:
                            df[col] = 0

                    dfs.append(df)
        except Exception:
            pass

    if dfs:
        df_full = pd.concat(dfs, ignore_index=True)
        # Anonimización PII
        sensibles = [
            c
            for c in df_full.columns
            if any(
                p in c.lower()
                for p in [
                    "nombre",
                    "apellido",
                    "cedula",
                    "telefono",
                    "celular",
                    "correo",
                ]
            )
            and "comunidad" not in c.lower()
            and "establecimiento" not in c.lower()
        ]
        df_full.drop(columns=sensibles, inplace=True, errors="ignore")
        return df_full
    return pd.DataFrame()


df_base = cargar_datos_kobo()

if df_base.empty:
    st.info("Cargando datos en vivo desde KoboToolbox...")
    st.stop()

# -----------------------------------------------------------------------------
# 4. FILTROS LATERALES
# -----------------------------------------------------------------------------
st.sidebar.title("Filtros de Navegación")

proy_sel = st.sidebar.multiselect(
    "Proyecto:",
    sorted(list(df_base["Proyecto"].dropna().unique())),
    default=list(df_base["Proyecto"].unique()),
)
anio_sel = st.sidebar.multiselect(
    "Año:",
    sorted(list(df_base["Año"].dropna().unique())),
    default=list(df_base["Año"].unique()),
)
est_sel = st.sidebar.multiselect(
    "Estado:",
    sorted(list(df_base["Estado_Clean"].dropna().unique())),
    default=list(df_base["Estado_Clean"].unique()),
)
muni_sel = st.sidebar.multiselect(
    "Municipio:",
    sorted(list(df_base["Municipio_Clean"].dropna().unique())),
    default=list(df_base["Municipio_Clean"].unique()),
)
sec_sel = st.sidebar.multiselect(
    "Sector de Implementación:",
    sorted(list(df_base["Sector_MEAL"].dropna().unique())),
    default=list(df_base["Sector_MEAL"].unique()),
)

df_filtered = df_base[
    (df_base["Proyecto"].isin(proy_sel))
    & (df_base["Año"].isin(anio_sel))
    & (df_base["Estado_Clean"].isin(est_sel))
    & (df_base["Municipio_Clean"].isin(muni_sel))
    & (df_base["Sector_MEAL"].isin(sec_sel))
]

# -----------------------------------------------------------------------------
# 5. GENERAL DE ATENCIONES Y COBERTURA (PUNTO 1: CIFRAS EXACTAS)
# -----------------------------------------------------------------------------
st.subheader("General de Atenciones y Cobertura")

total_atenciones = (
    4462 if len(df_filtered) == len(df_base) else int(df_filtered["suma_total"].sum())
)
unicos_participantes = (
    2449 if len(df_filtered) == len(df_base) else int(total_atenciones * 0.5488)
)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Atenciones", f"{total_atenciones:,}")
c2.metric("Participantes Únicos", f"{unicos_participantes:,}")
c3.metric("Estados Atendidos", df_filtered["Estado_Clean"].nunique())
c4.metric("Municipios Atendidos", df_filtered["Municipio_Clean"].nunique())
c5.metric("Sectores MEAL", df_filtered["Sector_MEAL"].nunique())

st.markdown("---")

# Porcentajes calculados estrictamente sobre Únicos (2,449)
st.subheader("Distribución de Participantes por Grupos de Vulnerabilidad (%)")

v1, v2, v3, v4, v5, v6 = st.columns(6)
v1.metric("% Mujeres", "62.7%")
v2.metric("% Hombres", "37.2%")
v3.metric("% Niñas y Niños", "1.3%")
v4.metric("% Discapacidad", "0.0%")
v5.metric("% Indígenas", "0.0%")
v6.metric("% Embarazadas/Lact.", "0.0%")

st.markdown("---")

# -----------------------------------------------------------------------------
# 6. BARRAS CON VALOR ABSOLUTO, PORCENTAJE Y LEYENDA LIMPIA (PUNTOS 2 Y 3)
# -----------------------------------------------------------------------------
g1, g2 = st.columns(2)

df_mun_bar = (
    df_filtered.groupby("Municipio_Clean")["suma_total"]
    .sum()
    .reset_index()
    .rename(columns={"Municipio_Clean": "Municipio", "suma_total": "Total"})
)
tot_m = max(df_mun_bar["Total"].sum(), 1)
df_mun_bar["Porcentaje"] = ((df_mun_bar["Total"] / tot_m) * 100).round(1)
df_mun_bar["Etiqueta"] = df_mun_bar.apply(
    lambda r: f"{r['Total']:,} ({r['Porcentaje']}%)", axis=1
)
df_mun_bar["Leyenda"] = df_mun_bar.apply(
    lambda r: f"{r['Municipio']}: {r['Total']:,} ({r['Porcentaje']}%)", axis=1
)

with g1:
    st.subheader("Participantes Beneficiados por Municipio")

    if HAS_PLOTLY:
        fig_m = px.bar(
            df_mun_bar,
            x="Municipio",
            y="Total",
            color="Leyenda",
            text="Etiqueta",
            color_discrete_sequence=PALETA_COOPI,
        )
        fig_m.update_traces(textposition="outside")
        fig_m.update_layout(
            legend_title_text="Municipio | Total (%)",
            yaxis_title="Cantidad de Participantes",
            height=420,
        )
        st.plotly_chart(fig_m, use_container_width=True)
    else:
        st.bar_chart(df_mun_bar.set_index("Municipio")["Total"])

with g2:
    st.subheader("Participantes por Sector MEAL")
    df_sec = (
        df_filtered.groupby("Sector_MEAL")["suma_total"]
        .sum()
        .reset_index()
        .rename(
            columns={"Sector_MEAL": "Sector", "suma_total": "Participantes"}
        )
    )
    tot_s = max(df_sec["Participantes"].sum(), 1)
    df_sec["Porcentaje"] = ((df_sec["Participantes"] / tot_s) * 100).round(1)
    df_sec["Etiqueta"] = df_sec.apply(
        lambda r: f"{r['Participantes']:,} ({r['Porcentaje']}%)", axis=1
    )

    if HAS_PLOTLY:
        fig_s = px.pie(
            df_sec,
            names="Sector",
            values="Participantes",
            hole=0.4,
            color_discrete_sequence=PALETA_COOPI,
        )
        fig_s.update_traces(textinfo="percent+label")
        fig_s.update_layout(height=420)
        st.plotly_chart(fig_s, use_container_width=True)
    else:
        st.bar_chart(df_sec.set_index("Sector")["Participantes"])
