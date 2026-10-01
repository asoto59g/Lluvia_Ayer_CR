# -*- coding: utf-8 -*-

"""
map_combined.py
Mapa de lluvia mediante polígonos Thiessen / Voronoi recortados
estrictamente al perímetro continental de Costa Rica utilizando 'cri.geojson'.

Requisitos:
    Python 3.10+
    streamlit
    pandas
    numpy
    geopandas
    shapely
    scipy

Archivos esperados en la misma carpeta:
    - cri.geojson
    - histlluviadiaria.csv o lluviadiaria.csv
"""

import os
import logging

import pandas as pd
import numpy as np
import geopandas as gpd
import streamlit as st

from shapely.geometry import Polygon, Point, box
from shapely.validation import make_valid
from scipy.spatial import Voronoi


# ============================================================
# CONFIGURACIÓN Y LOGS
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# RUTA ANTERIOR:
# ARCHIVO_RECORTE_GEOJSON = "CRI.geojson"

# RUTA ABSOLUTA SEGURA:
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_RECORTE_GEOJSON = os.path.join(BASE_DIR, "cri.geojson")


# ============================================================
# LECTURA DE ARCHIVOS Y DATOS
# ============================================================

def leer_csv_robusto(path: str) -> pd.DataFrame:
    """
    Intenta leer el CSV con UTF-8. Si falla, intenta latin-1.
    """
    try:
        return pd.read_csv(path, dtype=str, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(path, dtype=str, encoding="latin-1")


@st.cache_data(show_spinner=False)
def obtener_limite_costa_rica(geojson_path: str = ARCHIVO_RECORTE_GEOJSON) -> gpd.GeoDataFrame:
    """
    Carga el archivo GeoJSON local de Costa Rica, unifica las geometrías y las sanea.
    """
    if not os.path.exists(geojson_path):
        logger.error(f"No se encontró el archivo de recorte local: {geojson_path}")
        return None

    try:
        cr_gdf = gpd.read_file(geojson_path)

        if cr_gdf is None or cr_gdf.empty:
            return None

        # Asegurar sistema de referencia WGS84
        if cr_gdf.crs is None:
            cr_gdf = cr_gdf.set_crs(epsg=4326)
        else:
            cr_gdf = cr_gdf.to_crs(epsg=4326)

        # Unificar polígonos y sanear geometrías
        cr_gdf = cr_gdf.dissolve()
        cr_gdf["geometry"] = cr_gdf["geometry"].apply(
            lambda g: make_valid(g) if g is not None else None
        )

        return cr_gdf

    except Exception as error:
        logger.warning(f"Error al procesar el archivo GeoJSON local ({geojson_path}): {error}")
        return None


def detectar_columna_fecha(df: pd.DataFrame) -> str:
    """
    Detecta automáticamente la columna que contiene la fecha,
    dando prioridad al campo 'fecha_datos'.
    """
    if "fecha_datos" in df.columns:
        return "fecha_datos"

    for columna in df.columns:
        if "fecha" in str(columna).lower():
            return columna

    for columna in df.columns:
        valores = df[columna].dropna()
        if valores.empty:
            continue
        try:
            pd.to_datetime(valores.iloc[0], errors="raise")
            return columna
        except Exception:
            continue

    raise ValueError("No se pudo detectar una columna de fechas.")


def convertir_fechas_a_texto(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Convierte columnas datetime a texto para serialización a GeoJSON.
    """
    resultado = gdf.copy()
    for columna in resultado.columns:
        if pd.api.types.is_datetime64_any_dtype(resultado[columna]):
            resultado[columna] = resultado[columna].dt.strftime("%Y-%m-%d")
    return resultado


# ============================================================
# CÁLCULO DE VORONOI Y RECORTE EXACTO
# ============================================================

def generar_poligonos_voronoi_recortados(
    gdf_puntos_proj: gpd.GeoDataFrame,
    cr_boundary_proj: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """
    Calcula polígonos Voronoi finitos e intersecta exactamente
    con la capa de Costa Rica en la proyección plana CRTM05 (EPSG:5367).
    """
    coords = np.array([(geom.x, geom.y) for geom in gdf_puntos_proj.geometry], dtype=float)

    # 1. Definir extensión espacial de trabajo
    if cr_boundary_proj is not None and not cr_boundary_proj.empty:
        bounds = cr_boundary_proj.total_bounds
    else:
        bounds = gdf_puntos_proj.total_bounds

    # Margen amplio para cerrar regiones infinitas de Voronoi
    margin = 300000.0  # 300 km en metros
    minx, miny, maxx, maxy = bounds[0] - margin, bounds[1] - margin, bounds[2] + margin, bounds[3] + margin
    bbox = box(minx, miny, maxx, maxy)

    # 2. Agregar puntos auxiliares lejanos para forzar el cierre de todas las celdas
    far_points = np.array([
        [minx, miny],
        [minx, maxy],
        [maxx, miny],
        [maxx, maxy]
    ])

    all_coords = np.vstack([coords, far_points])
    vor = Voronoi(all_coords)

    # 3. Construir geometrías cerradas de Voronoi
    vor_polygons = []
    for i in range(len(coords)):
        region_idx = vor.point_region[i]
        vertices_idx = vor.regions[region_idx]

        if not vertices_idx or -1 in vertices_idx:
            continue

        polygon_verts = vor.vertices[vertices_idx]
        poly = Polygon(polygon_verts)

        if not poly.is_valid:
            poly = make_valid(poly)

        # Recortar previamente con la caja externa
        poly = poly.intersection(bbox)
        if not poly.is_empty:
            vor_polygons.append(poly)

    gdf_voronoi = gpd.GeoDataFrame(geometry=vor_polygons, crs=gdf_puntos_proj.crs)

    # 4. Join espacial para asignar los atributos del punto correspondiente a cada polígono
    gdf_voronoi = gpd.sjoin(gdf_voronoi, gdf_puntos_proj, how="inner", predicate="intersects")
    gdf_voronoi = gdf_voronoi.drop(columns=["index_right"], errors="ignore")

    # 5. RECORTE ESTRICTO CONTRA COSTA RICA
    if cr_boundary_proj is not None and not cr_boundary_proj.empty:
        try:
            gdf_voronoi["geometry"] = gdf_voronoi["geometry"].apply(make_valid)
            cr_clean = cr_boundary_proj.copy()
            cr_clean["geometry"] = cr_clean["geometry"].apply(make_valid)

            # Overlay por intersección espacial exacta
            gdf_voronoi = gpd.overlay(gdf_voronoi, cr_clean, how="intersection")
        except Exception as err:
            logger.warning(f"Error durante la intersección con Costa Rica: {err}")

    return gdf_voronoi


# ============================================================
# GENERACIÓN PRINCIPAL DEL MAPA
# ============================================================

def generar_mapa_con_thiessen(
    csv_path: str,
    fecha: str,
    geojson_path: str = ARCHIVO_RECORTE_GEOJSON,
    output_html: str = "mapa_lluvia.html"
):
    """
    Procesa los datos, genera el recorte Voronoi y construye la plantilla HTML Leaflet.
    """
    df = leer_csv_robusto(csv_path)

    if df.empty:
        raise ValueError("El archivo CSV está vacío.")

    columna_fecha = detectar_columna_fecha(df)

    df_temp_fecha = pd.to_datetime(df[columna_fecha], errors="coerce").dt.normalize()
    fecha_objetivo = pd.to_datetime(fecha, errors="coerce").normalize()

    if pd.isna(fecha_objetivo):
        raise ValueError(f"Fecha inválida: {fecha}")

    df_filtrado = df[df_temp_fecha == fecha_objetivo].copy()

    if df_filtrado.empty:
        raise ValueError(f"No hay datos para la fecha {fecha}.")

    # Restar 1 día a la fecha_datos para mostrar el día correspondiente a la medición
    if "fecha_datos" in df_filtrado.columns and not df_filtrado["fecha_datos"].dropna().empty:
        fecha_dt = pd.to_datetime(df_filtrado["fecha_datos"].dropna().iloc[0], errors="coerce")
        if not pd.isna(fecha_dt):
            fecha_datos_str = (fecha_dt - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            fecha_datos_str = (fecha_objetivo - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        fecha_datos_str = (fecha_objetivo - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    if "Longitud_Decimal" not in df_filtrado.columns or "Latitud_Decimal" not in df_filtrado.columns:
        raise ValueError("No existen las columnas 'Longitud_Decimal' y 'Latitud_Decimal'.")

    df_filtrado["lon"] = pd.to_numeric(df_filtrado["Longitud_Decimal"], errors="coerce")
    df_filtrado["lat"] = pd.to_numeric(df_filtrado["Latitud_Decimal"], errors="coerce")

    df_filtrado = df_filtrado.dropna(subset=["lon", "lat"]).copy()
    df_filtrado = df_filtrado[
        (df_filtrado["lon"] >= -180) & (df_filtrado["lon"] <= 180) &
        (df_filtrado["lat"] >= -90) & (df_filtrado["lat"] <= 90)
    ].copy()

    if df_filtrado.empty:
        raise ValueError("No existen coordenadas válidas para la fecha seleccionada.")

    df_filtrado = df_filtrado.drop_duplicates(subset=["lon", "lat"]).reset_index(drop=True)

    # Cantidad total de estaciones válidas procesadas
    num_estaciones_validas = len(df_filtrado)

    # 1. GeoDataFrame de puntos en WGS84
    gdf_puntos = gpd.GeoDataFrame(
        df_filtrado,
        geometry=gpd.points_from_xy(df_filtrado["lon"], df_filtrado["lat"]),
        crs="EPSG:4326"
    )

    # 2. Convertir a proyección oficial CRTM05 (EPSG:5367) en metros
    gdf_puntos_proj = gdf_puntos.to_crs(epsg=5367)

    # 3. Obtener perímetro de Costa Rica proyectado en CRTM05 desde el GeoJSON local
    cr_boundary = obtener_limite_costa_rica(geojson_path)
    if cr_boundary is not None and not cr_boundary.empty:
        cr_boundary_proj = cr_boundary.to_crs(epsg=5367)
    else:
        cr_boundary_proj = None

    # 4. Generar polígonos Thiessen recortados
    gdf_thiessen_proj = generar_poligonos_voronoi_recortados(gdf_puntos_proj, cr_boundary_proj)

    # 5. Volver a proyectar a WGS84 para exportar
    gdf_thiessen = gdf_thiessen_proj.to_crs(epsg=4326)

    # Limpiar columnas con geometrías duplicadas o secundarias
    cols_to_drop = [
        col for col in gdf_thiessen.columns
        if col != gdf_thiessen.geometry.name and isinstance(gdf_thiessen[col].dtype, gpd.array.GeometryDtype)
    ]
    if cols_to_drop:
        gdf_thiessen = gdf_thiessen.drop(columns=cols_to_drop, errors="ignore")

    gdf_thiessen_export = convertir_fechas_a_texto(gdf_thiessen)
    gdf_puntos_export = convertir_fechas_a_texto(gdf_puntos)

    geojson_thiessen = gdf_thiessen_export.to_json(ensure_ascii=False)
    geojson_puntos = gdf_puntos_export.to_json(ensure_ascii=False)

    # ----------------------------------------------------
    # PLANTILLA INTERACTIVA HTML (LEAFLET)
    # ----------------------------------------------------
    html_template = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Mapa de Lluvia Thiessen - Costa Rica</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<style>
html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
}
#map {
    width: 100%;
    height: 800px;
}
.map-title-box {
    background: rgba(255, 255, 255, 0.9);
    padding: 10px 14px;
    border-radius: 6px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    font-family: Arial, sans-serif;
    line-height: 1.35;
}
.map-title-box .line-1 {
    font-size: 16px;
    font-weight: bold;
    color: #000000;
}
.map-title-box .line-2 {
    font-size: 13px;
    font-weight: bold;
    color: #0056b3;
}
.map-title-box .line-3 {
    font-size: 13px;
    font-weight: bold;
    color: #0056b3;
}
.map-title-box .line-estaciones {
    font-size: 12px;
    font-weight: bold;
    color: #2b7813;
}
.map-title-box .line-4 {
    font-size: 11px;
    color: #000000;
}
.map-title-box .line-5 {
    font-size: 11px;
    color: #000000;
}

/* Estilo para las etiquetas flotantes de lluvia (sin fondo) */
.label-lluvia-container {
    background: transparent;
    border: none;
}
.label-lluvia {
    background-color: transparent;
    border: none;
    color: #000000;
    font-family: Arial, sans-serif;
    font-weight: bold;
    text-align: center;
    white-space: nowrap;
    box-shadow: none;
    pointer-events: none;
    text-shadow: -1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff, 1px 1px 0 #fff, 0 0 4px #fff;
    transition: font-size 0.2s ease;
}

/* Estilo para la caja de la leyenda / simbología */
.legend-box {
    background: rgba(255, 255, 255, 0.95);
    padding: 10px 12px;
    border-radius: 6px;
    border: 1px solid #777;
    box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    font-family: Arial, sans-serif;
    font-size: 13px;
    line-height: 1.4;
    color: #000;
}
.legend-title {
    font-weight: bold;
    font-size: 14px;
    margin-bottom: 6px;
    text-align: center;
}
.legend-item {
    display: flex;
    align-items: center;
    margin-bottom: 3px;
}
.legend-color {
    width: 28px;
    height: 16px;
    border: 1px solid #444;
    margin-right: 8px;
    box-sizing: border-box;
}
</style>
</head>

<body>
<div id="map"></div>

<script>
/* =========================================================
   1. MAPAS BASE (OSM + SATÉLITE ESRI)
   ========================================================= */
var osmStandard = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
});

var esriSatellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19,
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics'
});

var map = L.map('map', {
    center: [9.7489, -83.7534],
    zoom: 8,
    layers: [osmStandard]
});

/* =========================================================
   TÍTULO FLOTANTE EN ESQUINA SUPERIOR IZQUIERDA
   ========================================================= */
var titleControl = L.control({ position: 'topleft' });

titleControl.onAdd = function(map) {
    var div = L.DomUtil.create('div', 'map-title-box');
    div.innerHTML = `
        <div class="line-1">Lluvia diaria en Costa Rica</div>
        <div class="line-2">Polígonos de Thiessen</div>
        <div class="line-3">Fecha datos: __FECHA_DATOS__</div>
        <div class="line-estaciones">No estaciones: __NUM_ESTACIONES__</div>
        <div class="line-4">Fuente: IMN Costa Rica</div>
        <div class="line-5">Datos sin control de calidad</div>
    `;
    return div;
};

titleControl.addTo(map);

/* =========================================================
   2. DATOS GEOJSON Y ESCALA DE COLORES SEGÚN SIMBOLOGÍA
   ========================================================= */
var geojsonVoronoiData = __GEOJSON_VORONOI__;
var geojsonPuntosData = __GEOJSON_PUNTOS__;

// Mapeo exacto de rangos a colores hexadecimales tomados de la imagen
function obtenerColorLluvia(valorNum) {
    if (valorNum === null || valorNum === undefined || isNaN(valorNum)) return '#cccccc';
    if (valorNum === 0) return '#e3d2bf';
    if (valorNum > 0 && valorNum <= 1) return '#ffffcc';
    if (valorNum > 1 && valorNum <= 10) return '#e0f3f8';
    if (valorNum > 10 && valorNum <= 25) return '#91bfdb';
    if (valorNum > 25 && valorNum <= 50) return '#67a9cf';
    if (valorNum > 50 && valorNum <= 75) return '#4393c3';
    if (valorNum > 75 && valorNum <= 100) return '#4f41f1';
    if (valorNum > 100 && valorNum <= 125) return '#5432db';
    if (valorNum > 125 && valorNum <= 150) return '#443b85';
    if (valorNum > 150 && valorNum <= 175) return '#9b4393';
    if (valorNum > 175 && valorNum <= 200) return '#b93eab';
    if (valorNum > 200 && valorNum <= 225) return '#d94ce1';
    if (valorNum > 225 && valorNum <= 250) return '#e2589e';
    if (valorNum > 250) return '#ab4393';
    return '#e3d2bf';
}

function extraerNumLluvia(properties) {
    if (!properties) return null;
    var campos = [
        "Lluvia_Ayer_7am_a_7am_mm", 
        "Lluvia_Ayer", 
        "Lluvia", 
        "lluvia", 
        "Lluvia_mm", 
        "Lluvia_Diaria", 
        "Monto_mm", 
        "Precipitacion", 
        "precipitacion"
    ];
    for (var i = 0; i < campos.length; i++) {
        var campo = campos[i];
        if (properties[campo] !== undefined && properties[campo] !== null && properties[campo] !== "") {
            var val = parseFloat(properties[campo]);
            return isNaN(val) ? null : val;
        }
    }
    return null;
}

/* =========================================================
   3. CAPA VORONOI / THIESSEN (RECORTADA Y COLOREADA POR RANGOS)
   ========================================================= */
var capaVoronoi = L.geoJSON(geojsonVoronoiData, {
    style: function(feature) {
        var valNum = extraerNumLluvia(feature.properties);
        var colorRango = obtenerColorLluvia(valNum);
        return {
            color: '#444444',
            weight: 1.0,
            opacity: 0.8,
            fillColor: colorRango,
            fillOpacity: 0.75
        };
    },
    onEachFeature: function(feature, layer) {
        var contenido = '<div style="max-height:300px;overflow:auto;">';
        if (feature.properties) {
            Object.keys(feature.properties).forEach(function(key) {
                var valor = feature.properties[key];
                if (valor !== null && valor !== undefined && valor !== '') {
                    contenido += '<b>' + key + ':</b> ' + valor + '<br>';
                }
            });
        }
        contenido += '</div>';
        layer.bindPopup(contenido);

        layer.on({
            mouseover: function(e) {
                e.target.setStyle({ weight: 2.2, color: '#000000', fillOpacity: 0.9 });
            },
            mouseout: function(e) {
                capaVoronoi.resetStyle(e.target);
            }
        });
    }
}).addTo(map);

/* =========================================================
   4. FUNCIÓN AUXILIAR PARA OBTENER VALOR DE TEXTO EN MM
   ========================================================= */
function obtenerValorLluvia(properties) {
    var val = extraerNumLluvia(properties);
    return (val !== null) ? val.toFixed(1) + " mm" : "N/A";
}

/* =========================================================
   5. CAPA ESTACIONES / PUNTOS CON ETIQUETAS
   ========================================================= */
var capaPuntos = L.geoJSON(geojsonPuntosData, {
    pointToLayer: function(feature, latlng) {
        return L.circleMarker(latlng, {
            radius: 4.5,
            fillColor: '#e02424',
            color: '#ffffff',
            weight: 1.2,
            opacity: 1,
            fillOpacity: 0.95
        });
    },
    onEachFeature: function(feature, layer) {
        var contenido = '<div style="max-height:300px;overflow:auto;"><b>Estación Meteorológica</b><br>';
        if (feature.properties) {
            Object.keys(feature.properties).forEach(function(key) {
                var valor = feature.properties[key];
                if (valor !== null && valor !== undefined && valor !== '') {
                    contenido += '<b>' + key + ':</b> ' + valor + '<br>';
                }
            });
        }
        contenido += '</div>';
        layer.bindPopup(contenido);
    }
}).addTo(map);

/* =========================================================
   6. GRUPO DE ETIQUETAS Y ESCALADO SEGÚN ZOOM
   ========================================================= */
var grupoEtiquetas = L.layerGroup().addTo(map);

function actualizarEtiquetasZoom() {
    grupoEtiquetas.clearLayers();
    var zoomActual = map.getZoom();

    if (zoomActual < 7) return;

    var fontSize = Math.max(8, Math.min(18, zoomActual * 1.3 - 2));

    capaPuntos.eachLayer(function(layer) {
        var latlng = layer.getLatLng();
        var valorLluvia = obtenerValorLluvia(layer.feature.properties);

        var htmlLabel = `<div class="label-lluvia" style="font-size: ${fontSize}px;">${valorLluvia}</div>`;

        var labelIcon = L.divIcon({
            className: 'label-lluvia-container',
            html: htmlLabel,
            iconAnchor: [-8, fontSize / 2]
        });

        L.marker(latlng, { icon: labelIcon, interactive: false }).addTo(grupoEtiquetas);
    });
}

map.on('zoomend', actualizarEtiquetasZoom);
actualizarEtiquetasZoom();

/* =========================================================
   7. LEYENDA / SIMBOLOGÍA FIJA EN LA ESQUINA INFERIOR DERECHA
   ========================================================= */
var legendControl = L.control({ position: 'bottomright' });

legendControl.onAdd = function(map) {
    var div = L.DomUtil.create('div', 'legend-box');
    var rangos = [
        { label: '0', color: '#e3d2bf' },
        { label: '0 - 1', color: '#ffffcc' },
        { label: '1 - 10', color: '#e0f3f8' },
        { label: '10 - 25', color: '#91bfdb' },
        { label: '25 - 50', color: '#67a9cf' },
        { label: '50 - 75', color: '#4393c3' },
        { label: '75 - 100', color: '#4f41f1' },
        { label: '100 - 125', color: '#5432db' },
        { label: '125 - 150', color: '#443b85' },
        { label: '150 - 175', color: '#9b4393' },
        { label: '175 - 200', color: '#b93eab' },
        { label: '200 - 225', color: '#d94ce1' },
        { label: '225 - 250', color: '#e2589e' },
        { label: '250 - 275', color: '#ab4393' }
    ];

    var html = '<div class="legend-title">Lluvia (mm)</div>';
    for (var i = 0; i < rangos.length; i++) {
        html += '<div class="legend-item">' +
                '<div class="legend-color" style="background-color:' + rangos[i].color + ';"></div>' +
                '<span>' + rangos[i].label + '</span>' +
                '</div>';
    }
    div.innerHTML = html;
    return div;
};

legendControl.addTo(map);

/* =========================================================
   8. CONTROL DE CAPAS Y ENCUADRE
   ========================================================= */
var baseMaps = {
    "OSM Estándar": osmStandard,
    "Satélite (Esri World Imagery)": esriSatellite
};

var overlayMaps = {
    "Polígonos Voronoi / Thiessen": capaVoronoi,
    "Estaciones (Puntos)": capaPuntos,
    "Etiquetas de Lluvia (mm)": grupoEtiquetas
};

L.control.layers(baseMaps, overlayMaps, { collapsed: false }).addTo(map);

if (capaVoronoi.getBounds().isValid()) {
    map.fitBounds(capaVoronoi.getBounds(), { padding: [20, 20] });
}
</script>
</body>
</html>
"""

    html_final = html_template.replace(
        "__GEOJSON_VORONOI__", geojson_thiessen
    ).replace(
        "__GEOJSON_PUNTOS__", geojson_puntos
    ).replace(
        "__FECHA_DATOS__", fecha_datos_str
    ).replace(
        "__NUM_ESTACIONES__", str(num_estaciones_validas)
    )

    with open(output_html, "w", encoding="utf-8") as archivo:
        archivo.write(html_final)

    logger.info("Mapa guardado exitosamente: %s", output_html)
    return output_html


# ============================================================
# INTERFAZ STREAMLIT
# ============================================================

def run_streamlit():

    st.set_page_config(
        page_title="Mapa de Lluvia - Thiessen CR",
        page_icon="🌧️",
        layout="wide"
    )

    st.title("🌧️ Mapa de Lluvia - Polígonos Thiessen (Costa Rica)")
    st.caption("Intersección exacta recortada con archivo local cri.geojson")

    if not os.path.exists(ARCHIVO_RECORTE_GEOJSON):
        st.error(f"⚠️ No se encontró el archivo de recorte local `{ARCHIVO_RECORTE_GEOJSON}` en la carpeta de ejecución.")
        return

    if os.path.exists("histlluviadiaria.csv"):
        csv_path = "histlluviadiaria.csv"
    elif os.path.exists("lluviadiaria.csv"):
        csv_path = "lluviadiaria.csv"
    else:
        st.error("No se encontró el archivo de datos.")
        st.write("Debe existir uno de los siguientes archivos en el directorio:")
        st.code("histlluviadiaria.csv\nlluviadiaria.csv")
        return

    st.info(f"📄 Archivo CSV de lluvia: `{csv_path}` | 🗺 Capa de recorte: `{ARCHIVO_RECORTE_GEOJSON}`")

    try:
        df_dates = leer_csv_robusto(csv_path)
        columna_fecha = detectar_columna_fecha(df_dates)

        fechas = (
            pd.to_datetime(df_dates[columna_fecha], errors="coerce")
            .dt.normalize()
            .dropna()
            .unique()
        )
        fechas = sorted(fechas)

    except Exception as error:
        st.error("Error al leer las fechas del CSV.")
        st.exception(error)
        return

    if not fechas:
        st.error("No se encontraron fechas válidas.")
        return

    opciones_fecha = [fecha.strftime("%Y-%m-%d") for fecha in fechas]

    fecha_str = st.selectbox(
        "📅 Selecciona la fecha:",
        opciones_fecha
    )

    if st.button("🗺️ Generar mapa", type="primary"):
        with st.spinner("Procesando geometrías y recortando con cri.geojson..."):
            try:
                output_file = generar_mapa_con_thiessen(
                    csv_path=csv_path,
                    fecha=fecha_str,
                    geojson_path=ARCHIVO_RECORTE_GEOJSON,
                    output_html="mapa_lluvia.html"
                )

                st.success("✅ Mapa generado y recortado correctamente.")

                with open(output_file, "r", encoding="utf-8") as archivo:
                    html_content = archivo.read()

                st.components.v1.html(
                    html_content,
                    height=820,
                    scrolling=False
                )

            except Exception as error:
                st.error(f"❗ Error al generar el mapa: {error}")
                with st.expander("Detalles técnicos"):
                    st.exception(error)
                logger.exception("Error al generar mapa")


if __name__ == "__main__":
    run_streamlit()