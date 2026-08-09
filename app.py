import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# -----------------------------------------------------------------------------
# PALETA DE COLORES OFICIAL COOPI (Extraída del Logo)
# -----------------------------------------------------------------------------
COLOR_AZUL_COOPI = "#0082C8"
COLOR_VERDE_COOPI = "#00A859"
COLOR_TEXTO_OSCURO = "#1F2937"
COLOR_FONDO_CARTA = "#F8FAFC"

PALETA_COOPI = [
    "#0082C8",
    "#00A859",
    "#00A8E8",
    "#34D399",
    "#0284C7",
    "#10B981",
]

# Configuración de página
st.set_page_config(
    page_title="Tablero COOPI Venezuela", page_icon="📊", layout="wide"
)

# -----------------------------------------------------------------------------
# 4. ENCABEZADO CON LOGO EN LA PARTE SUPERIOR DERECHA
# -----------------------------------------------------------------------------
col_titulo, col_logo = st.columns([3.5, 1])

with col_titulo:
    st.title("Consolidado de Atenciones y Cobertura")
    st.caption("COOPI - Cooperazione Internazionale | Misión Venezuela")

with col_logo:
    # Asegúrate de colocar la ruta/archivo correcto de tu logo
    st.image("logo_coopi.jpg", use_container_width=True)

st.divider()

# -----------------------------------------------------------------------------
# DATOS DE EJEMPLO Y LIMPIEZA DE CÓDIGOS DE MUNICIPIOS (Punto 3)
# -----------------------------------------------------------------------------
data_municipios = {
    "codigo_municipio": [
        "VE1001 - Libertador",
        "VE1002 - Sucre",
        "VE1003 - Baruta",
        "VE1004 - Chacao",
        "VE1005 - El Hatillo",
    ],
    "participantes": [950, 720, 430, 210, 139],
}
df_muni = pd.DataFrame(data_municipios)

# Función para eliminar códigos (ej. "VE1001 - ") y dejar solo el nombre
df_muni["nombre_municipio"] = df_muni["codigo_municipio"].apply(
    lambda x: re.sub(r"^[A-Z0-9_-]+\s*-\s*", "", str(x))
)

total_participantes = df_muni["participantes"].sum()
df_muni["porcentaje"] = (df_muni["participantes"] / total_participantes) * 100

# Formato para la barra: Valor Absoluto + Porcentaje (Punto 2)
df_muni["etiqueta_barras"] = df_muni.apply(
    lambda row: f"{row['participantes']:,} ({row['porcentaje']:.1f}%)", axis=1
)

# -----------------------------------------------------------------------------
# METRICAS PRINCIPALES Y PORCENTAJES DE VULNERABILIDAD (Punto 1)
# -----------------------------------------------------------------------------
st.subheader("General de Atenciones y Cobertura")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Atenciones", "4,462")
m2.metric("Participantes Únicos", f"{total_participantes:,}")
m3.metric("Estados Atendidos", "1")
m4.metric("Municipios Atendidos", f"{len(df_muni)}")
m5.metric("Sectores MEAL", "5")

st.markdown("---")
st.subheader("Distribución de Participantes por Grupos de Vulnerabilidad (%)")

# Cálculo riguroso sobre Participantes Únicos (2,449)
v1, v2, v3, v4, v5, v6 = st.columns(6)
v1.metric("% Mujeres", "62.7%")
v2.metric("% Hombres", "37.2%")
v3.metric("% Niñas y Niños", "1.3%")
v4.metric("% Discapacidad", "0.0%")
v5.metric("% Indígenas", "0.0%")
v6.metric("% Embarazadas/Lact.", "0.0%")

st.markdown("---")

# -----------------------------------------------------------------------------
# 2 y 3. GRÁFICO DE BARRAS CON VALOR ABSOLUTO, PORCENTAJE Y LEYENDA LIMPIA
# -----------------------------------------------------------------------------
col_graf1, col_graf2 = st.columns(2)

with col_graf1:
    st.markdown("### Participantes Únicos por Municipio")

    fig_muni = px.bar(
        df_muni,
        x="participantes",
        y="nombre_municipio",
        orientation="h",
        text="etiqueta_barras",
        color="nombre_municipio",
        color_discrete_sequence=PALETA_COOPI,
        labels={
            "participantes": "Cantidad",
            "nombre_municipio": "Municipio",
            "etiqueta_barras": "Total (%)",
        },
    )

    # Configuración de etiquetas y formato dentro del gráfico
    fig_muni.update_traces(
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Cantidad: %{x:,}<br>Porcentaje: %{customdata:.1f}%<extra></extra>",
        customdata=df_muni["porcentaje"],
    )

    fig_muni.update_layout(
        showlegend=True,
        legend_title_text="Municipio | Total (%)",
        xaxis_title="Número de Participantes",
        yaxis_title="",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLOR_TEXTO_OSCURO),
        margin=dict(l=20, r=50, t=30, b=20),
    )

    # Personalizar la leyenda para mostrar Nombre, Valor Absoluto y Porcentaje (Punto 3)
    for i, row in df_muni.iterrows():
        fig_muni.for_each_trace(
            lambda trace, r=row: trace.update(
                name=f"{r['nombre_municipio']} - {r['participantes']:,} ({r['porcentaje']:.1f}%)"
            )
            if trace.name == r["nombre_municipio"]
            else None
        )

    st.plotly_chart(fig_muni, use_container_width=True)

with col_graf2:
    st.markdown("### Distribución por Sector MEAL")

    df_sector = pd.DataFrame(
        {
            "sector": [
                "Agua para la Vida",
                "Eco Resiliencia",
                "Protección",
                "Salud",
                "Nutrición",
            ],
            "atenciones": [1800, 1200, 800, 400, 262],
        }
    )
    total_sec = df_sector["atenciones"].sum()
    df_sector["porcentaje"] = (df_sector["atenciones"] / total_sec) * 100
    df_sector["etiqueta"] = df_sector.apply(
        lambda r: f"{r['atenciones']:,} ({r['porcentaje']:.1f}%)", axis=1
    )

    fig_sector = px.bar(
        df_sector,
        x="sector",
        y="atenciones",
        text="etiqueta",
        color="sector",
        color_discrete_sequence=PALETA_COOPI,
    )

    fig_sector.update_traces(textposition="outside")
    fig_sector.update_layout(
        showlegend=False,
        xaxis_title="Sector",
        yaxis_title="Total Atenciones",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLOR_TEXTO_OSCURO),
    )

    st.plotly_chart(fig_sector, use_container_width=True)
