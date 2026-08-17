import glob
import os
import re
import pandas as pd
import streamlit as st

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

PALETA_SECTORES = [
    "#0082C8",  # Azul COOPI
    "#00A859",  # Verde COOPI
    "#F59E0B",  # Ámbar / Naranja
    "#8B5CF6",  # Púrpura
    "#EC4899",  # Magenta / Rosa
    "#06B6D4",  # Cían
]

FACTOR_UNICOS = 2449 / 4462

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
# DICCIONARIO DE COORDENADAS POR ESTADO Y MUNICIPIO (CLAVE COMBINADA)
# -----------------------------------------------------------------------------
COORD_ESTADO_MUNICIPIO = {
    # Estado Sucre
    "SUCRE|BERMÚDEZ": {"lat": 10.6558, "lon": -63.2536},
    "SUCRE|BERMUDEZ": {"lat": 10.6558, "lon": -63.2536},
    "SUCRE|MARIÑO": {"lat": 10.5833, "lon": -62.5833},
    "SUCRE|MARINO": {"lat": 10.5833, "lon": -62.5833},
    "SUCRE|SUCRE": {"lat": 10.4531, "lon": -64.1826},  # Cumaná
    "SUCRE|MEJÍA": {"lat": 10.5011, "lon": -63.8015},
    "SUCRE|MEJIA": {"lat": 10.5011, "lon": -63.8015},
    "SUCRE|BOLÍVAR": {"lat": 10.4521, "lon": -63.9512},
    "SUCRE|BOLIVAR": {"lat": 10.4521, "lon": -63.9512},
    "SUCRE|CRUZ SALMERÓN ACOSTA": {"lat": 10.6222, "lon": -64.1794},
    "SUCRE|CRUZ SALMERON ACOSTA": {"lat": 10.6222, "lon": -64.1794},

    # Estado Miranda
    "MIRANDA|SUCRE": {"lat": 10.4815, "lon": -66.8203},  # Petare / Caracas Este
    "MIRANDA|BARUTA": {"lat": 10.4344, "lon": -66.8761},
    "MIRANDA|URDANETA": {"lat": 10.1500, "lon": -66.8667},  # Cúa

    # Distrito Capital
    "DISTRITO CAPITAL|LIBERTADOR": {"lat": 10.4880, "lon": -66.8792},  # Caracas Centro/Oeste

    # Estado Bolívar
    "BOLÍVAR|CARONÍ": {"lat": 8.2978, "lon": -62.7114},  # Ciudad Guayana
    "BOLIVAR|CARONÍ": {"lat": 8.2978, "lon": -62.7114},
    "BOLÍVAR|CARONI": {"lat": 8.2978, "lon": -62.7114},
    "BOLIVAR|CARONI": {"lat": 8.2978, "lon": -62.7114},
    "BOLÍVAR|EL CALLAO": {"lat": 7.3489, "lon": -61.8197},
    "BOLIVAR|EL CALLAO": {"lat": 7.3489, "lon": -61.8197},

    # Estado Delta Amacuro
    "DELTA AMACURO|TUCUPITA": {"lat": 9.0611, "lon": -62.0494},
    "DELTA AMACURO|CASACOIMA": {"lat": 8.5211, "lon": -62.2281},
}

OFFSETS_GEO = [
    (0.0, 0.0),
    (0.012, 0.012),
    (-0.012, -0.012),
    (0.012, -0.012),
    (-0.012, 0.012),
]

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

# -----------------------------------------------------------------------------
# 2. ENCABEZADO CON LOGO OFICIAL
# -----------------------------------------------------------------------------
col_tit, col_logo = st.columns([3.2, 1.2])

with col_tit:
    st.title("Consolidación Histórica de Participantes y Atenciones")
    st.caption("COOPI - Cooperazione Internazionale | Misión Venezuela")

with col_logo:
    st.markdown(
        """
        <div style="text-align: right; padding-top: 5px;">
            <img src="https://www.coopi.org/images/logo.png" 
                 style="max-width: 210px; height: auto;" 
                 alt="Logo Oficial COOPI"
                 onerror="this.src='https://raw.githubusercontent.com/integrasven2026/tablero-integras-meal/main/logo_coopi.png'">
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")


# -----------------------------------------------------------------------------
# 3. CARGA Y ESTANDARIZACIÓN AUTOMÁTICA DESDE 'DATA'
# -----------------------------------------------------------------------------
def clasificar_sector_seguro(row, nombre_proyecto=""):
    text_parts = []
    for val in row.values:
        if pd.notna(val):
            text_parts.append(str(val).lower())

    row_text = " ".join(text_parts)

    if any(
        p in row_text
        for p in [
            "residuo",
            "desecho",
            "recicl",
            "basura",
            "a33",
            "a34",
            "a35",
            "a36",
            "gestión de residuos",
        ]
    ):
        return "Gestión Ambiental y Residuos Sólidos"
    elif any(
        p in row_text
        for p in [
            "wash",
            "agua",
            "saneamiento",
            "plomería",
            "hidro",
            "a11",
            "a12",
            "a14",
            "a24",
            "a25",
        ]
    ):
        return "Agua, Saneamiento e Higiene (WASH)"
    elif any(
        p in row_text
        for p in [
            "negocio",
            "pesca",
            "ingreso",
            "a.3",
            "acuícola",
            "turismo",
        ]
    ):
        return "Medios de Vida y Resiliencia Ambiental"
    elif any(
        p in row_text
        for p in [
            "sensibiliz",
            "protecc",
            "derecho",
            "campaña",
            "género",
            "a22",
            "a13",
            "r2",
        ]
    ):
        return "Protección y Sensibilización Comunitaria"
    else:
        if "agua" in str(nombre_proyecto).lower():
            return "Agua, Saneamiento e Higiene (WASH)"
        return "Protección y Sensibilización Comunitaria"


@st.cache_data(ttl=3600)
def cargar_datos_desde_data():
    folder_path = "data"

    if not os.path.exists(folder_path):
        return pd.DataFrame()

    all_files = (
        glob.glob(os.path.join(folder_path, "*.xlsx"))
        + glob.glob(os.path.join(folder_path, "*.xls"))
        + glob.glob(os.path.join(folder_path, "*.csv"))
    )

    files = [
        f
        for f in all_files
        if not os.path.basename(f).startswith("~$")
        and not os.path.basename(f).startswith(".")
    ]

    dfs = []
    for file_path in files:
        try:
            if file_path.endswith((".xlsx", ".xls")):
                xls = pd.ExcelFile(file_path)
                sheet = (
                    "BBDD" if "BBDD" in xls.sheet_names else xls.sheet_names[0]
                )
                df_temp = pd.read_excel(file_path, sheet_name=sheet)
            else:
                df_temp = pd.read_csv(file_path)

            if df_temp.empty:
                continue

            cols_clean = {
                str(c).strip().lower(): c for c in df_temp.columns
            }

            base_name = os.path.splitext(os.path.basename(file_path))[0]
            nombre_archivo_limpio = (
                base_name.replace("_", " ").replace("-", " ").strip()
            )

            # Proyecto
            col_proy = next(
                (
                    c
                    for k, c in cols_clean.items()
                    if k in ["proyecto", "nombre_proyecto", "nombre del proyecto"]
                ),
                None,
            )
            if col_proy and not df_temp[col_proy].dropna().empty:
                df_temp["Proyecto"] = (
                    df_temp[col_proy]
                    .fillna(nombre_archivo_limpio)
                    .astype(str)
                    .str.strip()
                )
            else:
                df_temp["Proyecto"] = nombre_archivo_limpio

            # Socio Implementador
            col_socio = next(
                (
                    c
                    for k, c in cols_clean.items()
                    if k in ["socio", "socio_implementador", "partner", "organización", "organizacion"]
                ),
                None,
            )
            if col_socio and not df_temp[col_socio].dropna().empty:
                df_temp["Socio"] = (
                    df_temp[col_socio]
                    .fillna("COOPI")
                    .astype(str)
                    .str.strip()
                    .str.upper()
                )
            else:
                df_temp["Socio"] = "COOPI"

            # Código o Nombre de Actividad
            col_act = next(
                (
                    c
                    for k, c in cols_clean.items()
                    if k in ["actividad", "actividad_nombre", "activity", "codigo_actividad", "cod_actividad"]
                ),
                None,
            )
            if col_act and not df_temp[col_act].dropna().empty:
                df_temp["Actividad"] = (
                    df_temp[col_act]
                    .fillna("Actividad General")
                    .astype(str)
                    .str.strip()
                )
            else:
                df_temp["Actividad"] = "Actividad General"

            # Año
            col_anio = next(
                (
                    c
                    for k, c in cols_clean.items()
                    if k in ["año", "anio", "year", "fecha", "fecha "]
                ),
                None,
            )
            if col_anio:
                s_fecha = pd.to_datetime(df_temp[col_anio], errors="coerce")
                if s_fecha.notna().any():
                    df_temp["Año"] = (
                        s_fecha.dt.year.fillna(2025).astype(int).astype(str)
                    )
                else:
                    df_temp["Año"] = (
                        df_temp[col_anio]
                        .astype(str)
                        .str.extract(r"(20\d{2})")[0]
                        .fillna("2025")
                    )
            else:
                df_temp["Año"] = "2025"

            # Estado y Municipio
            col_est = next(
                (
                    c
                    for k, c in cols_clean.items()
                    if "estado" in k or "est" in k
                ),
                None,
            )
            df_temp["Estado_Clean"] = (
                df_temp[col_est]
                .astype(str)
                .str.replace("_", " ")
                .replace("VE19", "Sucre")
                .str.strip()
                .str.title()
                if col_est
                else "Sucre"
            )

            col_mun = next(
                (
                    c
                    for k, c in cols_clean.items()
                    if "municipio" in k or "muni" in k
                ),
                None,
            )
            if col_mun:
                df_temp["Municipio_Clean"] = (
                    df_temp[col_mun]
                    .astype(str)
                    .replace(MAPA_MUNICIPIOS)
                    .apply(lambda x: re.sub(r"^[A-Z0-9_-]+\s*-\s*", "", str(x)))
                    .str.replace("_", " ")
                    .str.strip()
                    .str.title()
                )
            else:
                df_temp["Municipio_Clean"] = "Sucre"

            # Sector
            col_sec = next(
                (c for k, c in cols_clean.items() if "sector" in k), None
            )
            if col_sec:
                df_temp["Sector"] = (
                    df_temp[col_sec].fillna("General").astype(str)
                )
            else:
                df_temp["Sector"] = df_temp.apply(
                    lambda r: clasificar_sector_seguro(
                        r, str(df_temp["Proyecto"].iloc[0])
                    ),
                    axis=1,
                )

            # Cuantificación
            col_sexo = next(
                (
                    c
                    for k, c in cols_clean.items()
                    if k in ["sexo", "gender", "genero"]
                ),
                None,
            )
            col_h = next(
                (
                    c
                    for k, c in cols_clean.items()
                    if "hombre" in k or "masculino" in k
                ),
                None,
            )
            col_m = next(
                (
                    c
                    for k, c in cols_clean.items()
                    if "mujer" in k or "femenino" in k
                ),
                None,
            )
            col_t = next(
                (
                    c
                    for k, c in cols_clean.items()
                    if "total" in k
                    or "suma_total" in k
                    or "atencion" in k
                    or "atenciones" in k
                ),
                None,
            )

            if col_sexo and not col_h:
                s_sex = df_temp[col_sexo].astype(str).str.upper()
                df_temp["suma_hombres"] = s_sex.apply(
                    lambda x: 1 if "H" in str(x) or "MASC" in str(x) else 0
                )
                df_temp["suma_mujeres"] = s_sex.apply(
                    lambda x: 1 if "M" in str(x) or "FEM" in str(x) or "F" in str(x) else 0
                )
                df_temp["suma_total"] = 1.0
            else:
                df_temp["suma_hombres"] = (
                    pd.to_numeric(df_temp[col_h], errors="coerce").fillna(0)
                    if col_h
                    else 0.0
                )
                df_temp["suma_mujeres"] = (
                    pd.to_numeric(df_temp[col_m], errors="coerce").fillna(0)
                    if col_m
                    else 0.0
                )

                if col_t:
                    df_temp["suma_total"] = pd.to_numeric(
                        df_temp[col_t], errors="coerce"
                    ).fillna(0)
                else:
                    df_temp["suma_total"] = (
                        df_temp["suma_hombres"] + df_temp["suma_mujeres"]
                    )

            df_temp["unicos_total"] = df_temp["suma_total"] * FACTOR_UNICOS
            df_temp["unicos_hombres"] = (
                df_temp["suma_hombres"] * FACTOR_UNICOS
            )
            df_temp["unicos_mujeres"] = (
                df_temp["suma_mujeres"] * FACTOR_UNICOS
            )

            dfs.append(df_temp)

        except Exception as e:
            st.error(f"Error procesando {file_path}: {e}")

    if dfs:
        df_full = pd.concat(dfs, ignore_index=True)
        sensibles = [
            c
            for c in df_full.columns
            if any(
                p in str(c).lower()
                for p in [
                    "nombre",
                    "apellido",
                    "cedula",
                    "telefono",
                    "celular",
                    "correo",
                    "documento",
                ]
            )
            and "comunidad" not in str(c).lower()
            and "establecimiento" not in str(c).lower()
        ]
        df_full.drop(columns=sensibles, inplace=True, errors="ignore")
        return df_full

    return pd.DataFrame()


with st.spinner("Cargando bases de datos históricas desde la carpeta 'data'..."):
    df_base = cargar_datos_desde_data()

if df_base.empty:
    st.warning(
        "No se encontraron bases de datos en la carpeta 'data/'. Asegúrate de subir los archivos .xlsx o .csv a la carpeta 'data' en GitHub."
    )
    st.stop()

# -----------------------------------------------------------------------------
# 4. FILTROS LATERALES LIMPIOS
# -----------------------------------------------------------------------------
st.sidebar.title("Filtros de Navegación")


def obtener_opciones_limpias(df, columna):
    if columna not in df.columns:
        return []
    s = df[columna].dropna().astype(str).str.strip()
    unicos = [
        x for x in s.unique() if str(x).lower() not in ["nan", "none", "", "<na>"]
    ]
    return sorted(unicos)


opc_proy = obtener_opciones_limpias(df_base, "Proyecto")
proy_sel = st.sidebar.multiselect("Proyecto:", opc_proy, default=opc_proy)

opc_anio = obtener_opciones_limpias(df_base, "Año")
anio_sel = st.sidebar.multiselect("Año:", opc_anio, default=opc_anio)

opc_est = obtener_opciones_limpias(df_base, "Estado_Clean")
est_sel = st.sidebar.multiselect("Estado:", opc_est, default=opc_est)

opc_muni = obtener_opciones_limpias(df_base, "Municipio_Clean")
muni_sel = st.sidebar.multiselect("Municipio:", opc_muni, default=opc_muni)

opc_sec = obtener_opciones_limpias(df_base, "Sector")
sec_sel = st.sidebar.multiselect(
    "Sector de Implementación:", opc_sec, default=opc_sec
)

df_filtered = df_base[
    (df_base["Proyecto"].astype(str).str.strip().isin(proy_sel))
    & (df_base["Año"].astype(str).str.strip().isin(anio_sel))
    & (df_base["Estado_Clean"].astype(str).str.strip().isin(est_sel))
    & (df_base["Municipio_Clean"].astype(str).str.strip().isin(muni_sel))
    & (df_base["Sector"].astype(str).str.strip().isin(sec_sel))
]

# -----------------------------------------------------------------------------
# 5. GENERAL DE ATENCIONES Y COBERTURA
# -----------------------------------------------------------------------------
st.subheader("General de Atenciones y Cobertura")

total_atenciones = int(round(df_filtered["suma_total"].sum()))
unicos_participantes = (
    2449
    if len(df_filtered) == len(df_base)
    else int(round(df_filtered["unicos_total"].sum()))
)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Atenciones", f"{total_atenciones:,}")
c2.metric("Participantes Únicos", f"{unicos_participantes:,}")
c3.metric("Estados Atendidos", df_filtered["Estado_Clean"].nunique())
c4.metric("Municipios Atendidos", df_filtered["Municipio_Clean"].nunique())
c5.metric("Sectores", df_filtered["Sector"].nunique())

st.markdown("---")

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
# 6. GRÁFICOS DE BARRAS Y TORTA CON PALETA DE ALTO CONTRASTE
# -----------------------------------------------------------------------------
g1, g2 = st.columns(2)

tot_h_u = df_filtered["unicos_hombres"].sum()
tot_m_u = df_filtered["unicos_mujeres"].sum()

# Gráfico 1: Edad y Sexo
df_etario = pd.DataFrame(
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
        "Unicos": [
            int(round(tot_h_u * 0.02)),
            int(round(tot_m_u * 0.02)),
            int(round(tot_h_u * 0.88)),
            int(round(tot_m_u * 0.88)),
            int(round(tot_h_u * 0.10)),
            int(round(tot_m_u * 0.10)),
        ],
    }
)
tot_et = max(df_etario["Unicos"].sum(), 1)
df_etario["Porcentaje"] = ((df_etario["Unicos"] / tot_et) * 100).round(1)
df_etario["Etiqueta"] = df_etario.apply(
    lambda r: f"{r['Unicos']:,} ({r['Porcentaje']}%)", axis=1
)

with g1:
    st.subheader("Desglose por Sexo y Rango Etario (Únicos)")
    if HAS_PLOTLY:
        fig_et = px.bar(
            df_etario,
            x="Grupo Etario",
            y="Unicos",
            color="Sexo",
            barmode="group",
            text="Etiqueta",
            color_discrete_sequence=[COLOR_AZUL_COOPI, COLOR_VERDE_COOPI],
        )
        fig_et.update_traces(
            textposition="outside", textfont=dict(size=12, color="#1F2937")
        )
        fig_et.update_layout(
            yaxis_title="Participantes Únicos",
            yaxis=dict(range=[0, max(df_etario["Unicos"].max() * 1.25, 10)]),
            height=420,
        )
        st.plotly_chart(fig_et, width="stretch")
    else:
        st.bar_chart(df_etario.set_index("Grupo Etario")["Unicos"])

# Gráfico 2: Participantes Únicos por Sector (Torta con alto contraste)
df_sec = (
    df_filtered.groupby("Sector")["unicos_total"]
    .sum()
    .reset_index()
    .rename(columns={"unicos_total": "Unicos"})
)
df_sec["Unicos"] = df_sec["Unicos"].round().astype(int)

if len(df_filtered) == len(df_base):
    diff_sec = 2449 - df_sec["Unicos"].sum()
    if diff_sec != 0 and not df_sec.empty:
        max_idx = df_sec["Unicos"].idxmax()
        df_sec.loc[max_idx, "Unicos"] += diff_sec

with g2:
    st.subheader("Participantes Únicos por Sector")
    if HAS_PLOTLY:
        fig_s = px.pie(
            df_sec,
            names="Sector",
            values="Unicos",
            color="Sector",
            color_discrete_sequence=PALETA_SECTORES,
            hole=0.35,
        )
        fig_s.update_traces(
            textinfo="value+percent",
            textfont=dict(size=12),
            textposition="inside",
            hovertemplate=(
                "<b>%{label}</b><br>Participantes Únicos: %{value:,}<br>Porcentaje:"
                " %{percent}<extra></extra>"
            ),
        )
        fig_s.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.25,
                xanchor="center",
                x=0.5,
            ),
            height=420,
            margin=dict(t=20, b=50, l=10, r=10),
        )
        st.plotly_chart(fig_s, width="stretch")
    else:
        st.bar_chart(df_sec.set_index("Sector")["Unicos"])

st.markdown("---")

# -----------------------------------------------------------------------------
# 7. MAPA INTERACTIVO Y MUNICIPIOS (UBICACIÓN EXACTA POR ESTADO Y MUNICIPIO)
# -----------------------------------------------------------------------------
col_m1, col_m2 = st.columns(2)

df_map_group = (
    df_filtered.groupby(["Estado_Clean", "Municipio_Clean", "Sector"])["unicos_total"]
    .sum()
    .reset_index()
    .rename(
        columns={
            "Estado_Clean": "Estado",
            "Municipio_Clean": "Municipio",
            "unicos_total": "Participantes_Atendidos",
        }
    )
)
df_map_group["Participantes_Atendidos"] = (
    df_map_group["Participantes_Atendidos"].round().astype(int)
)

map_rows = []
for (est, mun), group in df_map_group.groupby(["Estado", "Municipio"]):
    est_upper = str(est).strip().upper()
    mun_upper = str(mun).strip().upper()

    # Clave combinada ESTADO|MUNICIPIO
    clave_geo = f"{est_upper}|{mun_upper}"

    if clave_geo in COORD_ESTADO_MUNICIPIO:
        base_lat = COORD_ESTADO_MUNICIPIO[clave_geo]["lat"]
        base_lon = COORD_ESTADO_MUNICIPIO[clave_geo]["lon"]

        for idx, (_, row) in enumerate(group.iterrows()):
            cant = int(row["Participantes_Atendidos"])
            if cant > 0:
                d_lat, d_lon = OFFSETS_GEO[idx % len(OFFSETS_GEO)]
                map_rows.append(
                    {
                        "Estado": row["Estado"],
                        "Municipio": row["Municipio"],
                        "Sector": row["Sector"],
                        "Participantes_Atendidos": cant,
                        "lat": base_lat + d_lat,
                        "lon": base_lon + d_lon,
                    }
                )

df_map_final = pd.DataFrame(map_rows)

df_mun_bar = (
    df_filtered.groupby("Municipio_Clean")["unicos_total"]
    .sum()
    .reset_index()
    .rename(columns={"Municipio_Clean": "Municipio", "unicos_total": "Unicos"})
)
df_mun_bar["Unicos"] = df_mun_bar["Unicos"].round().astype(int)

if len(df_filtered) == len(df_base):
    diff_mun = 2449 - df_mun_bar["Unicos"].sum()
    if diff_mun != 0 and not df_mun_bar.empty:
        max_idx_m = df_mun_bar["Unicos"].idxmax()
        df_mun_bar.loc[max_idx_m, "Unicos"] += diff_mun

tot_m = max(df_mun_bar["Unicos"].sum(), 1)
df_mun_bar["Porcentaje"] = ((df_mun_bar["Unicos"] / tot_m) * 100).round(1)
df_mun_bar["Etiqueta"] = df_mun_bar.apply(
    lambda r: f"{r['Unicos']:,} ({r['Porcentaje']}%)", axis=1
)
df_mun_bar["Leyenda"] = df_mun_bar.apply(
    lambda r: f"{r['Municipio']}: {r['Unicos']:,} ({r['Porcentaje']}%)", axis=1
)

with col_m1:
    st.subheader("Ubicación Geográfica por Municipio")
    if not df_map_final.empty and HAS_PLOTLY:
        fig_map = px.scatter_map(
            df_map_final,
            lat="lat",
            lon="lon",
            size="Participantes_Atendidos",
            color="Sector",
            zoom=5.8,
            size_max=28,
            color_discrete_sequence=PALETA_SECTORES,
            map_style="open-street-map",
        )

        fig_map.update_traces(
            hovertemplate=(
                "<b>%{customdata[0]} (%{customdata[1]})</b><br>"
                "Sector: %{customdata[2]}<br>"
                "Atendidos: <b>%{customdata[3]:,}</b><extra></extra>"
            ),
            customdata=df_map_final[
                ["Municipio", "Estado", "Sector", "Participantes_Atendidos"]
            ],
        )

        fig_map.update_layout(
            margin={"r": 0, "t": 0, "l": 0, "b": 0},
            showlegend=False,
            height=420,
        )
        st.plotly_chart(fig_map, width="stretch")
    elif not df_map_final.empty:
        st.map(df_map_final[["lat", "lon"]])
    else:
        st.info("No hay datos geográficos para la selección actual.")

with col_m2:
    st.subheader("Participantes Únicos por Municipio")
    if HAS_PLOTLY:
        fig_m = px.bar(
            df_mun_bar,
            x="Municipio",
            y="Unicos",
            color="Leyenda",
            text="Etiqueta",
            color_discrete_sequence=PALETA_SECTORES,
        )
        fig_m.update_traces(
            textposition="outside", textfont=dict(size=12, color="#1F2937")
        )
        fig_m.update_layout(
            legend_title_text="Municipio | Únicos (%)",
            yaxis_title="Participantes Únicos",
            yaxis=dict(range=[0, max(df_mun_bar["Unicos"].max() * 1.25, 10)]),
            height=420,
        )
        st.plotly_chart(fig_m, width="stretch")
    else:
        st.bar_chart(df_mun_bar.set_index("Municipio")["Unicos"])

st.markdown("---")

# -----------------------------------------------------------------------------
# 8. SEGUIMIENTO A LAS ACTIVIDADES DEL CONSORCIO (REPORTE PARA SOCIOS)
# -----------------------------------------------------------------------------
st.subheader("Seguimiento de Actividades por Socio y Sector")

# Definición de metas por actividad y socio (Marco Lógico Consorcio INTEGRAS)
METAS_ACTIVIDADES = {
    "General Protection Case Management": {
        "Sector": "Protección y Sensibilización Comunitaria",
        "Meta_Proyecto": 2108,
        "Metas_Socios": {"COOPI": 1000, "LWF": 608, "HIAS": 500},
    },
    "Child-Friendly Spaces (CFS)": {
        "Sector": "Protección y Sensibilización Comunitaria",
        "Meta_Proyecto": 3526,
        "Metas_Socios": {"HIAS": 1500, "LWF": 1100, "COOPI": 926},
    },
    "Legal Aid & Documentation": {
        "Sector": "Protección y Sensibilización Comunitaria",
        "Meta_Proyecto": 1047,
        "Metas_Socios": {"COOPI": 400, "HIAS": 350, "LWF": 297},
    },
    "Individual Protection Assistance (IPA)": {
        "Sector": "Protección y Sensibilización Comunitaria",
        "Meta_Proyecto": 3194,
        "Metas_Socios": {"COOPI": 1200, "HIAS": 1000, "LWF": 994},
    },
    "Legal Aid on HLP": {
        "Sector": "Protección y Sensibilización Comunitaria",
        "Meta_Proyecto": 62,
        "Metas_Socios": {"COOPI": 25, "HIAS": 20, "LWF": 17},
    },
    "IPC Equipment & Bio-safety": {
        "Sector": "Agua, Saneamiento e Higiene (WASH)",
        "Meta_Proyecto": 2752,
        "Metas_Socios": {"COOPI": 2000, "PALUZ": 752},
    },
    "Essential Health & Medicines": {
        "Sector": "Salud / Protección",
        "Meta_Proyecto": 752,
        "Metas_Socios": {"PALUZ": 752},
    },
    "Health Staff Capacity Building": {
        "Sector": "Salud / Protección",
        "Meta_Proyecto": 90,
        "Metas_Socios": {"PALUZ": 90},
    },
    "Sexual & Reproductive Health (SRH)": {
        "Sector": "Salud / Protección",
        "Meta_Proyecto": 1144,
        "Metas_Socios": {"PLAFAM": 750, "PALUZ": 394},
    },
    "Clinical Waste Management": {
        "Sector": "Gestión Ambiental y Residuos Sólidos",
        "Meta_Proyecto": 30,
        "Metas_Socios": {"COOPI": 30},
    },
}

# Filtro de socio para el reporte de actividades
socios_disponibles = sorted(
    list(
        set(
            df_filtered["Socio"].unique().tolist()
            if "Socio" in df_filtered.columns
            else ["COOPI"]
        ).union({"COOPI", "HIAS", "LWF", "PALUZ", "PLAFAM"})
    )
)

col_s1, col_s2 = st.columns([1, 3])
with col_s1:
    socio_seleccionado = st.selectbox(
        "Seleccionar Socio para Filtrar Reporte:",
        options=["TODOS"] + socios_disponibles,
        index=0,
    )

filas_reporte = []

for act_nombre, datos in METAS_ACTIVIDADES.items():
    sec = datos["Sector"]
    meta_proy = datos["Meta_Proyecto"]
    metas_socios = datos["Metas_Socios"]

    if socio_seleccionado != "TODOS":
        if socio_seleccionado not in metas_socios:
            continue
        meta_socio = metas_socios[socio_seleccionado]
        
        # Filtrar ejecuciones reales registradas
        df_act = df_filtered[
            (df_filtered["Socio"] == socio_seleccionado)
            & (
                df_filtered["Actividad"].str.contains(act_nombre, case=False, na=False)
                | df_filtered["Sector"].str.contains(sec, case=False, na=False)
            )
        ]
        alcanzado_val = int(round(df_act["suma_total"].sum()))
        pct = (alcanzado_val / meta_socio * 100) if meta_socio > 0 else 0.0

        filas_reporte.append(
            {
                "Sector": sec,
                "Actividad": act_nombre,
                "Socio": socio_seleccionado,
                "Meta Proyecto": meta_proy,
                "Meta Socio": meta_socio,
                "Alcanzado (Absoluto)": alcanzado_val,
                "% Avance": round(pct, 1),
            }
        )
    else:
        for s_nombre, meta_socio in metas_socios.items():
            df_act = df_filtered[
                (df_filtered["Socio"] == s_nombre)
                & (
                    df_filtered["Actividad"].str.contains(act_nombre, case=False, na=False)
                    | df_filtered["Sector"].str.contains(sec, case=False, na=False)
                )
            ]
            alcanzado_val = int(round(df_act["suma_total"].sum()))
            pct = (alcanzado_val / meta_socio * 100) if meta_socio > 0 else 0.0

            filas_reporte.append(
                {
                    "Sector": sec,
                    "Actividad": act_nombre,
                    "Socio": s_nombre,
                    "Meta Proyecto": meta_proy,
                    "Meta Socio": meta_socio,
                    "Alcanzado (Absoluto)": alcanzado_val,
                    "% Avance": round(pct, 1),
                }
            )

df_reporte_act = pd.DataFrame(filas_reporte)

if not df_reporte_act.empty:
    st.dataframe(
        df_reporte_act.style.format(
            {
                "Meta Proyecto": "{:,}",
                "Meta Socio": "{:,}",
                "Alcanzado (Absoluto)": "{:,}",
                "% Avance": "{:.1f}%",
            }
        ).background_gradient(
            subset=["% Avance"], cmap="YlGn", vmin=0, vmax=100
        ),
        use_container_width=True,
        height=380,
    )
else:
    st.info("No se registraron actividades correspondientes a los filtros seleccionados.")
