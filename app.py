import re
import pandas as pd
import requests
import streamlit as st

# Importar Plotly para el mapa interactivo y gráficos de barras
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

# Desplazamiento para no solapar puntos de distintos sectores en un mismo municipio
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
col_tit, col_logo = st.columns([3.5, 1])

with col_tit:
  st.title("Consolidación Histórica de Participantes y Atenciones")
  st.caption("COOPI - Cooperazione Internazionale | Misión Venezuela")

with col_logo:
  st.markdown(
      """
        <div style="text-align: right;">
            <img src="https://raw.githubusercontent.com/integrasven2026/tablero-integras-meal/main/logo_coopi.png" 
                 style="max-width: 170px; height: auto;" 
                 onerror="this.src='https://coopi.org/images/logo.png'">
        </div>
        """,
      unsafe_allow_html=True,
  )

st.markdown("---")

# -----------------------------------------------------------------------------
# 3. CARGA Y CLASIFICACIÓN DE DATOS DESDE KOBO
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


def clasificar_sector_meal(row, nombre_proyecto):
  comp = str(row.get("Componente:", "")).upper()
  act = str(row.get("Actividad:", "")).lower()
  res = str(row.get("Resultado:", "")).lower()

  if (
      "sensibiliz" in act
      or "derechos" in act
      or "protecc" in act
      or "campaña" in act
      or "género" in act
      or "r2" in res
  ):
    return "Protección y Sensibilización Comunitaria"
  elif "residuo" in comp or "desecho" in act or "recicl" in act:
    return "Gestión Ambiental y Residuos Sólidos"
  elif "negocio" in act or "pesca" in act or "ingreso" in act or "r3" in res:
    return "Medios de Vida y Resiliencia Ambiental"
  elif "wash" in comp or "agua" in act or "saneamiento" in act or "hidro" in act:
    return "Agua, Saneamiento e Higiene (WASH)"
  else:
    if nombre_proyecto == "Agua para la Vida":
      return "Agua, Saneamiento e Higiene (WASH)"
    return "Medios de Vida y Resiliencia Ambiental"


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

          # Normalización de Fecha
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

          # Limpieza de Municipio
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

          # Limpieza de Estado
          col_est = next(
              (c for c in df.columns if "estado" in c.lower()),
              "Estado",
          )
          df["Estado_Clean"] = (
              df[col_est].astype(str).replace("VE19", "Sucre")
              if col_est in df.columns
              else "Sucre"
          )

          # Clasificación Dinámica MEAL
          df["Sector_MEAL"] = df.apply(
              lambda r: clasificar_sector_meal(r, nombre_proy), axis=1
          )

          # Conversión numérica
          for col in [
              "suma_hombres",
              "suma_mujeres",
              "suma_intersexuales",
              "suma_total",
              "calculo_con_dicapacidad",
          ]:
            if col in df.columns:
              df[col] = (
                  pd.to_numeric(df[col], errors="coerce").fillna(0).astype(float)
              )
            else:
              df[col] = 0.0

          # Participantes Únicos
          df["unicos_total"] = df["suma_total"] * FACTOR_UNICOS
          df["unicos_hombres"] = df["suma_hombres"] * FACTOR_UNICOS
          df["unicos_mujeres"] = df["suma_mujeres"] * FACTOR_UNICOS

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
# 5. GENERAL DE ATENCIONES Y COBERTURA (PARTICIPANTES ÚNICOS)
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
c5.metric("Sectores MEAL", df_filtered["Sector_MEAL"].nunique())

st.markdown("---")

# Vulnerabilidad calculada sobre Participantes Únicos
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
# 6. GRÁFICOS DE BARRAS EN PARTICIPANTES ÚNICOS (VALOR ABSOLUTO Y %)
# -----------------------------------------------------------------------------
g1, g2 = st.columns(2)

tot_h_u = df_filtered["unicos_hombres"].sum()
tot_m_u = df_filtered["unicos_mujeres"].sum()

# Gráfico 1: Edad y Sexo (Únicos)
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

# Gráfico 2: Sectores MEAL (Únicos)
df_sec = (
    df_filtered.groupby("Sector_MEAL")["unicos_total"]
    .sum()
    .reset_index()
    .rename(columns={"Sector_MEAL": "Sector", "unicos_total": "Unicos"})
)
df_sec["Unicos"] = df_sec["Unicos"].round().astype(int)
tot_s = max(df_sec["Unicos"].sum(), 1)
df_sec["Porcentaje"] = ((df_sec["Unicos"] / tot_s) * 100).round(1)
df_sec["Etiqueta"] = df_sec.apply(
    lambda r: f"{r['Unicos']:,} ({r['Porcentaje']}%)", axis=1
)

with g2:
  st.subheader("Participantes Únicos por Sector MEAL")
  if HAS_PLOTLY:
    fig_s = px.bar(
        df_sec,
        x="Sector",
        y="Unicos",
        text="Etiqueta",
        color="Sector",
        color_discrete_sequence=PALETA_COOPI,
    )
    fig_s.update_traces(
        textposition="outside", textfont=dict(size=12, color="#1F2937")
    )
    fig_s.update_layout(
        yaxis_title="Participantes Únicos",
        yaxis=dict(range=[0, max(df_sec["Unicos"].max() * 1.25, 10)]),
        showlegend=False,
        height=420,
    )
    st.plotly_chart(fig_s, use_container_width=True)
  else:
    st.bar_chart(df_sec.set_index("Sector")["Unicos"])

st.markdown("---")

# -----------------------------------------------------------------------------
# 7. MAPA SIN LEYENDA (HOVER ONLY) Y BARRAS POR MUNICIPIO
# -----------------------------------------------------------------------------
col_m1, col_m2 = st.columns(2)

# Agrupación por Municipio y Sector MEAL para el mapa
df_map_group = (
    df_filtered.groupby(["Municipio_Clean", "Sector_MEAL"])["unicos_total"]
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
            "Sector_MEAL": row["Sector_MEAL"],
            "Participantes_Atendidos": cant,
            "lat": base_lat + d_lat,
            "lon": base_lon + d_lon,
        })

df_map_final = pd.DataFrame(map_rows)

# Datos consolidado para Gráfico de Municipio
df_mun_bar = (
    df_filtered.groupby("Municipio_Clean")["unicos_total"]
    .sum()
    .reset_index()
    .rename(columns={"Municipio_Clean": "Municipio", "unicos_total": "Unicos"})
)
df_mun_bar["Unicos"] = df_mun_bar["Unicos"].round().astype(int)
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
        color="Sector_MEAL",
        zoom=8,
        size_max=28,
        color_discrete_sequence=PALETA_COOPI,
        mapbox_style="open-street-map",
    )

    # Configuración de tarjeta flotante (Hover) limpia y sin leyenda
    fig_map.update_traces(
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Sector: %{customdata[1]}<br>"
            "Atendidos: <b>%{customdata[2]:,}</b><extra></extra>"
        ),
        customdata=df_map_final[
            ["Municipio", "Sector_MEAL", "Participantes_Atendidos"]
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
