# Analizador Comercial

Aplicación web en Streamlit para cargar, validar, depurar, consultar, analizar, visualizar y exportar bases de datos comerciales sin enviar información a servicios externos.

## Objetivo

Facilitar el trabajo cotidiano de una Analista Comercial mediante un flujo sencillo de revisión de calidad, limpieza no destructiva, filtros, indicadores comerciales, gráficos interactivos y exportación.

## Funcionalidades

- Carga de archivos CSV y XLSX en memoria.
- Selección de hoja para libros de Excel.
- Detección automática del separador y prueba de codificaciones comunes para CSV.
- Vista previa, dimensiones, tipos y memoria aproximada.
- Validación de duplicados, valores nulos, columnas vacías, espacios y tipos probables.
- Indicador porcentual de calidad.
- Limpieza con vista previa, aplicación, deshacer y restablecimiento.
- Filtros combinables para variables numéricas, categóricas, fechas y texto.
- Indicadores de ventas, operaciones y clientes.
- Tendencia mensual y análisis por clientes, productos, vendedores, canales, regiones y estados.
- Gráficos Plotly: histogramas, barras, series temporales, faltantes y correlaciones.
- Exportación en CSV y Excel, con hojas `Datos` y `Resumen`.
- Descarga del reporte de calidad y del historial de limpieza.

## Requisitos previos

- Python 3.11 o superior.
- `pip` disponible.
- Un navegador web moderno.

## Estructura del proyecto

```text
.
├── app.py
├── requirements.txt
└── README.md
```

## Instalación

Se recomienda usar un entorno virtual:

```bash
python -m venv .venv
```

Activación en Windows:

```bash
.venv\Scripts\activate
```

Activación en macOS o Linux:

```bash
source .venv/bin/activate
```

Instale las dependencias:

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
streamlit run app.py
```

Streamlit mostrará la dirección local, normalmente `http://localhost:8501`.

## Ejemplo de uso

1. Abra **Carga de archivos** y seleccione un CSV o XLSX.
2. Si es Excel, elija la hoja.
3. Revise el diagnóstico en **Validación**.
4. Configure acciones en **Limpieza**, revise la vista previa y aplique los cambios.
5. Use **Filtros** para reducir los registros.
6. Configure las columnas en **Análisis Comercial**.
7. Explore gráficos en **Visualizaciones**.
8. Descargue resultados desde **Exportación**.

## Formatos admitidos

- `.csv`
- `.xlsx`

El límite predeterminado es de 50 MB y puede modificarse mediante `MAX_FILE_MB` en `app.py`.

## Recomendaciones para los datos

- Utilice una sola fila de encabezados.
- Evite celdas combinadas y subtotales dentro de la tabla.
- Mantenga un tipo de dato consistente por columna.
- Use una fila por operación o registro.
- Incluya nombres descriptivos para fecha, venta, cliente, producto, vendedor, canal, región y estado.
- Use fechas reales de Excel o formatos de fecha consistentes.

## Métricas comerciales

Según las columnas configuradas, la aplicación calcula:

- **Total de ventas:** suma de los valores numéricos válidos.
- **Operaciones:** cantidad de valores de venta válidos.
- **Promedio por operación:** total dividido entre operaciones válidas.
- **Clientes únicos:** número de clientes distintos, excluyendo nulos.
- **Venta promedio por cliente:** total dividido entre clientes únicos.
- **Venta máxima:** mayor valor válido de venta.
- **Tendencia mensual:** suma de ventas agrupada por mes.
- **Resultados por categoría:** suma de ventas por cliente, producto, vendedor, canal, región o estado.

Las columnas no numéricas seleccionadas como ventas se convierten con tolerancia. Los valores que no puedan convertirse se excluyen del cálculo.

## Indicador de calidad

El indicador comienza en 100 y aplica estas penalizaciones:

- Hasta 40 puntos por proporción de celdas nulas.
- Hasta 30 puntos por proporción de filas duplicadas.
- Hasta 30 puntos por columnas completamente vacías, a razón de 2 puntos por columna.

Es una guía operativa, no sustituye reglas de calidad específicas del negocio.

## Privacidad y seguridad

- Los archivos se procesan en memoria.
- La aplicación no usa APIs externas ni servicios pagos.
- No incorpora contraseñas, tokens ni credenciales.
- No guarda archivos permanentemente en el servidor.
- Antes de cargar datos personales, comerciales o confidenciales, valide las políticas internas aplicables.

Para uso empresarial real se recomienda incorporar autenticación corporativa, autorización por roles, cifrado, auditoría, límites de carga, políticas de retención y despliegue en un entorno autorizado.

## Solución de problemas

### El CSV no carga

- Confirme que sea un CSV válido.
- Revise que tenga una estructura tabular consistente.
- Guárdelo como UTF-8 si su codificación no es reconocida.
- Verifique que no supere el límite configurado.

### El Excel no carga

- Confirme que el archivo sea `.xlsx`.
- Abra y vuelva a guardar el libro para descartar corrupción.
- Elimine protecciones o estructuras especiales si impiden la lectura.

### Las métricas no aparecen

- Seleccione una columna de ventas.
- Verifique que contenga números o textos convertibles a número.
- Configure las columnas opcionales necesarias para cada análisis.

### El proceso consume demasiada memoria

- Reduzca el archivo antes de cargarlo.
- Elimine columnas innecesarias.
- Use CSV para tablas grandes.
- Disminuya `MAX_FILE_MB` en equipos con recursos limitados.

## Despliegue opcional en Streamlit Community Cloud

1. Cree un repositorio con estos tres archivos.
2. Ingrese a [Streamlit Community Cloud](https://share.streamlit.io/).
3. Seleccione el repositorio, la rama y `app.py` como archivo principal.
4. Despliegue la aplicación.

No use Community Cloud con información confidencial sin aprobación formal. Para entornos empresariales, considere infraestructura privada y controles corporativos.

## Limitaciones conocidas

- Las detecciones semánticas se basan en heurísticas.
- El indicador de calidad no incorpora reglas particulares del negocio.
- No incluye autenticación ni control de acceso.
- No guarda sesiones de forma permanente.
- El rendimiento depende de la memoria disponible.
- No admite el formato heredado `.xls`.

## Mejoras futuras

- Reglas configurables por columna.
- Validación de documentos, teléfonos y correos con reglas locales.
- Catálogos maestros para homologación.
- Comparación entre periodos más avanzada.
- Segmentación de clientes y productos.
- Registro persistente y auditable de transformaciones.
- Autenticación corporativa y perfiles de acceso.
- Pruebas automatizadas y empaquetado con contenedores.
