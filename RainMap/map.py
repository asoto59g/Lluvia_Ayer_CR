import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import voronoi_diagram
import matplotlib.pyplot as plt
import json
import os
import re
import base64
from datetime import datetime, timedelta

def es_dato_valido_lluvia(val):
    if pd.isna(val): return False
    val_str = str(val).strip().upper()
    if val_str in ['', 'N/D', 'NONE', 'NAN', 'NULL', 'SD', 'S/D', '-']: return False
    try:
        limpio = val_str.replace('MM','').replace(',','.').strip()
        float(limpio)
        return True
    except:
        return False

def limpiar_valor_lluvia(val):
    try:
        val_str = str(val).strip().upper()
        limpio = val_str.replace('MM','').replace(',','.').strip()
        return float(limpio)
    except:
        return 0.0

def esta_en_costa_rica_continental(lat, lon):
    try:
        lat_f = float(lat); lon_f = float(lon)
        return (8.0 <= lat_f <= 11.25) and (-86.1 <= lon_f <= -82.5)
    except:
        return False

def limpiar_nombre_estacion(nombre):
    if not nombre or pd.isna(nombre): return "Estación"
    nombre_str = str(nombre).strip()
    if ',' in nombre_str:
        nombre_str = nombre_str.split(',')[0]
    nombre_str = re.sub(r'(?i)autom[aá]tica\s+de\s*', '', nombre_str)
    return nombre_str.strip()

def obtener_color_y_rango(val):
    """
    Simbología oficial IMN corregida y alineada estrictamente con la leyenda HTML.
    """
    if val <= 0:
        return "0 mm", '#ffffff'
    elif 0 < val <= 1:
        return "0 - 1 mm", '#e6f2ff'
    elif 1 < val <= 10:
        return "1 - 10 mm", '#cce6ff'
    elif 10 < val <= 25:
        return "10 - 25 mm", '#99ccff'
    elif 25 < val <= 50:
        return "25 - 50 mm", '#66b3ff'
    elif 50 < val <= 75:
        return "50 - 75 mm", '#3399ff'
    elif 75 < val <= 100:
        return "75 - 100 mm", '#0066cc'
    elif 100 < val <= 125:
        return "100 - 125 mm", '#003399'
    elif 125 < val <= 150:
        return "125 - 150 mm", '#9933ff'
    elif 150 < val <= 175:
        return "150 - 175 mm", '#cc33cc'
    elif 175 < val <= 200:
        return "175 - 200 mm", '#ff3399'
    elif 200 < val <= 225:
        return "200 - 225 mm", '#ff6600'
    elif 225 < val <= 250:
        return "225 - 250 mm", '#cc0000'
    else:
        return "> 250 mm", '#800000'

def generar_mapa_con_thiessen(csv_path='lluviadiaria.csv', output_html='mapa_lluvia_osm.html'):
    if not os.path.exists(csv_path):
        print(f"Error: No se encontró '{csv_path}'.")
        return

    df = pd.read_csv(csv_path)
    
    df_valid = df.dropna(subset=['Latitud_Decimal', 'Longitud_Decimal']).copy()
    df_valid = df_valid[df_valid['Lluvia_Ayer_7am_a_7am_mm'].apply(es_dato_valido_lluvia)].copy()
    df_valid = df_valid[df_valid.apply(lambda r: esta_en_costa_rica_continental(r['Latitud_Decimal'], r['Longitud_Decimal']), axis=1)].copy()

    if df_valid.empty:
        print("No hay registros válidos dentro de Costa Rica.")
        return

    df_valid['val_num'] = df_valid['Lluvia_Ayer_7am_a_7am_mm'].apply(limpiar_valor_lluvia)

    print("Descargando límite territorial de Costa Rica...")
    url_cr = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson"
    world = gpd.read_file(url_cr)
    cr_geom = world[world['ADM0_A3'] == 'CRI'].geometry.values[0]
    
    gdf_cr = gpd.GeoDataFrame(geometry=[cr_geom], crs="EPSG:4326")

    geometry = [Point(xy) for xy in zip(df_valid['Longitud_Decimal'], df_valid['Latitud_Decimal'])]
    gdf_estaciones = gpd.GeoDataFrame(df_valid, geometry=geometry, crs="EPSG:4326")

    print("Generando y recortando polígonos de Thiessen...")
    multi_point = gdf_estaciones.union_all()
    envelope = multi_point.envelope.buffer(2.0)
    voronoi_polys = voronoi_diagram(multi_point, envelope=envelope)

    voronoi_list = list(voronoi_polys.geoms)
    voronoi_gdf = gpd.GeoDataFrame(geometry=voronoi_list, crs="EPSG:4326")
    
    thiessen_gdf = gpd.sjoin_nearest(voronoi_gdf, gdf_estaciones, how="inner")
    thiessen_gdf = thiessen_gdf[~thiessen_gdf.index.duplicated(keep='first')]

    thiessen_clipped = gpd.clip(thiessen_gdf, gdf_cr)

    print("\n" + "="*70)
    print(" REPORTE DE CONTROL DE CALIDAD Y SIMBOLOGÍA DE ESTACIONES")
    print("="*70)
    colores = []
    for _, row in thiessen_clipped.iterrows():
        val = row['val_num']
        rango_str, color_hex = obtener_color_y_rango(val)
        colores.append(color_hex)
        estacion = limpiar_nombre_estacion(row.get('Nombre_Estacion', ''))
        print(f"Estación: {estacion:<28} | Lluvia: {val:>6.1f} mm | Rango: {rango_str:<15} | Color: {color_hex}")
    
    print("="*70 + "\n")
    thiessen_clipped['color'] = colores

    fig, ax = plt.subplots(figsize=(12, 12), dpi=300)
    ax.set_axis_off()

    ax.set_xlim(-86.1, -82.5)
    ax.set_ylim(8.0, 11.25)

    thiessen_clipped.plot(ax=ax, color=thiessen_clipped['color'], edgecolor='#555555', linewidth=0.2, alpha=0.95)

    overlay_path = 'thiessen_overlay.png'
    plt.savefig(overlay_path, bbox_inches='tight', pad_inches=0, transparent=True)
    plt.close()

    with open(overlay_path, "rb") as img_file:
        img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
    img_data_uri = f"data:image/png;base64,{img_base64}"

    if os.path.exists(overlay_path):
        os.remove(overlay_path)

    ayer = datetime.now() - timedelta(days=1)
    meses_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    fecha_titulo = f"{ayer.day} de {meses_es[ayer.month - 1]} de {ayer.year}"

    puntos = []
    for _, row in df_valid.iterrows():
        nombre_original = row.get('Nombre_Estacion', 'Estación')
        nombre_limpio = limpiar_nombre_estacion(nombre_original)
        puntos.append({
            'nombre': nombre_limpio,
            'nombre_completo': str(nombre_original).strip(),
            'region': str(row.get('Region', '')),
            'lat': float(row['Latitud_Decimal']),
            'lon': float(row['Longitud_Decimal']),
            'lluvia_ayer': str(row.get('Lluvia_Ayer_7am_a_7am_mm', '')).strip(),
            'lluvia_hoy': str(row.get('Lluvia_Desde_7am_mm', '0')).strip(),
            'temp': str(row.get('Temperatura_Actual_C', 'N/D')).strip()
        })

    puntos_json = json.dumps(puntos, ensure_ascii=False)

    html_template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mapa de Polígonos de Thiessen - Lluvia Costa Rica</title>
    
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    
    <style>
        body, html {
            margin: 0;
            padding: 0;
            height: 100%;
            font-family: Arial, sans-serif;
        }
        #map {
            width: 100%;
            height: 100vh;
        }
        .info-panel {
            position: absolute;
            top: 15px;
            left: 55px;
            z-index: 1000;
            background: rgba(255, 255, 255, 0.95);
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            max-width: 320px;
        }
        .info-panel h2 {
            margin: 0 0 4px 0;
            font-size: 17px;
            color: #0d233a;
        }
        .info-panel h3 {
            margin: 0 0 6px 0;
            font-size: 14px;
            color: #0056b3;
            font-weight: bold;
        }
        .info-panel p {
            margin: 0;
            font-size: 12px;
            color: #555;
        }
        
        .etiqueta-lluvia {
            background: rgba(0, 51, 102, 0.9);
            color: #ffffff;
            border: 1px solid #ffffff;
            border-radius: 5px;
            padding: 3px 6px;
            font-size: 12px;
            font-weight: bold;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            white-space: nowrap;
        }
        .leaflet-tooltip-top:before {
            border-top-color: rgba(0, 51, 102, 0.9);
        }

        .legend {
            position: absolute;
            bottom: 30px;
            right: 20px;
            z-index: 1000;
            background: white;
            padding: 10px 14px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            font-size: 11px;
            line-height: 1.4;
            max-height: 350px;
            overflow-y: auto;
        }
        .legend h4 {
            margin: 0 0 6px 0;
            font-size: 12px;
            color: #333;
            text-align: center;
        }
        .legend-item {
            display: flex;
            align-items: center;
            margin-bottom: 3px;
        }
        .legend-color {
            width: 18px;
            height: 12px;
            margin-right: 6px;
            border: 1px solid #ccc;
        }

        .leaflet-image-layer {
            image-rendering: pixelated;
            image-rendering: crisp-edges;
        }
    </style>
</head>
<body>

    <div class="info-panel">
        <h2>Instituto Meteorológico Nacional</h2>
        <h3>Polígonos de Thiessen - Lluvia (mm)<br>__FECHA_TITULO__</h3>
        <p>(datos preliminares sin control de calidad)</p>
    </div>

    <div class="legend">
        <h4>Lluvia (mm)</h4>
        <div class="legend-item"><div class="legend-color" style="background: #ffffff;"></div><span>0</span></div>
        <div class="legend-item"><div class="legend-color" style="background: #e6f2ff;"></div><span>0 - 1</span></div>
        <div class="legend-item"><div class="legend-color" style="background: #cce6ff;"></div><span>1 - 10</span></div>
        <div class="legend-item"><div class="legend-color" style="background: #99ccff;"></div><span>10 - 25</span></div>
        <div class="legend-item"><div class="legend-color" style="background: #66b3ff;"></div><span>25 - 50</span></div>
        <div class="legend-item"><div class="legend-color" style="background: #3399ff;"></div><span>50 - 75</span></div>
        <div class="legend-item"><div class="legend-color" style="background: #0066cc;"></div><span>75 - 100</span></div>
        <div class="legend-item"><div class="legend-color" style="background: #003399;"></div><span>100 - 125</span></div>
        <div class="legend-item"><div class="legend-color" style="background: #9933ff;"></div><span>125 - 150</span></div>
        <div class="legend-item"><div class="legend-color" style="background: #cc33cc;"></div><span>150 - 175</span></div>
        <div class="legend-item"><div class="legend-color" style="background: #ff3399;"></div><span>175 - 200</span></div>
        <div class="legend-item"><div class="legend-color" style="background: #ff6600;"></div><span>200 - 225</span></div>
        <div class="legend-item"><div class="legend-color" style="background: #cc0000;"></div><span>225 - 250</span></div>
        <div class="legend-item"><div class="legend-color" style="background: #800000;"></div><span>> 250</span></div>
    </div>

    <div id="map"></div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        var map = L.map('map').setView([9.6000, -84.2000], 8.5);

        var esriStreet = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
            maxZoom: 19,
            attribution: 'Tiles &copy; Esri, OpenStreetMap'
        });

        var esriSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            maxZoom: 19,
            attribution: 'Tiles &copy; Esri'
        });

        esriStreet.addTo(map);

        var imageBounds = [[8.0, -86.1], [11.25, -82.5]];
        var thiessenLayer = L.imageOverlay('__IMG_DATA_URI__', imageBounds, {
            opacity: 0.85,
            interactive: false
        }).addTo(map);

        var estaciones = __PUNTOS_JSON__;
        var markersList = [];

        estaciones.forEach(function(p) {
            var marker = L.circleMarker([p.lat, p.lon], {
                radius: 8,
                fillColor: "#0066cc",
                color: "#ffffff",
                weight: 2,
                opacity: 1,
                fillOpacity: 0.9
            });

            marker.bindTooltip(`${p.lluvia_ayer} mm`, {
                permanent: true,
                direction: 'top',
                offset: [0, -8],
                className: 'etiqueta-lluvia'
            });

            var popupContent = `
                <div style="font-size: 13px; line-height: 1.5; min-width: 190px;">
                    <strong style="font-size: 14px; color: #004488;">${p.nombre_completo}</strong><br>
                    <b>Región:</b> ${p.region}<br>
                    <b>Lluvia (24h Ayer 7am-7am):</b> <span style="color: #0056b3; font-weight: bold; font-size:14px;">${p.lluvia_ayer} mm</span><br>
                    <b>Lluvia Hoy (desde 7am):</b> ${p.lluvia_hoy} mm<br>
                    <b>Temperatura:</b> ${p.temp} °C<br>
                    <small style="color: #666;">Coordenadas: ${p.lat.toFixed(4)}, ${p.lon.toFixed(4)}</small>
                </div>
            `;
            marker.bindPopup(popupContent);

            markersList.push(marker);
        });

        var estacionesLayer = L.layerGroup(markersList);

        var baseMaps = {
            "Calles (Esri/OSM)": esriStreet,
            "Satelital": esriSat
        };

        var overlayMaps = {
            "Polígonos de Thiessen": thiessenLayer,
            "Estaciones y Etiquetas": estacionesLayer
        };

        L.control.layers(baseMaps, overlayMaps, { collapsed: true }).addTo(map);

        if (markersList.length > 0) {
            var group = new L.featureGroup(markersList);
            map.fitBounds(group.getBounds().pad(0.15));
        }
    </script>
</body>
</html>
"""

    html_content = html_template.replace("__FECHA_TITULO__", fecha_titulo)
    html_content = html_content.replace("__IMG_DATA_URI__", img_data_uri)
    html_content = html_content.replace("__PUNTOS_JSON__", puntos_json)

    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"¡Mapa de Polígonos de Thiessen con simbología corregida generado en '{output_html}'!")

if __name__ == '__main__':
    generar_mapa_con_thiessen()