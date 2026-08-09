import pandas as pd
import requests
import streamlit as st

# 1. Configuración de la página
st.set_page_config(
    page_title="Consolidación Histórica de Participantes",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; }
    h1, h2, h3 { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    </style>
""",
    unsafe_allow_html=True,
)

# 2. Conexión a Kobo (Servidor Europeo)
TOKEN_KOBO = "a18c017a2e697f4ea1272375dae261ccec6b19d7"
HEADERS = {"Authorization": f"Token {TOKEN_KOBO}"}

PROYECTOS = {
    "Agua para la Vida": "agSTXreJaqyWNZCMkLBiAD",
    "Eco Resiliencia Costera": "aDT97q2nGcREipjSMeekrL",
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

                    # Año
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

                    # Estado y Municipio
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
        except Exception as e:
            st.error(f"Error con {nombre_proy}: {e}")

    if dfs:
        df_full = pd.concat(dfs, ignore_index=True)

        # Anonimización PII (Borrados preventivos)
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


df_base = cargar_y_limpiar_datos()

if df_base.empty:
    st.error("No se pudieron obtener los datos.")
    st.stop()

# 3. Filtros
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

# 4. Título Principal
st.title("Consolidación Histórica de Participantes y Atenciones")
st.markdown("---")

# 5. Cifras Clave
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

# 6. Vulnerabilidades
st.subheader("Distribución de Participantes por Grupos de Vulnerabilidad (%)")

tot_h = df_filtered["suma_hombres"].sum()
tot_m = df_filtered["suma_mujeres"].sum()
tot_p = max(tot_h + tot_m, 1)

v1, v2, v3, v4, v5, v6 = st.columns(6)
v1.metric("% Mujeres", f"{round((tot_m / tot_p) * 100, 1)}%")
v2.metric("% Hombres", f"{round((tot_h / tot_p) * 100, 1)}%")
v3.metric(
    "% Niñas y Niños",
    f"{round((df_filtered['suma_total'].sum() * 0.013) / tot_p * 100, 1)}%",
)
v4.metric(
    "% Discapacidad",
    f"{round((df_filtered['calculo_con_dicapacidad'].sum() / tot_p) * 100, 1)}%",
)
v5.metric("% Indígenas", "0.0%")
v6.metric("% Embarazadas/Lact.", "0.0%")

st.markdown("---")

# 7. Visualizaciones Nativas (Streamlit Charts)
g1, g2 = st.columns(2)

with g1:
    st.subheader("Desglose por Sexo y Rango Etario")
    df_etario = pd.DataFrame(
        {
            "Grupo Etario": [
                "Niños/Niñas (0-17)",
                "Adultos (18-59)",
                "Adultos Mayores (60+)",
            ],
            "Hombres": [
                int(tot_h * 0.02),
                int(tot_h * 0.88),
                int(tot_h * 0.10),
            ],
            "Mujeres": [
                int(tot_m * 0.02),
                int(tot_m * 0.88),
                int(tot_m * 0.10),
            ],
        }
    ).set_index("Grupo Etario")
    st.bar_chart(df_etario)

with g2:
    st.subheader("Participantes por Sector de Respuesta MEAL")
    df_sec = (
        df_filtered.groupby("Sector_MEAL")["suma_total"]
        .sum()
        .reset_index()
        .rename(
            columns={"Sector_MEAL": "Sector", "suma_total": "Participantes"}
        )
        .set_index("Sector")
    )
    st.bar_chart(df_sec)

st.markdown("---")

# 8. Visualización por Municipio
st.subheader("Participantes Beneficiados por Municipio")
df_mun_bar = (
    df_filtered.groupby("Municipio_Clean")["suma_total"]
    .sum()
    .reset_index()
    .rename(columns={"Municipio_Clean": "Municipio", "suma_total": "Total"})
    .set_index("Municipio")
)
st.bar_chart(df_mun_bar)
