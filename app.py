import re
import unicodedata
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

MAX_FILE_MB = 50

st.set_page_config(
    page_title="Analizador Comercial",
    page_icon="📊",
    layout="wide"
)

st.markdown("""
<style>
.block-container {padding-top: 1rem;}
.metric-card {
    padding:10px;border-radius:10px;
    border:1px solid #ddd;background:#fafafa;
}
</style>
""", unsafe_allow_html=True)


def inicializar_estado() -> None:
    """Inicializa las variables persistentes de la aplicación."""
    defaults = {
        "df_original": None,
        "df_trabajo": None,
        "df_filtrado": None,
        "archivo": None,
        "historial": [],
        "config_cols": {},
    }
    for clave, valor in defaults.items():
        if clave not in st.session_state:
            st.session_state[clave] = valor


def normalizar_nombre(texto: str) -> str:
    """Normaliza un nombre para usarlo como encabezado de columna."""
    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^\w\s]", "", texto)
    return re.sub(r"\s+", "_", texto)


def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve una copia con nombres de columnas normalizados y únicos."""
    nuevo = df.copy()
    nombres = []
    usados = {}
    for columna in nuevo.columns:
        base = normalizar_nombre(columna) or "columna"
        usados[base] = usados.get(base, 0) + 1
        nombres.append(base if usados[base] == 1 else f"{base}_{usados[base]}")
    nuevo.columns = nombres
    return nuevo


@st.cache_data(show_spinner=False)
def leer_csv(contenido: bytes) -> pd.DataFrame:
    """Lee un CSV desde memoria, probando codificaciones comunes."""
    ultimo_error = None
    for codificacion in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return pd.read_csv(BytesIO(contenido), sep=None, engine="python", encoding=codificacion)
        except (UnicodeDecodeError, pd.errors.ParserError) as error:
            ultimo_error = error
    raise ValueError("No fue posible detectar la codificación o el separador del CSV.") from ultimo_error


@st.cache_data(show_spinner=False)
def obtener_hojas_excel(contenido: bytes) -> list[str]:
    """Obtiene las hojas disponibles en un libro XLSX."""
    return pd.ExcelFile(BytesIO(contenido), engine="openpyxl").sheet_names


@st.cache_data(show_spinner=False)
def leer_excel(contenido: bytes, hoja: str) -> pd.DataFrame:
    """Lee una hoja de Excel desde memoria."""
    return pd.read_excel(BytesIO(contenido), sheet_name=hoja, engine="openpyxl")


def detectar_tipos(df: pd.DataFrame) -> dict[str, str]:
    """Detecta tipos semánticos probables usando heurísticas simples."""
    resultado = {}
    for columna in df.columns:
        serie = df[columna].dropna()
        texto = serie.astype(str).str.strip()
        if serie.empty:
            resultado[columna] = "vacía"
        elif pd.api.types.is_datetime64_any_dtype(serie):
            resultado[columna] = "fecha"
        elif pd.api.types.is_numeric_dtype(serie):
            resultado[columna] = "numérico"
        elif texto.str.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$").mean() >= 0.7:
            resultado[columna] = "correo"
        elif texto.str.replace(r"[\s()+-]", "", regex=True).str.match(r"^\d{7,15}$").mean() >= 0.7:
            resultado[columna] = "teléfono"
        else:
            fechas = pd.to_datetime(texto, errors="coerce", dayfirst=True)
            resultado[columna] = "fecha probable" if fechas.notna().mean() >= 0.8 else "texto"
    return resultado


def calidad_datos(df: pd.DataFrame) -> dict[str, float | int]:
    """Calcula indicadores básicos de calidad de datos."""
    filas, columnas = df.shape
    duplicados = int(df.duplicated().sum())
    nulos = int(df.isna().sum().sum())
    columnas_vacias = int(df.isna().all().sum())
    celdas = max(1, filas * columnas)
    penalizacion_nulos = min(40.0, nulos / celdas * 100)
    penalizacion_duplicados = min(30.0, duplicados / max(1, filas) * 100)
    penalizacion_columnas = min(30.0, columnas_vacias * 2.0)
    calidad = max(0.0, round(100 - penalizacion_nulos - penalizacion_duplicados - penalizacion_columnas, 2))
    return {
        "duplicados": duplicados,
        "nulos": nulos,
        "columnas_vacias": columnas_vacias,
        "calidad": calidad,
    }


def aplicar_transformaciones(df: pd.DataFrame, opciones: dict) -> pd.DataFrame:
    """Aplica las transformaciones seleccionadas sobre una copia."""
    nuevo = df.copy()
    if opciones.get("eliminar_duplicados"):
        nuevo = nuevo.drop_duplicates()
    if opciones.get("filas_vacias"):
        nuevo = nuevo.dropna(how="all")
    if opciones.get("columnas_vacias"):
        nuevo = nuevo.dropna(axis=1, how="all")
    if opciones.get("normalizar_columnas"):
        nuevo = normalizar_columnas(nuevo)
    for columna in opciones.get("trim", []):
        if columna in nuevo.columns:
            mascara = nuevo[columna].notna()
            nuevo.loc[mascara, columna] = nuevo.loc[mascara, columna].astype(str).str.strip()
    for accion, metodo in (("mayusculas", "upper"), ("minusculas", "lower"), ("titulo", "title")):
        for columna in opciones.get(accion, []):
            if columna in nuevo.columns:
                mascara = nuevo[columna].notna()
                transformador = getattr(nuevo.loc[mascara, columna].astype(str).str, metodo)
                nuevo.loc[mascara, columna] = transformador()
    return nuevo


def exportar_excel(df: pd.DataFrame, resumen: pd.DataFrame) -> bytes:
    """Genera un libro Excel en memoria con hojas Datos y Resumen."""
    salida = BytesIO()
    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Datos", index=False)
        resumen.to_excel(writer, sheet_name="Resumen", index=False)
    return salida.getvalue()


def crear_grafico_faltantes(df: pd.DataFrame):
    """Crea un gráfico de valores faltantes por columna."""
    faltantes = df.isna().sum().rename("Faltantes").reset_index(names="Columna")
    faltantes = faltantes[faltantes["Faltantes"] > 0]
    if faltantes.empty:
        return None
    return px.bar(faltantes, x="Columna", y="Faltantes", title="Valores faltantes por columna")


def nombre_descarga(nombre: str, sufijo: str) -> str:
    """Construye un nombre seguro para archivos descargables."""
    base = normalizar_nombre(Path(nombre).stem) if nombre else "datos"
    return f"{base}_{sufijo}"


inicializar_estado()

menu = st.sidebar.radio(
    "Navegación",
    ["Inicio", "Carga de archivos", "Validación", "Limpieza", "Filtros", "Análisis Comercial", "Visualizaciones", "Exportación"],
)
st.sidebar.info("Valide las políticas internas antes de cargar información personal, comercial o confidencial.")

if menu == "Inicio":
    st.title("📊 Analizador Comercial")
    st.write("Aplicación para cargar, validar, depurar, consultar y analizar bases de datos comerciales.")
    if st.session_state.df_trabajo is None:
        st.info("Comience en 'Carga de archivos' y seleccione un archivo CSV o XLSX.")
    else:
        df = st.session_state.df_trabajo
        perfil = calidad_datos(df)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Registros", f"{len(df):,}")
        c2.metric("Columnas", len(df.columns))
        c3.metric("Duplicados", perfil["duplicados"])
        c4.metric("Filas con faltantes", int(df.isna().any(axis=1).sum()))

elif menu == "Carga de archivos":
    st.header("Carga de archivos")
    archivo = st.file_uploader("Seleccione un archivo CSV o XLSX", type=["csv", "xlsx"])
    if archivo is not None:
        if archivo.size > MAX_FILE_MB * 1024 * 1024:
            st.error(f"El archivo supera el límite configurable de {MAX_FILE_MB} MB.")
        else:
            contenido = archivo.getvalue()
            try:
                if archivo.name.lower().endswith(".csv"):
                    df = leer_csv(contenido)
                    hoja = None
                else:
                    hojas = obtener_hojas_excel(contenido)
                    hoja = st.selectbox("Hoja de Excel", hojas)
                    df = leer_excel(contenido, hoja)
                if df.empty and len(df.columns) == 0:
                    st.warning("El archivo no contiene una tabla reconocible.")
                else:
                    identificador = f"{archivo.name}:{hoja or ''}:{archivo.size}"
                    if st.session_state.get("archivo_id") != identificador:
                        st.session_state.df_original = df.copy()
                        st.session_state.df_trabajo = df.copy()
                        st.session_state.df_filtrado = df.copy()
                        st.session_state.archivo = archivo.name
                        st.session_state.archivo_id = identificador
                        st.session_state.historial = []
                        st.session_state.pila_deshacer = []
                    st.success("Archivo cargado correctamente.")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Archivo", archivo.name)
                    c2.metric("Filas", f"{len(df):,}")
                    c3.metric("Columnas", len(df.columns))
                    c4.metric("Memoria aproximada", f"{df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
                    st.dataframe(df.head(20), use_container_width=True)
                    with st.expander("Columnas y tipos detectados"):
                        st.dataframe(pd.DataFrame({"Columna": df.columns, "Tipo pandas": df.dtypes.astype(str).values}), hide_index=True)
            except (ValueError, UnicodeDecodeError, pd.errors.ParserError, OSError) as error:
                st.error(f"No fue posible leer el archivo: {str(error)[:180]}")
            except Exception:
                st.error("Ocurrió un error inesperado al procesar el archivo. Verifique que no esté dañado.")

elif menu == "Validación":
    if st.session_state.df_trabajo is None:
        st.warning("No existe información cargada.")
    else:
        df = st.session_state.df_trabajo
        perfil = calidad_datos(df)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Calidad", f"{perfil['calidad']:.1f}%")
        c2.metric("Duplicados", perfil["duplicados"])
        c3.metric("Celdas vacías", perfil["nulos"])
        c4.metric("Columnas vacías", perfil["columnas_vacias"])
        st.caption("La calidad parte de 100 puntos y descuenta hasta 40 por celdas nulas, 30 por filas duplicadas y 30 por columnas completamente vacías.")
        tipos = detectar_tipos(df)
        st.dataframe(pd.DataFrame(tipos.items(), columns=["Columna", "Tipo probable"]), hide_index=True, use_container_width=True)
        espacios = []
        for columna in df.select_dtypes(include=["object", "string"]).columns:
            serie = df[columna].dropna().astype(str)
            espacios.append({"Columna": columna, "Textos con espacios externos": int((serie != serie.str.strip()).sum())})
        if espacios:
            st.subheader("Posibles inconsistencias de texto")
            st.dataframe(pd.DataFrame(espacios), hide_index=True, use_container_width=True)
        figura = crear_grafico_faltantes(df)
        if figura:
            st.plotly_chart(figura, use_container_width=True)
        else:
            st.success("No se detectaron valores faltantes.")

elif menu == "Limpieza":
    if st.session_state.df_trabajo is None:
        st.warning("No existe información cargada.")
    else:
        df = st.session_state.df_trabajo
        texto_cols = list(df.select_dtypes(include=["object", "string"]).columns)
        st.subheader("Seleccione las transformaciones")
        c1, c2 = st.columns(2)
        eliminar_duplicados = c1.checkbox("Eliminar duplicados")
        filas_vacias = c1.checkbox("Eliminar filas completamente vacías")
        columnas_vacias = c1.checkbox("Eliminar columnas completamente vacías")
        normalizar_cols = c1.checkbox("Normalizar nombres de columnas")
        trim = c2.multiselect("Quitar espacios externos", texto_cols)
        mayusculas = c2.multiselect("Convertir a mayúsculas", texto_cols)
        minusculas = c2.multiselect("Convertir a minúsculas", texto_cols)
        titulo = c2.multiselect("Convertir a formato título", texto_cols)
        opciones = {
            "eliminar_duplicados": eliminar_duplicados,
            "filas_vacias": filas_vacias,
            "columnas_vacias": columnas_vacias,
            "normalizar_columnas": normalizar_cols,
            "trim": trim,
            "mayusculas": mayusculas,
            "minusculas": minusculas,
            "titulo": titulo,
        }
        preview = aplicar_transformaciones(df, opciones)
        st.subheader("Vista previa del resultado")
        st.dataframe(preview.head(50), use_container_width=True)
        c1, c2, c3 = st.columns(3)
        if c1.button("Aplicar cambios", type="primary"):
            st.session_state.setdefault("pila_deshacer", []).append(df.copy())
            st.session_state.df_trabajo = preview.copy()
            st.session_state.df_filtrado = preview.copy()
            st.session_state.historial.append({"Paso": len(st.session_state.historial) + 1, "Transformaciones": ", ".join(k for k, v in opciones.items() if v) or "Sin cambios", "Filas resultantes": len(preview)})
            st.success("Cambios aplicados.")
            st.rerun()
        if c2.button("Deshacer el último cambio", disabled=not st.session_state.get("pila_deshacer")):
            st.session_state.df_trabajo = st.session_state.pila_deshacer.pop()
            if st.session_state.historial:
                st.session_state.historial.pop()
            st.session_state.df_filtrado = st.session_state.df_trabajo.copy()
            st.rerun()
        if c3.button("Restablecer la base original"):
            st.session_state.df_trabajo = st.session_state.df_original.copy()
            st.session_state.df_filtrado = st.session_state.df_original.copy()
            st.session_state.historial = []
            st.session_state.pila_deshacer = []
            st.rerun()

elif menu == "Filtros":
    if st.session_state.df_trabajo is None:
        st.warning("No existe información cargada.")
    else:
        base = st.session_state.df_trabajo
        seleccionadas = st.multiselect("Columnas que desea filtrar", list(base.columns))
        filtrado = base.copy()
        for columna in seleccionadas:
            serie = base[columna]
            if pd.api.types.is_numeric_dtype(serie) and serie.notna().any():
                minimo, maximo = float(serie.min()), float(serie.max())
                if minimo < maximo:
                    rango = st.slider(f"Rango: {columna}", minimo, maximo, (minimo, maximo))
                    filtrado = filtrado[pd.to_numeric(filtrado[columna], errors="coerce").between(*rango)]
            elif pd.api.types.is_datetime64_any_dtype(serie):
                fechas = serie.dropna()
                rango = st.date_input(f"Rango de fechas: {columna}", value=(fechas.min().date(), fechas.max().date()))
                if len(rango) == 2:
                    valores = pd.to_datetime(filtrado[columna], errors="coerce")
                    filtrado = filtrado[valores.between(pd.Timestamp(rango[0]), pd.Timestamp(rango[1]) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1))]
            else:
                unicos = serie.dropna().astype(str).unique()
                if len(unicos) <= 100:
                    valores = st.multiselect(f"Valores: {columna}", sorted(unicos.tolist()))
                    if valores:
                        filtrado = filtrado[filtrado[columna].astype(str).isin(valores)]
                else:
                    busqueda = st.text_input(f"Buscar texto en {columna}")
                    if busqueda:
                        filtrado = filtrado[filtrado[columna].astype(str).str.contains(busqueda, case=False, na=False, regex=False)]
        ordenar = st.selectbox("Ordenar por", [""] + list(filtrado.columns))
        if ordenar:
            ascendente = st.toggle("Orden ascendente", value=True)
            filtrado = filtrado.sort_values(ordenar, ascending=ascendente, na_position="last")
        st.session_state.df_filtrado = filtrado.copy()
        st.metric("Registros resultantes", f"{len(filtrado):,}")
        st.dataframe(filtrado, use_container_width=True)

elif menu == "Análisis Comercial":
    if st.session_state.df_trabajo is None:
        st.warning("No existe información cargada.")
    else:
        df = st.session_state.df_filtrado if st.session_state.df_filtrado is not None else st.session_state.df_trabajo
        columnas = [""] + list(df.columns)
        c1, c2, c3 = st.columns(3)
        fecha = c1.selectbox("Fecha", columnas)
        venta = c1.selectbox("Ventas o valor", columnas)
        cantidad = c1.selectbox("Cantidad", columnas)
        cliente = c2.selectbox("Cliente", columnas)
        producto = c2.selectbox("Producto", columnas)
        vendedor = c2.selectbox("Asesor o vendedor", columnas)
        canal = c3.selectbox("Canal", columnas)
        region = c3.selectbox("Ciudad, región o zona", columnas)
        estado = c3.selectbox("Estado", columnas)
        st.session_state.config_cols = {"fecha": fecha, "venta": venta, "cantidad": cantidad, "cliente": cliente, "producto": producto, "vendedor": vendedor, "canal": canal, "region": region, "estado": estado}
        if not venta:
            st.info("Seleccione la columna de ventas para calcular indicadores monetarios.")
        else:
            valores = pd.to_numeric(df[venta], errors="coerce")
            validos = valores.dropna()
            if validos.empty:
                st.warning("La columna seleccionada no contiene valores numéricos válidos.")
            else:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total de ventas", f"$ {validos.sum():,.2f}")
                c2.metric("Operaciones", f"{validos.count():,}")
                c3.metric("Promedio por operación", f"$ {validos.mean():,.2f}")
                c4.metric("Venta máxima", f"$ {validos.max():,.2f}")
                if cliente:
                    clientes = df[cliente].nunique(dropna=True)
                    a, b = st.columns(2)
                    a.metric("Clientes únicos", clientes)
                    b.metric("Venta promedio por cliente", f"$ {validos.sum() / max(1, clientes):,.2f}")
                if fecha:
                    temporal = pd.DataFrame({"Fecha": pd.to_datetime(df[fecha], errors="coerce"), "Ventas": valores}).dropna()
                    if not temporal.empty:
                        mensual = temporal.set_index("Fecha").resample("MS")["Ventas"].sum().reset_index()
                        st.plotly_chart(px.line(mensual, x="Fecha", y="Ventas", markers=True, title="Tendencia mensual de ventas"), use_container_width=True)
                for etiqueta, columna in (("Clientes", cliente), ("Productos", producto), ("Vendedores", vendedor), ("Canales", canal), ("Regiones", region), ("Estados", estado)):
                    if columna:
                        agrupado = pd.DataFrame({columna: df[columna], "Ventas": valores}).groupby(columna, dropna=False)["Ventas"].sum().nlargest(10).reset_index()
                        if not agrupado.empty:
                            st.plotly_chart(px.bar(agrupado, x=columna, y="Ventas", title=f"Ventas por {etiqueta.lower()}"), use_container_width=True)

elif menu == "Visualizaciones":
    if st.session_state.df_trabajo is None:
        st.warning("No existe información cargada.")
    else:
        df = st.session_state.df_filtrado if st.session_state.df_filtrado is not None else st.session_state.df_trabajo
        tipo = st.selectbox("Tipo de visualización", ["Histograma", "Barras", "Serie temporal", "Correlaciones", "Valores faltantes"])
        numericas = list(df.select_dtypes(include="number").columns)
        if tipo == "Histograma":
            if numericas:
                x = st.selectbox("Variable numérica", numericas)
                st.plotly_chart(px.histogram(df, x=x, title=f"Distribución de {x}"), use_container_width=True)
            else:
                st.info("No hay columnas numéricas.")
        elif tipo == "Barras":
            categoria = st.selectbox("Categoría", list(df.columns))
            valor = st.selectbox("Valor", numericas)
            if valor:
                datos = df.groupby(categoria, dropna=False)[valor].sum().nlargest(20).reset_index()
                st.plotly_chart(px.bar(datos, x=categoria, y=valor, title=f"{valor} por {categoria}"), use_container_width=True)
        elif tipo == "Serie temporal":
            fecha_col = st.selectbox("Fecha", list(df.columns))
            valor = st.selectbox("Valor", numericas)
            if valor:
                datos = pd.DataFrame({"Fecha": pd.to_datetime(df[fecha_col], errors="coerce"), "Valor": pd.to_numeric(df[valor], errors="coerce")}).dropna().sort_values("Fecha")
                if datos.empty:
                    st.info("No hay datos suficientes para la serie temporal.")
                else:
                    st.plotly_chart(px.line(datos, x="Fecha", y="Valor", title=f"Evolución de {valor}"), use_container_width=True)
        elif tipo == "Correlaciones":
            if len(numericas) >= 2:
                corr = df[numericas].corr(numeric_only=True)
                st.plotly_chart(px.imshow(corr, text_auto=".2f", aspect="auto", title="Mapa de correlaciones", color_continuous_scale="RdBu_r", zmin=-1, zmax=1), use_container_width=True)
            else:
                st.info("Se requieren al menos dos columnas numéricas.")
        else:
            figura = crear_grafico_faltantes(df)
            if figura:
                st.plotly_chart(figura, use_container_width=True)
            else:
                st.success("No se detectaron valores faltantes.")

elif menu == "Exportación":
    if st.session_state.df_trabajo is None:
        st.warning("No existe información cargada.")
    else:
        limpio = st.session_state.df_trabajo
        filtrado = st.session_state.df_filtrado if st.session_state.df_filtrado is not None else limpio
        perfil = calidad_datos(limpio)
        resumen = pd.DataFrame([{"Archivo": st.session_state.archivo, "Registros": len(limpio), "Columnas": len(limpio.columns), "Duplicados": perfil["duplicados"], "Celdas vacías": perfil["nulos"], "Calidad (%)": perfil["calidad"]}])
        c1, c2 = st.columns(2)
        c1.download_button("Descargar base limpia en CSV", limpio.to_csv(index=False).encode("utf-8-sig"), nombre_descarga(st.session_state.archivo, "limpio.csv"), "text/csv")
        c1.download_button("Descargar base limpia en Excel", exportar_excel(limpio, resumen), nombre_descarga(st.session_state.archivo, "limpio.xlsx"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        c2.download_button("Descargar datos filtrados en CSV", filtrado.to_csv(index=False).encode("utf-8-sig"), nombre_descarga(st.session_state.archivo, "filtrado.csv"), "text/csv")
        c2.download_button("Descargar datos filtrados en Excel", exportar_excel(filtrado, resumen), nombre_descarga(st.session_state.archivo, "filtrado.xlsx"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        reporte_calidad = pd.DataFrame({"Columna": limpio.columns, "Valores faltantes": limpio.isna().sum().values, "Porcentaje faltante": (limpio.isna().mean().values * 100).round(2), "Tipo": limpio.dtypes.astype(str).values})
        st.download_button("Descargar reporte de calidad", reporte_calidad.to_csv(index=False).encode("utf-8-sig"), "reporte_calidad.csv", "text/csv")
        historial = pd.DataFrame(st.session_state.historial)
        st.download_button("Descargar historial de limpieza", historial.to_csv(index=False).encode("utf-8-sig"), "historial_limpieza.csv", "text/csv", disabled=historial.empty)
