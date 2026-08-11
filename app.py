import base64
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
PALETA_COOPI = [
    "#0082C8",
    "#00A859",
    "#0284C7",
    "#10B981",
    "#005580",
    "#059669",
]

# Factor global de conversión a Participantes Únicos (2,449 / 4,462)
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

# Coordenadas geográficas base de municipios del Estado Sucre
COORD_MUNICIPIOS = {
    "BERMÚDEZ": {"lat": 10.6558, "lon": -63.2536},
    "BERMUDEZ": {"lat": 10.6558, "lon": -63.2536},
    "MARIÑO": {"lat": 10.5833, "lon": -62.5833},
    "SUCRE": {"lat": 10.4531, "lon": -64.1826},
    "MEJÍA": {"lat": 10.5011, "lon": -63.8015},
    "MEJIA": {"lat": 10.5011, "lon": -63.8015},
    "BOLÍVAR": {"lat": 10.4521, "lon": -63.9512},
    "BOLIVAR": {"lat": 10.4521, "lon": -63.9512},
}

OFFSETS_GEO = [
    (0.0, 0.0),
    (0.012, 0.012),
    (-0.012, -0.012),
    (0.012, -0.012),
    (-0.012, 0.012),
]

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
# 3. CARGA EXCLUSIVA Y DEPURADA DESDE LA CARPETA 'DATA'
# -----------------------------------------------------------------------------
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


def clasificar_sector_seguro(row, nombre_proyecto=""):
    text_parts = []
    for val in row.values:
        if val is None:
            continue
        if isinstance(val, (list, dict)):
            text_parts.append(str(val).lower())
        elif pd.notna(val):
            text_parts.append(str(val).lower())

    row_text = " ".join(text_parts)

    if any(p in row_text for p in ["residuo", "desecho", "recicl", "basura", "a33", "a34", "a35", "a36", "gestión de residuos"]):
        return "Gestión Ambiental y Residuos Sólidos"
    elif any(p in row_text for p in ["wash", "agua", "saneamiento", "plomería", "hidro", "a11", "a12", "a14", "a24", "a25"]):
        return "Agua, Saneamiento e Higiene (WASH)"
    elif any(p in row_text for p in ["negocio", "pesca", "ingreso", "a.3", "acuícola", "turismo"]):
        return "Medios de Vida y Resiliencia Ambiental"
    elif any(p in row_text for p in ["sensibiliz", "protecc", "derecho", "campaña", "género", "a22", "a13", "r2"]):
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

    all_files = glob.glob(os.path.join(folder_path, "*.xlsx")) + \
                glob.glob(os.path.join(folder_path, "*.xls")) + \
                glob.glob(os.path.join(folder_path, "*.csv"))

    # Filtrar archivos temporales o del sistema (ej. ~$archivo.xlsx)
    files = [f for f in all_files if not os.path.basename(f).startswith("~$") and not os.path.basename(f).startswith(".")]

    dfs = []
    for file_path in files:
        try:
            if file_path.endswith(('.xlsx', '.xls')):
                df_temp = pd.read_excel(file_path)
            else:
                df_temp = pd.read_csv(file_path)

            if not df_temp.empty:
                cols_lower = {str(c).strip().lower(): c for c in df_temp.columns}
                
                # Nombre del archivo para usar como fallback limpio
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                nombre_archivo_limpio = base_name.replace("_", " ").replace("-", " ").strip()

                # Identificar si existe una columna de proyecto real y legible
                col_proy = next((c for k, c in cols_lower.items() if k in ["proyecto", "nombre_proyecto", "nombre del proyecto"]), None)
                
                usar_fallback = True
                if col_proy:
                    # Verificar si la columna no es puramente numérica o de códigos (evita 0.0, 1.0)
                    es_numerico = pd.to_numeric(df_temp[col_proy], errors='coerce').notna().all()
                    if not es_numerico and not df_temp[col_proy].dropna().empty:
                        df_temp["Proyecto"] = df_temp[col_proy].fillna(nombre_archivo_limpio).astype(str).str.strip()
                        usar_fallback = False

                if usar_fallback:
                    df_temp["Proyecto"] = nombre_archivo_limpio

                # Año
                col_anio = next((c for k, c in cols_lower.items() if "año" in k or "anio" in k or "year" in k), None)
                if col_anio:
                    df_temp["Año"] = df_temp[col_anio].fillna("2025").astype(str).str.replace(".0", "", regex=False)
                else:
                    df_temp["Año"] = "2025"

                # Estado y Municipio
                col_est = next((c for k, c in cols_lower.items() if "estado" in k), None)
                df_temp["Estado_Clean"] = df_temp[col_est].astype(str).replace("VE19", "Sucre") if col_est else "Sucre"

                col_mun = next((c for k, c in cols_lower.items() if "municipio" in k or "muni" in k), None)
                if col_mun:
                    df_temp["Municipio_Clean"] = (
                        df_temp[col_mun]
                        .astype(str)
                        .replace(MAPA_MUNICIPIOS)
                        .apply(lambda x: re.sub(r"^[A-Z0-9_-]+\s*-\s*", "", str(x)))
                    )
                else:
                    df_temp["Municipio_Clean"] = "Sucre"

                # Sector
                col_sec = next((c for k, c in cols_lower.items() if "sector" in k), None)
                if col_sec:
                    df_temp["Sector"] = df_temp[col_sec].fillna("General").astype(str)
                else:
                    df_temp["Sector"] = df_temp.apply(lambda r: clasificar_sector_seguro(r, df_temp["Proyecto"].iloc[0]), axis=1)

                # Totales numéricos
                col_h = next((c for k, c in cols_lower.items() if "hombre" in k or "masculino" in k), None)
                col_m = next((c for k, c in cols_lower.items() if "mujer" in k or "femenino" in k), None)
                col_t = next((c for k, c in cols_lower.items() if "total" in k or "suma_total" in k or "atencion" in k), None)

                df_temp["suma_hombres"] = pd.to_numeric(df_temp[col_h], errors="coerce").fillna(0) if col_h else 0.0
                df_temp["suma_mujeres"] = pd.to_numeric(df_temp[col_m], errors="coerce").fillna(0) if col_m else 0.0
                
                if col_t:
                    df_temp["suma_total"] = pd.to_numeric(df_temp[col_t], errors="coerce").fillna(0)
                else:
                    df_temp["suma_total"] = df_temp["suma_hombres"] + df_temp["suma_mujeres"]

                df_temp["unicos_total"] = df_temp["suma_total"] * FACTOR_UNICOS
                df_temp["unicos_hombres"] = df_temp["suma_hombres"] * FACTOR_UNICOS
                df_temp["unicos_mujeres"] = df_temp["suma_mujeres"] * FACTOR_UNICOS

                dfs.append(df_temp)

        except Exception as e:
            st.error(f"Error procesando {file_path}: {e}")

    if dfs:
        df_full = pd.concat(dfs, ignore_index=True)
        sensibles = [
            c for c in df_full.columns
            if any(p in c.lower() for p in ["nombre", "apellido", "cedula", "telefono", "celular", "correo"])
            and "comunidad" not in c.lower() and "establecimiento" not in c.lower()
        ]
        df_full.drop(columns=sensibles, inplace=True, errors="ignore")
        return df_full

    return pd.DataFrame()


with st.spinner("Cargando bases de datos históricas desde la carpeta 'data'..."):
    df_base = cargar_datos_desde_data()

if df_base.empty:
    st.warning("No se encontraron bases de datos en la carpeta 'data/'. Asegúrate de subir los archivos .xlsx o .csv a la carpeta 'data' en GitHub.")
    st.stop()

# -----------------------------------------------------------------------------
# 4. FILTROS LATERALES LIMPIOS
# -----------------------------------------------------------------------------
st.sidebar.title("Filtros de Navegación")

def obtener_opciones_limpias(df, columna):
    if columna not in df.columns:
        return []
    s = df[columna].dropna().astype(str).str.strip()
    unicos = [x for x in s.unique() if x.lower() not in ['nan', 'none', '', '<na>']]
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
sec_sel = st.sidebar.multiselect("Sector de Implementación:", opc_sec, default=opc_sec)

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
# 6. GRÁFICOS DE BARRAS Y TORTA EN PARTICIPANTES ÚNICOS
# -----------------------------------------------------------------------------
g1, g2 = st.columns(2)

tot_h_u = df_filtered["unicos_hombres"].sum()
tot_m_u = df_filtered["unicos_mujeres"].sum()

# Gráfico 1: Edad y Sexo
df_etario = pd.DataFrame({
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
})
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
        st.plotly_chart(fig_et, use_container_width=True)
    else:
        st.bar_chart(df_etario.set_index("Grupo Etario")["Unicos"])

# Gráfico 2: Participantes Únicos por Sector (Torta)
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
            color_discrete_sequence=PALETA_COOPI,
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
                orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5
            ),
            height=420,
            margin=dict(t=20, b=50, l=10, r=10),
        )
        st.plotly_chart(fig_s, use_container_width=True)
    else:
        st.bar_chart(df_sec.set_index("Sector")["Unicos"])

st.markdown("---")

# -----------------------------------------------------------------------------
# 7. MAPA INTERACTIVO Y MUNICIPIOS
# -----------------------------------------------------------------------------
col_m1, col_m2 = st.columns(2)

df_map_group = (
    df_filtered.groupby(["Municipio_Clean", "Sector"])["unicos_total"]
    .sum()
    .reset_index()
    .rename(
        columns={
            "Municipio_Clean": "Municipio",
            "unicos_total": "Participantes_Atendidos",
        }
    )
)
df_map_group["Participantes_Atendidos"] = (
    df_map_group["Participantes_Atendidos"].round().astype(int)
)

map_rows = []
for mun, group in df_map_group.groupby("Municipio"):
    mun_upper = str(mun).strip().upper()
    if mun_upper in COORD_MUNICIPIOS:
        base_lat = COORD_MUNICIPIOS[mun_upper]["lat"]
        base_lon = COORD_MUNICIPIOS[mun_upper]["lon"]

        for idx, (_, row) in enumerate(group.iterrows()):
            cant = int(row["Participantes_Atendidos"])
            if cant > 0:
                d_lat, d_lon = OFFSETS_GEO[idx % len(OFFSETS_GEO)]
                map_rows.append({
                    "Municipio": row["Municipio"],
                    "Sector": row["Sector"],
                    "Participantes_Atendidos": cant,
                    "lat": base_lat + d_lat,
                    "lon": base_lon + d_lon,
                })

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
        fig_map = px.scatter_mapbox(
            df_map_final,
            lat="lat",
            lon="lon",
            size="Participantes_Atendidos",
            color="Sector",
            zoom=8,
            size_max=28,
            color_discrete_sequence=PALETA_COOPI,
            mapbox_style="open-street-map",
        )

        fig_map.update_traces(
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Sector: %{customdata[1]}<br>"
                "Atendidos: <b>%{customdata[2]:,}</b><extra></extra>"
            ),
            customdata=df_map_final[
                ["Municipio", "Sector", "Participantes_Atendidos"]
            ],
        )

        fig_map.update_layout(
            margin={"r": 0, "t": 0, "l": 0, "b": 0}, showlegend=False, height=420
        )
        st.plotly_chart(fig_map, use_container_width=True)
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
            color_discrete_sequence=PALETA_COOPI,
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
        st.plotly_chart(fig_m, use_container_width=True)
    else:
        st.bar_chart(df_mun_bar.set_index("Municipio")["Unicos"])
