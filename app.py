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

    # Filtrar archivos temporales o del sistema
    files = [
        f
        for f in all_files
        if not os.path.basename(f).startswith("~$")
        and not os.path.basename(f).startswith(".")
    ]

    dfs = []
    for file_path in files:
        try:
            # 1. Cargar archivo
            if file_path.endswith((".xlsx", ".xls")):
                xls = pd.ExcelFile(file_path)
                # Seleccionar automáticamente la hoja con datos principal
                sheet = (
                    "BBDD"
                    if "BBDD" in xls.sheet_names
                    else xls.sheet_names[0]
                )
                df_temp = pd.read_excel(file_path, sheet_name=sheet)
            else:
                df_temp = pd.read_csv(file_path)

            if df_temp.empty:
                continue

            # Diccionario auxiliar de nombres minúsculos sin espacios extras
            cols_clean = {
                str(c).strip().lower(): c for c in df_temp.columns
            }

            # Nombre base limpio como fallback
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            nombre_archivo_limpio = (
                base_name.replace("_", " ").replace("-", " ").strip()
            )

            # -----------------------------------------------------------------
            # ESTANDARIZACIÓN DE PROYECTO
            # -----------------------------------------------------------------
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

            # -----------------------------------------------------------------
            # ESTANDARIZACIÓN DE AÑO
            # -----------------------------------------------------------------
            col_anio = next(
                (
                    c
                    for k, c in cols_clean.items()
                    if k in ["año", "anio", "year", "fecha", "fecha "]
                ),
                None,
            )
            if col_anio:
                # Intentar extraer año en formato fecha o numérico
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

            # -----------------------------------------------------------------
            # ESTANDARIZACIÓN DE ESTADO Y MUNICIPIO
            # -----------------------------------------------------------------
            col_est = next(
                (
                    c
                    for k, c in cols_clean.items()
                    if "estado" in k or "est" in k
                ),
                None,
            )
            df_temp["Estado_Clean"] = (
                df_temp[col_est].astype(str).replace("VE19", "Sucre")
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
                    .str.strip()
                    .str.title()
                )
            else:
                df_temp["Municipio_Clean"] = "Sucre"

            # -----------------------------------------------------------------
            # ESTANDARIZACIÓN DE SECTOR
            # -----------------------------------------------------------------
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
                        r, df_temp["Proyecto"].iloc[0]
                    ),
                    axis=1,
                )

            # -----------------------------------------------------------------
            # ESTANDARIZACIÓN Y CONTEO DE PERSONAS (INDIVIDUAL VS AGREGADO)
            # -----------------------------------------------------------------
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

            # CASO A: Base de datos por registros individuales (ej: CONAHVE)
            if col_sexo and not col_h:
                s_sex = df_temp[col_sexo].astype(str).str.upper()
                df_temp["suma_hombres"] = s_sex.apply(
                    lambda x: 1 if "H" in x or "MASC" in x else 0
                )
                df_temp["suma_mujeres"] = s_sex.apply(
                    lambda x: 1 if "M" in x or "FEM" in x or "F" in x else 0
                )
                df_temp["suma_total"] = 1.0

            # CASO B: Base de datos agregada / resumida por filas
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

            # Factores de conversión
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
