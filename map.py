# -*- coding: utf-8 -*-
"""map.py
Genera un mapa de polígonos Thiessen (Voronoi) a partir de datos de lluvia
para una fecha seleccionada y lo muestra con Streamlit.

Se ha reforzado para:
- Leer CSV con codificación UTF‑8 o latin‑1.
- Detectar automáticamente la columna de fechas y normalizarla.
- Filtrar filas sin coordenadas válidas y eliminar duplicados.
- Garantizar que el GeoDataFrame tenga CRS definido antes de cualquier transformación.
- Manejar casos degenerados de Voronoi (pocos puntos, colinealidad, Qhull errors).
- Proveer mensajes claros en la UI de Streamlit.
"""

import os
import logging
from datetime import datetime
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon, Point, MultiPoint
import streamlit as st
from scipy.spatial import Voronoi, QhullError

# ----------------------------------------------------------------------
# Configuración básica
# ----------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
def _read_csv_robust(path: str) -> pd.DataFrame:
    """Lee un CSV intentando UTF‑8 y, si falla, vuelve a latin‑1.
    Devuelve un DataFrame con todas las columnas como string.
    """
    try:
        return pd.read_csv(path, dtype=str, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(path, dtype=str, encoding="latin-1")

def _detect_date_column(df: pd.DataFrame) -> str:
    """Intenta inferir cuál columna contiene fechas.
    Busca la primera columna cuyo nombre contiene la palabra 'fecha' (ignora mayúsculas).
    Si no la encuentra, devuelve la primera columna que pueda convertirse a datetime.
    """
    for col in df.columns:
        if "fecha" in col.lower():
            return col
    # fallback: intento de parseo rápido
    for col in df.columns:
        try:
            pd.to_datetime(df[col].iloc[0])
            return col
        except Exception:
            continue
    raise ValueError("No se pudo detectar una columna de fechas en el CSV.")

# ----------------------------------------------------------------------
# Generación del mapa Thiessen
# ----------------------------------------------------------------------
def generar_mapa_con_thiessen(csv_path: str, fecha: str, output_html: str = "mapa_lluvia.html"):
    """Genera un mapa Thiessen para la *fecha* indicada.

    Args:
        csv_path: Ruta al archivo CSV con datos de lluvia.
        fecha: Fecha a filtrar (cualquier formato parseable por pandas).
        output_html: Nombre del archivo HTML resultante.
    """
    # 1️⃣ Lectura robusta del CSV
    df = _read_csv_robust(csv_path)

    # 2️⃣ Detección y normalización de la columna de fechas
    date_col = _detect_date_column(df)
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.normalize()
    target_date = pd.to_datetime(fecha).normalize()
    df_filtrado = df[df[date_col] == target_date]
    if df_filtrado.empty:
        raise ValueError(f"No hay datos para la fecha {fecha}")

    # 3️⃣ Conversión de coordenadas (columnas esperadas: Longitud_Decimal, Latitud_Decimal)
    df_filtrado["lon"] = pd.to_numeric(df_filtrado.get("Longitud_Decimal"), errors="coerce")
    df_filtrado["lat"] = pd.to_numeric(df_filtrado.get("Latitud_Decimal"), errors="coerce")
    # 4️⃣ Eliminar filas sin coordenadas válidas
    df_filtrado = df_filtrado.dropna(subset=["lon", "lat"]).reset_index(drop=True)

    # 5️⃣ Eliminar puntos duplicados (evita problemas en Qhull)
    df_filtrado = df_filtrado.drop_duplicates(subset=["lon", "lat"]).reset_index(drop=True)

    # 6️⃣ Crear GeoDataFrame y asignar CRS explícitamente
    gdf = gpd.GeoDataFrame(
        df_filtrado,
        geometry=gpd.points_from_xy(df_filtrado["lon"], df_filtrado["lat"]),
    )
    gdf.set_crs(epsg=4326, inplace=True)  # CRS obligatorio antes de cualquier transformación

    # 7️⃣ Proyección plana para Voronoi
    gdf = gdf.to_crs(epsg=3857)

    # 8️⃣ Preparar coordenadas y filtrar valores no finitos
    raw_coords = np.array([(p.x, p.y) for p in gdf.geometry])
    valid_mask = np.isfinite(raw_coords).all(axis=1)
    coords = raw_coords[valid_mask]
    # Eliminar duplicados que puedan haber quedado tras la proyección
    if len(coords) > 0:
        coords = np.unique(coords, axis=0)

    # 9️⃣ Construir polígonos Thiessen con manejo robusto de casos degenerados
    if len(coords) < 3:
        # Fallback: buffer pequeño alrededor de cada punto
        polygons = [geom.buffer(1) for geom in gdf.geometry.iloc[valid_mask].reset_index(drop=True)]
    else:
        try:
            vor = Voronoi(coords)
        except QhullError:
            # Convex hull como polígono único cuando Qhull falla
            hull = MultiPoint([geom for geom in gdf.geometry.iloc[valid_mask]]).convex_hull
            polygons = [hull] * len(gdf.iloc[valid_mask])
        else:
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

    # 10️⃣ Asignar polígonos al GeoDataFrame
    # Si se utilizó fallback, debemos asegurarnos de que el número de polígonos coincida con el número de puntos válidos
    if len(polygons) != len(gdf.iloc[valid_mask]):
        # rellenar con buffers mínimos para los puntos que faltan
        needed = len(gdf.iloc[valid_mask]) - len(polygons)
        polygons.extend([Point(p).buffer(1) for p in coords[-needed:]])
    gdf = gdf.iloc[valid_mask].reset_index(drop=True)
    gdf["thiessen"] = polygons
    gdf = gdf.set_geometry("thiessen")

    # 11️⃣ Volver a CRS geográfico para exportar GeoJSON
    gdf = gdf.to_crs(epsg=4326)

    # 12️⃣ Exportar a HTML sencillo con Leaflet
    geojson_str = gdf.drop(columns=["geometry"]).to_json()
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset=\"utf-8\" />
        <title>Mapa Thiessen</title>
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
        <link rel=\"stylesheet\" href=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.css\" />
        <script src=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.js\"></script>
    </head>
    <body>
        <div id=\"map\" style=\"width: 100%; height: 800px;\"></div>
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
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_template % geojson_str)
    logger.info(f"Mapa guardado en {output_html}")

# ----------------------------------------------------------------------
# UI de Streamlit
# ----------------------------------------------------------------------
def run_streamlit():
    st.set_page_config(page_title="Mapa de Lluvia – Thiessen", layout="wide")
    st.title("Mapa de Lluvia – Thiessen")
    st.write("🚀 La aplicación se ha iniciado correctamente.")

    # Selección del CSV (histórico tiene prioridad)
    csv_path = "histlluviadiaria.csv" if os.path.exists("histlluviadiaria.csv") else "lluviadiaria.csv"
    if not os.path.exists(csv_path):
        st.error(f"No se encontró ningún CSV de datos en el directorio ({csv_path}).")
        return

    # Lectura ligera para extraer las fechas disponibles
    try:
        df_dates = _read_csv_robust(csv_path)
        date_col = _detect_date_column(df_dates)
        fechas = pd.to_datetime(df_dates[date_col], errors="coerce").dt.normalize().dropna().unique()
        fechas = sorted(fechas)
    except Exception as e:
        st.error(f"Error al cargar el CSV: {e}")
        return

    # Selector de fecha
    fecha_str = st.selectbox("Selecciona la fecha del mapa (se mostrará el día seleccionado)",
                             options=[d.strftime("%Y-%m-%d") for d in fechas])
    if not fecha_str:
        st.warning("Debe seleccionar una fecha.")
        return

    # Generar y mostrar el mapa
    try:
        generar_mapa_con_thiessen(csv_path, fecha_str)
        st.success("✅ Mapa generado con éxito.")
        st.components.v1.html(open("mapa_lluvia.html", "r", encoding="utf-8").read(), height=820)
    except Exception as e:
        st.error(f"❗️ Error al generar el mapa: {e}")
        logger.exception("Error al generar el mapa")

if __name__ == "__main__":
    run_streamlit()
