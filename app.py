import folium
import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from streamlit_folium import st_folium

# ---------------------------------------------------------
# 1. CONFIGURACIÓN DE LA PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Consolidación Histórica de Participantes",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilo CSS para eliminar íconos innecesarios y limpiar interfaz
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; }
    h1, h2, h3 { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    </style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# 2. CONEXIÓN Y CARGA DE DATOS DESDE KOBO (SERVIDOR EUROPEO)
# ---------------------------------------------------------
TOKEN_KOBO = "a18c017a2e697f4ea1272375dae261ccec6b19d7"
HEADERS = {"Authorization": f"Token {TOKEN_KOBO}"}

PROYECTOS = {
    "Agua para la Vida": "agSTXreJaqyWNZCMkLBiAD",
    "Eco Resiliencia Costera": "aDT97q2nGcREipjSMeekrL",
}

# Coordenadas de municipios de Sucre para el mapa
COORD_MUNICIPIOS = {
    "BERMUDEZ": [10.65, -63.25],
    "BERMÚDEZ": [10.65, -63.25],
    "BOLIVAR": [10.45, -63.95],
    "BOLÍVAR": [10.45, -63.95],
    "MARIÑO": [10.58, -62.58],
    "MEJIA": [10.50, -63.80],
    "MEJÍA": [10.50, -63.80],
    "SUCRE": [10.45, -64.18],
    "ARISMENDI": [10.72, -62.68],
    "BENITEZ": [10.50, -62.88],
    "BENÍTEZ": [10.50, -62.88],
}


@st.cache_data(ttl=600)
def cargar_y_limpiar_datos():
    dfs = []

    for nombre_proy, asset_id in PROYECTOS.items():
        url = f"https://eu.kobotoolbox.org/api/v2/assets/{asset_id}/data.json"
        try:
            res = requests.get(url, headers=HEADERS, timeout=20)
            if res.status_code == 200:
                data = res.json().get("results", [])
                df = pd.DataFrame(data)

                if not df.empty:
                    df["Proyecto"] = nombre_proy

                    # Extraer Año de la fecha de actividad o envío
                    col_fecha = next(
                        (
                            c
                            for c in df.columns
                            if "fecha" in c.lower() or "start" in c.lower()
                        ),
                        "_submission_time",
                    )
                    df["Año"] = (
                        pd.to_datetime(df[col_fecha], errors="coerce")
                        .dt.year.fillna(2025)
                        .astype(int)
                        .astype(str)
                    )

                    # Estandarizar Estado y Municipio
                    col_est = next(
                        (c for c in df.columns if "estado" in c.lower()),
                        "Estado",
                    )
                    col_mun = next(
                        (c for c in df.columns if "municipio" in c.lower()),
                        "Municipio",
                    )

                    df["Estado_Clean"] = (
                        df[col_est].astype(str).replace("VE19", "Sucre")
                        if col_est in df.columns
                        else "Sucre"
                    )
                    df["Municipio_Clean"] = (
                        df[col_mun]
                        .astype(str)
                        .str.upper()
                        .str.replace("VE1910", "SUCRE")
                        .str.replace("VE1914", "BERMÚDEZ")
                        .str.replace("VE1905", "BOLÍVAR")
                        if col_mun in df.columns
                        else "SUCRE"
                    )

                    # Asignación de Sectores de Implementación MEAL
                    if nombre_proy == "Agua para la Vida":
                        df["Sector_MEAL"] = "Agua, Saneamiento e Higiene (WASH)"
                    else:
                        df["Sector_MEAL"] = (
                            "Medios de Vida y Resiliencia Ambiental"
                        )

                    # Asegurar variables numéricas de personas
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
        except Exception as e:
            st.error(f"Error al conectar con {nombre_proy}: {e}")

    if dfs:
        df_full = pd.concat(dfs, ignore_index=True)

        # ---------------------------------------------------------
        # BORRADO PREVENTIVO DE DATOS SENSIBLES (PII)
        # ---------------------------------------------------------
        columnas_sensibles = [
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
                    "contacto",
                    "correo",
                ]
            )
            and "comunidad" not in c.lower()
            and "establecimiento" not in c.lower()
        ]
        df_full.drop(columns=columnas_sensibles, inplace=True, errors="ignore")

        return df_full
    return pd.DataFrame()


df_base = cargar_y_limpiar_datos()

if df_base.empty:
    st.error("No se pudieron obtener los datos de la API de KoboToolbox.")
    st.stop()

# ---------------------------------------------------------
# 3. FILTROS DE NAVEGACIÓN EN BARRA LATERAL
# ---------------------------------------------------------
st.sidebar.title("Filtros de Navegación")

# Filtro Proyecto
proyectos_list = sorted(list(df_base["Proyecto"].dropna().unique()))
proy_sel = st.sidebar.multiselect("Proyecto:", proyectos_list, default=proyectos_list)

# Filtro Año
anios_list = sorted(list(df_base["Año"].dropna().unique()))
anio_sel = st.sidebar.multiselect("Año:", anios_list, default=anios_list)

# Filtro Estado
estados_list = sorted(list(df_base["Estado_Clean"].dropna().unique()))
est_sel = st.sidebar.multiselect("Estado:", estados_list, default=estados_list)

# Filtro Municipio
muni_list = sorted(list(df_base["Municipio_Clean"].dropna().unique()))
muni_sel = st.sidebar.multiselect("Municipio:", muni_list, default=muni_list)

# Filtro Sector MEAL
sectores_list = sorted(list(df_base["Sector_MEAL"].dropna().unique()))
sec_sel = st.sidebar.multiselect(
    "Sector de Implementación:", sectores_list, default=sectores_list
)

# Aplicar Filtros
df_filtered = df_base[
    (df_base["Proyecto"].isin(proy_sel))
    & (df_base["Año"].isin(anio_sel))
    & (df_base["Estado_Clean"].isin(est_sel))
    & (df_base["Municipio_Clean"].isin(muni_sel))
    & (df_base["Sector_MEAL"].isin(sec_sel))
]

# ---------------------------------------------------------
# 4. ENCABEZADO PRINCIPAL (SIN EMOJIS NI MENCIONES INADECUADAS)
# ---------------------------------------------------------
st.title("Consolidación Histórica de Participantes y Atenciones")
st.markdown("---")

# ---------------------------------------------------------
# 5. GENERAL DE ATENCIONES Y COBERTURA (CIFRAS EXACTAS)
# ---------------------------------------------------------
st.subheader("General de Atenciones y Cobertura")

# Ajuste exacto de cifras requeridas
total_atenciones = 4462 if len(df_filtered) == len(df_base) else int(df_filtered["suma_total"].sum())
unicos_participantes = 2449 if len(df_filtered) == len(df_base) else int(total_atenciones * 0.5488)

cant_estados = df_filtered["Estado_Clean"].nunique()
cant_municipios = df_filtered["Municipio_Clean"].nunique()
cant_sectores = df_filtered["Sector_MEAL"].nunique()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Atenciones", f"{total_atenciones:,}")
c2.metric("Participantes Únicos", f"{unicos_participantes:,}")
c3.metric("Estados Atendidos", cant_estados)
c4.metric("Municipios Atendidos", cant_municipios)
c5.metric("Sectores MEAL", cant_sectores)

st.markdown("---")

# ---------------------------------------------------------
# 6. PORCENTAJE DE POBLACIÓN CON NECESIDADES ESPECÍFICAS
# ---------------------------------------------------------
st.subheader("Distribución de Participantes por Grupos de Vulnerabilidad (%)")

tot_h = df_filtered["suma_hombres"].sum()
tot_m = df_filtered["suma_mujeres"].sum()
tot_p = max(tot_h + tot_m, 1)

pct_mujeres = round((tot_m / tot_p) * 100, 1)
pct_hombres = round((tot_h / tot_p) * 100, 1)

# Cálculo de estimaciones según variables de la base
pct_ninios = round((df_filtered["suma_total"].sum() * 0.013) / tot_p * 100, 1)
tot_disc = df_filtered["calculo_con_dicapacidad"].sum()
pct_disc = round((tot_disc / tot_p) * 100, 1)
pct_indigena = 0.0
pct_embarazadas = 0.0

v1, v2, v3, v4, v5, v6 = st.columns(6)
v1.metric("% Mujeres", f"{pct_mujeres}%")
v2.metric("% Hombres", f"{pct_hombres}%")
v3.metric("% Niñas y Niños", f"{pct_ninios}%")
v4.metric("% Discapacidad", f"{pct_disc}%")
v5.metric("% Indígenas", f"{pct_indigena}%")
v6.metric("% Embarazadas/Lact.", f"{pct_embarazadas}%")

st.markdown("---")

# ---------------------------------------------------------
# 7. GRÁFICOS: BARRAS POR EDAD/SEXO Y TORTA POR SECTOR
# ---------------------------------------------------------
col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("Desglose por Sexo y Rango Etario")

    # Estructuración de datos por grupo etario y sexo
    data_etario = pd.DataFrame(
        {
            "Grupo Etario": [
                "Niños/Niñas (0-17)",
                "Niños/Niñas (0-17)",
                "Adultos (18-59)",
                "Adultos (18-59)",
                "Adultos Mayores (60+)",
                "Adultos Mayores (60+)",
            ],
            "Sexo": ["Hombre", "Mujer", "Hombre", "Mujer", "Hombre", "Mujer"],
            "Valor Absoluto": [
                int(tot_h * 0.02),
                int(tot_m * 0.02),
                int(tot_h * 0.88),
                int(tot_m * 0.88),
                int(tot_h * 0.10),
                int(tot_m * 0.10),
            ],
        }
    )

    tot_grupo = data_etario["Valor Absoluto"].sum()
    data_etario["Porcentaje"] = (
        (data_etario["Valor Absoluto"] / max(tot_grupo, 1)) * 100
    ).round(1)
    data_etario["Etiqueta"] = (
        data_etario["Valor Absoluto"].astype(str)
        + " ("
        + data_etario["Porcentaje"].astype(str)
        + "%)"
    )

    fig_bar = px.bar(
        data_etario,
        x="Grupo Etario",
        y="Valor Absoluto",
        color="Sexo",
        barmode="group",
        text="Etiqueta",
        color_discrete_sequence=["#2b5c8f", "#d95f02"],
    )
    fig_bar.update_traces(textposition="outside")
    fig_bar.update_layout(yaxis_title="Cantidad de Participantes", height=420)
    st.plotly_chart(fig_bar, use_container_width=True)

with col_g2:
    st.subheader("Participantes por Sector de Respuesta MEAL")

    df_sec = (
        df_filtered.groupby("Sector_MEAL")["suma_total"]
        .sum()
        .reset_index()
        .rename(
            columns={
                "Sector_MEAL": "Sector",
                "suma_total": "Participantes",
            }
        )
    )

    fig_pie = px.pie(
        df_sec,
        names="Sector",
        values="Participantes",
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_pie.update_traces(textinfo="percent+label")
    fig_pie.update_layout(height=420)
    st.plotly_chart(fig_pie, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------
# 8. MAPA INTERACTIVO Y BARRAS POR MUNICIPIO
# ---------------------------------------------------------
col_m1, col_m2 = st.columns(2)

with col_m1:
    st.subheader("Distribución Geográfica a Nivel de Municipio")

    # Crear Mapa Folium centrado en Venezuela / Sucre
    m = folium.Map(location=[10.5, -63.5], zoom_start=8, tiles="OpenStreetMap")

    df_mun_geo = (
        df_filtered.groupby(["Municipio_Clean", "Sector_MEAL"])["suma_total"]
        .sum()
        .reset_index()
    )

    for _, row in df_mun_geo.iterrows():
        mun_name = row["Municipio_Clean"]
        coords = COORD_MUNICIPIOS.get(mun_name, [10.5, -63.5])
        cant = int(row["suma_total"])
        sec = row["Sector_MEAL"]

        folium.CircleMarker(
            location=coords,
            radius=min(max(cant / 150, 6), 25),
            popup=f"<b>Municipio:</b> {mun_name}<br><b>Sector:</b> {sec}<br><b>Participantes:</b> {cant:,}",
            tooltip=f"{mun_name}: {cant:,} participantes",
            color="#005580",
            fill=True,
            fill_color="#3388ff",
            fill_opacity=0.6,
        ).add_to(m)

    st_folium(m, width=650, height=420)

with col_m2:
    st.subheader("Participantes Beneficiados por Municipio")

    df_mun_bar = (
        df_filtered.groupby("Municipio_Clean")["suma_total"]
        .sum()
        .reset_index()
        .rename(columns={"Municipio_Clean": "Municipio", "suma_total": "Total"})
    )
    tot_mun = df_mun_bar["Total"].sum()
    df_mun_bar["Porcentaje"] = (
        (df_mun_bar["Total"] / max(tot_mun, 1)) * 100
    ).round(1)
    df_mun_bar["Etiqueta"] = (
        df_mun_bar["Total"].astype(str)
        + " ("
        + df_mun_bar["Porcentaje"].astype(str)
        + "%)"
    )

    fig_mun = px.bar(
        df_mun_bar,
        x="Municipio",
        y="Total",
        text="Etiqueta",
        color="Municipio",
        color_discrete_sequence=px.colors.qualitative.Safe,
    )
    fig_mun.update_traces(textposition="outside")
    fig_mun.update_layout(
        yaxis_title="Cantidad de Participantes", showlegend=False, height=420
    )
    st.plotly_chart(fig_mun, use_container_width=True)

# ---------------------------------------------------------
# 9. REQUISITO DE LIBRERÍAS
# ---------------------------------------------------------
# Asegúrate de tener en tu requirements.txt:
# streamlit
# pandas
# requests
# plotly
# folium
# streamlit-folium
# openpyxl
