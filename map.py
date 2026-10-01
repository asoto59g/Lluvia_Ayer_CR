# -*- coding: utf-8 -*-
"""Map generation for Lluvia Ayer CR.

Esta versión está preparada para ejecutarse en Streamlit Cloud.
- Detecta automáticamente la columna de fechas (incluye la columna "X").
- Muestra un mensaje de arranque y captura global de errores.
- Usa `st.spinner` y `st.empty()` para indicar progreso mientras se escribe
  el archivo HTML del mapa.
- Ignora archivos temporales mediante `.gitignore`.
"""

import os
import time
import logging
import base64
from datetime import datetime

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
import matplotlib.pyplot as plt

import streamlit as st

# ----------------------------------------------------------------------
# Configuración básica
# ----------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Utilidades para manejo de datos
# ----------------------------------------------------------------------
def _clean_value(val):
    """Limpia valores de lluvia que pueden venir como strings.
    Devuelve un float o NaN.
    """
    if pd.isna(val):
        return float('nan')
    if isinstance(val, str):
        val = val.replace(',', '.')
        try:
            return float(val)
        except ValueError:
            return float('nan')
    return float(val)

def _detect_date_column(df: pd.DataFrame) -> str:
    """Devuelve el nombre de la columna que contiene fechas.
    Busca la columna que, al intentar parsearla con `pd.to_datetime`, genera
    la mayor cantidad de valores no nulos. También acepta la columna "X" que
    contiene fechas reales.
    """
    best_col = None
    best_count = -1
    for col in df.columns:
        try:
            parsed = pd.to_datetime(df[col], errors='coerce')
            cnt = parsed.notna().sum()
            if cnt > best_count:
                best_count = cnt
                best_col = col
        except Exception:
            continue
    if best_col is None:
        raise ValueError('No se encontró columna de fechas en el CSV')
    LOGGER.info(f"Columna de fechas detectada: {best_col} (valores válidos: {best_count})")
    return best_col

# ----------------------------------------------------------------------
# Helper: robust CSV reader (UTF‑8 → latin‑1 fallback)
def _read_csv_robust(path: str) -> pd.DataFrame:
    """Lee un CSV intentando UTF‑8 y, si falla, vuelve a intentar con latin‑1.
    Devuelve un DataFrame con todas las columnas como string."""
    try:
        return pd.read_csv(path, dtype=str, encoding='utf-8')
    except UnicodeDecodeError:
        return pd.read_csv(path, dtype=str, encoding='latin-1')

# ----------------------------------------------------------------------
# Generación del mapa Thiessen
# ----------------------------------------------------------------------
def generar_mapa_con_thiessen(csv_path: str, fecha: str, output_html: str = "mapa_lluvia.html"):
    """Genera un mapa de polígonos Thiessen a partir de los datos de lluvia.
    - `csv_path`: ruta al CSV con los datos.
    - `fecha`: string con la fecha a filtrar (formato ISO o equivalente).
    - `output_html`: nombre del archivo HTML resultante.
    """
    df = _read_csv_robust(csv_path)
    # Detectar la columna de fechas y normalizar (solo fecha, sin hora)
    date_col = _detect_date_column(df)
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce').dt.normalize()
    # Normalizar la fecha solicitada
    target_date = pd.to_datetime(fecha).normalize()
    # Filtrar los registros que coinciden exactamente en la fecha
    df_filtrado = df[df[date_col] == target_date]
    if df_filtrado.empty:
        raise ValueError(f"No hay datos para la fecha {fecha}")
    # Convertir coordenadas a puntos geográficos
    # Convertir coordenadas a puntos geográficos usando columnas existentes
    df_filtrado["lon"] = pd.to_numeric(df_filtrado["Longitud_Decimal"], errors='coerce')
    df_filtrado["lat"] = pd.to_numeric(df_filtrado["Latitud_Decimal"], errors='coerce')
    # Eliminar filas donde lon o lat sean NaN para evitar errores al crear geometrías
    df_filtrado = df_filtrado.dropna(subset=["lon", "lat"]).reset_index(drop=True)
    gdf = gpd.GeoDataFrame(
        df_filtrado,
        geometry=gpd.points_from_xy(df_filtrado["lon"], df_filtrado["lat"]),
    )
    # Establecer CRS explícitamente (EPSG:4326)
    gdf.set_crs(epsg=4326, inplace=True)
    # Crear polígonos Thiessen (Voronoi) en proyección plana
    gdf = gdf.to_crs(epsg=3857)
    points = gdf.geometry.unary_union
    # Robust Voronoi creation with handling for degenerate cases
    from scipy.spatial import Voronoi, QhullError
    import numpy as np
    from shapely.geometry import Point, MultiPoint
    coords = np.array([(p.x, p.y) for p in gdf.geometry])
    # Si hay menos de 3 puntos, no se puede construir un Voronoi significativo
    if len(coords) < 3:
        # Usar un pequeño buffer alrededor de cada punto como polígono fallback
        polygons = [geom.buffer(1) for geom in gdf.geometry]
    else:
        try:
            vor = Voronoi(coords)
        except QhullError:
            # Falla de Qhull (puntos colineales, coincidencias, etc.)
            # Utilizar el convex hull de todos los puntos como polígono único
            hull = MultiPoint([geom for geom in gdf.geometry]).convex_hull
            polygons = [hull] * len(gdf)
        else:
            # Construir polígonos a partir de los vértices del Voronoi
            polygons = []
            for region_idx in vor.point_region:
                vertices = vor.regions[region_idx]
                if -1 in vertices or len(vertices) == 0:
                    # Región infinita: crear un gran buffer alrededor del punto
                    point_coords = vor.points[region_idx]
                    polygons.append(Point(point_coords).buffer(1e6))
                    continue
                poly_coords = [vor.vertices[i] for i in vertices]
                polygons.append(Polygon(poly_coords))
    gdf["thiessen"] = polygons
    gdf = gdf.set_geometry("thiessen")
    # Volver a EPSG:4326 para el HTML
    gdf = gdf.to_crs(epsg=4326)
    # Guardar HTML sencillo con Leaflet
    html_template = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Mapa Thiessen</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
</head>
<body>
<div id="map" style="width: 100%; height: 800px;"></div>
<script>
  var map = L.map('map').setView([0,0], 2);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);
  var geojson = %s;
  L.geoJSON(geojson).addTo(map);
</script>
</body>
</html>
"""
    # Convertir a GeoJSON
    geojson_str = gdf.drop(columns=["geometry"]).to_json()
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_template % geojson_str)

# ----------------------------------------------------------------------
# UI de Streamlit
# ----------------------------------------------------------------------
def run_streamlit():
    st.set_page_config(page_title="Mapa de Lluvia – Thiessen", layout="wide")
    st.title("Mapa de Lluvia – Thiessen")
    st.write("🚀 La aplicación se ha iniciado correctamente.")

    # Determinar CSV a usar (prefiere historial si existe)
    csv_path = "histlluviadiaria.csv" if os.path.exists("histlluviadiaria.csv") else "lluviadiaria.csv"
    if not os.path.exists(csv_path):
        st.error(f"No se encontró ningún CSV de datos en el directorio ({csv_path}).")
        return

    # Cargar fechas disponibles
    df = _read_csv_robust(csv_path)
    date_col = _detect_date_column(df)
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    fechas = sorted(df[date_col].dropna().dt.strftime("%Y-%m-%d").unique())
    if not fechas:
        st.warning("No se encontraron fechas válidas en el CSV.")
        return

    fecha_seleccionada = st.selectbox(
        "Selecciona la fecha del mapa (se mostrará el día seleccionado)",
        options=fechas,
        index=len(fechas) - 1,
    )

    # Helper para generar y mostrar el mapa
    def _generar_y_mostrar():
        try:
            generar_mapa_con_thiessen(csv_path=csv_path, fecha=fecha_seleccionada)
            st.success("✅ Mapa generado con éxito.")
        except Exception as e:
            st.error(f"❗️ Error al generar el mapa: {e}")
            return

        # Spinner y placeholder mientras esperamos el archivo
        placeholder = st.empty()
        with st.spinner("⏳ Generando mapa …"):
            max_wait = 30  # segundos
            waited = 0
            while waited < max_wait:
                if os.path.exists("mapa_lluvia.html"):
                    break
                placeholder.info("Esperando a que el archivo HTML se guarde …")
                time.sleep(1)
                waited += 1

        if not os.path.exists("mapa_lluvia.html"):
            st.error("⏰ El archivo del mapa no se creó a tiempo.")
            return
        try:
            with open("mapa_lluvia.html", "r", encoding="utf-8") as f:
                html_content = f.read()
            st.components.v1.html(html_content, height=800, scrolling=True)
        except Exception as e:
            st.error(f"❗️ Error al cargar el mapa generado: {e}")

    # Generar automáticamente con la fecha predeterminada
    _generar_y_mostrar()

    # Botón para volver a generar si el usuario cambia la fecha
    if st.button("🔄 Ejecutar con fecha seleccionada"):
        _generar_y_mostrar()

# ----------------------------------------------------------------------
# Entrada principal
# ----------------------------------------------------------------------
if __name__ == "__main__":
    try:
        run_streamlit()
    except Exception as exc:
        st.error("❗️ Se produjo un error inesperado en la aplicación.")
        st.code(str(exc))

def _read_csv_robust(path: str) -> pd.DataFrame:
    """Lee un CSV intentando UTF‑8 y, si falla, vuelve a intentar con latin‑1.
    Devuelve un DataFrame con todas las columnas como string.
    """
    try:
        return pd.read_csv(path, dtype=str, encoding='utf-8')
    except UnicodeDecodeError:
        return pd.read_csv(path, dtype=str, encoding='latin-1')
