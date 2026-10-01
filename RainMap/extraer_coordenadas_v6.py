#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para extraer y afinar coordenadas (latitud/longitud decimal) de todas las estaciones.
Pipeline híbrido v6: v1+v2+v3+v4 (PSM Selectivo) + Fallback DOM Robusto (score < 50).

Archivo de salida: coordenadas_estaciones_refinadas.csv
"""

import pandas as pd
import re
import os
import asyncio
import numpy as np
import json
from datetime import datetime

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Instala Playwright con: pip install playwright && playwright install chromium")
    exit(1)

try:
    import pytesseract
    from PIL import Image, ImageEnhance
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("Aviso: pytesseract/PIL no están instalados. Para usar OCR ejecuta: pip install pytesseract pillow")

# Importar funciones de parsing
from parser_coords_final import corregir_texto_ocr, extraer_dms, dms_a_decimal


# Intentar importar scipy para Sauvola
try:
    from scipy.ndimage import uniform_filter, binary_opening, binary_closing
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("Aviso: scipy no disponible, Sauvola deshabilitado. pip install scipy")


def detectar_layout_texto(ruta_img):
    """
    Analiza la imagen para detectar el layout del texto y elegir PSM óptimo.
    Retorna: 'single_line' | 'sparse' | 'block' | 'auto'
    """
    try:
        img = Image.open(ruta_img)
        w, h = img.size
        img_gray = img.convert('L')
        arr = np.array(img_gray)
        
        # Binarización simple para análisis
        threshold = 128
        arr_bin = (arr < threshold).astype(np.uint8)  # 1 = texto, 0 = fondo
        
        # Proyección horizontal (suma por fila)
        h_proj = np.sum(arr_bin, axis=1)
        # Filas con texto
        text_rows = np.where(h_proj > w * 0.05)[0]
        
        if len(text_rows) == 0:
            return 'auto'
        
        # Contar líneas separadas (gaps verticales)
        gaps = np.diff(text_rows) > 3
        num_lineas = np.sum(gaps) + 1
        
        # Proyección vertical (suma por columna)
        v_proj = np.sum(arr_bin, axis=0)
        text_cols = np.where(v_proj > h * 0.05)[0]
        
        if len(text_cols) == 0:
            return 'auto'
        
        # Ancho ocupado
        text_width = text_cols[-1] - text_cols[0]
        text_height = text_rows[-1] - text_rows[0]
        
        aspect_ratio = text_width / max(text_height, 1)
        
        # Decisión basada en layout
        if num_lineas == 1:
            return 'single_line'      # PSM 7 (una línea)
        elif num_lineas <= 3 and aspect_ratio > 2:
            return 'sparse'           # PSM 8 (poco texto disperso)
        elif num_lineas >= 4:
            return 'block'            # PSM 6 (bloque uniforme)
        else:
            return 'auto'             # PSM 13 (automático)
    except Exception:
        return 'auto'


def get_psm_configs(layout):
    """Retorna lista de configs PSM ordenados por prioridad para el layout."""
    configs_map = {
        'single_line': ['--psm 7', '--psm 8', '--psm 13', '--psm 6'],
        'sparse': ['--psm 8', '--psm 7', '--psm 13', '--psm 6'],
        'block': ['--psm 6', '--psm 4', '--psm 3', '--psm 13'],
        'auto': ['--psm 13', '--psm 6', '--psm 7', '--psm 8']
    }
    return configs_map.get(layout, configs_map['auto'])


def preprocesar_imagen_ocr_v1(ruta_img):
    """
    Pipeline v1 (original): DSF=2.0, resize 2.5x, escala de grises, contraste 2.0x, PSM 6/11.
    """
    if not os.path.exists(ruta_img):
        return ""
    try:
        img = Image.open(ruta_img)
        w, h = img.size
        img_large = img.resize((int(w * 2.5), int(h * 2.5)), Image.Resampling.LANCZOS)
        img_gray = img_large.convert('L')
        enhancer = ImageEnhance.Contrast(img_gray)
        img_contrast = enhancer.enhance(2.0)
        
        texto = pytesseract.image_to_string(img_contrast, lang='spa', config='--psm 6')
        if len(texto.strip()) < 5:
            texto += " " + pytesseract.image_to_string(img_contrast, config='--psm 11')
            
        return texto
    except Exception as e:
        print(f"  [Aviso OCR v1] Error al procesar {ruta_img}: {e}")
        return ""


def preprocesar_imagen_ocr_v2(ruta_img):
    """
    Pipeline v2: DSF=3.0, resize 2.0x, Otsu global, multi-PSM fijo.
    """
    if not os.path.exists(ruta_img):
        return ""
    try:
        img = Image.open(ruta_img)
        w, h = img.size
        img_large = img.resize((int(w * 2.0), int(h * 2.0)), Image.Resampling.LANCZOS)
        img_gray = img_large.convert('L')
        
        arr = np.array(img_gray)
        threshold = 128
        try:
            hist, bins = np.histogram(arr.flatten(), 256, [0, 256])
            total = arr.size
            sum_total = np.sum(np.arange(256) * hist)
            sum_b, w_b, max_var, thresh = 0, 0, 0, 0
            for i in range(256):
                w_b += hist[i]
                if w_b == 0:
                    continue
                w_f = total - w_b
                if w_f == 0:
                    break
                sum_b += i * hist[i]
                m_b = sum_b / w_b
                m_f = (sum_total - sum_b) / w_f
                var_between = w_b * w_f * (m_b - m_f) ** 2
                if var_between > max_var:
                    max_var = var_between
                    thresh = i
            threshold = thresh
        except Exception:
            pass
        
        arr_bin = np.where(arr > threshold, 255, 0).astype(np.uint8)
        img_bin = Image.fromarray(arr_bin, mode='L')
        
        enhancer = ImageEnhance.Contrast(img_bin)
        img_contrast = enhancer.enhance(1.5)
        
        configs = ['--psm 7', '--psm 6', '--psm 8', '--psm 13']
        textos = []
        for config in configs:
            try:
                txt = pytesseract.image_to_string(img_contrast, lang='spa', config=config)
                if txt.strip():
                    textos.append(txt.strip())
            except Exception:
                pass
        
        return " ".join(dict.fromkeys(textos))
    except Exception as e:
        print(f"  [Aviso OCR v2] Error al procesar {ruta_img}: {e}")
        return ""


def preprocesar_imagen_ocr_v3(ruta_img):
    """
    Pipeline v3: Sauvola local + morfológico.
    """
    if not os.path.exists(ruta_img):
        return ""
    if not HAS_SCIPY:
        return preprocesar_imagen_ocr_v2(ruta_img)
    try:
        img = Image.open(ruta_img)
        w, h = img.size
        img_large = img.resize((int(w * 2.5), int(h * 2.5)), Image.Resampling.LANCZOS)
        img_gray = img_large.convert('L')
        
        arr = np.array(img_gray, dtype=np.float32) / 255.0
        
        window_size = 15
        k = 0.2
        R = 128
        
        mean = uniform_filter(arr, size=window_size)
        mean_sq = uniform_filter(arr * arr, size=window_size)
        std = np.sqrt(np.maximum(mean_sq - mean * mean, 0))
        
        threshold_map = mean * (1 + k * (std / R - 1))
        arr_bin = np.where(arr > threshold_map, 1.0, 0.0)
        
        struct = np.ones((2, 2), dtype=bool)
        arr_clean = binary_opening(arr_bin, structure=struct)
        arr_clean = binary_closing(arr_clean, structure=struct)
        
        img_bin = Image.fromarray((arr_clean * 255).astype(np.uint8), mode='L')
        
        enhancer = ImageEnhance.Contrast(img_bin)
        img_contrast = enhancer.enhance(1.3)
        
        configs = ['--psm 7', '--psm 6', '--psm 8', '--psm 13', '--psm 4']
        textos = []
        for config in configs:
            try:
                txt = pytesseract.image_to_string(img_contrast, lang='spa', config=config)
                if txt.strip():
                    textos.append(txt.strip())
            except Exception:
                pass
        
        return " ".join(dict.fromkeys(textos))
    except Exception as e:
        print(f"  [Aviso OCR v3] Error al procesar {ruta_img}: {e}")
        return preprocesar_imagen_ocr_v2(ruta_img)


def preprocesar_imagen_ocr_v4_psm_selectivo(ruta_img):
    """
    Pipeline v4 (Paso 3 - PSM Selectivo): Detección automática de layout + PSM óptimo.
    """
    if not os.path.exists(ruta_img):
        return ""
    try:
        # Detectar layout
        layout = detectar_layout_texto(ruta_img)
        
        img = Image.open(ruta_img)
        w, h = img.size
        img_large = img.resize((int(w * 2.5), int(h * 2.5)), Image.Resampling.LANCZOS)
        img_gray = img_large.convert('L')
        
        # Preprocesado estándar: Otsu global (más rápido que Sauvola)
        arr = np.array(img_gray)
        threshold = 128
        try:
            hist, bins = np.histogram(arr.flatten(), 256, [0, 256])
            total = arr.size
            sum_total = np.sum(np.arange(256) * hist)
            sum_b, w_b, max_var, thresh = 0, 0, 0, 0
            for i in range(256):
                w_b += hist[i]
                if w_b == 0:
                    continue
                w_f = total - w_b
                if w_f == 0:
                    break
                sum_b += i * hist[i]
                m_b = sum_b / w_b
                m_f = (sum_total - sum_b) / w_f
                var_between = w_b * w_f * (m_b - m_f) ** 2
                if var_between > max_var:
                    max_var = var_between
                    thresh = i
            threshold = thresh
        except Exception:
            pass
        
        arr_bin = np.where(arr > threshold, 255, 0).astype(np.uint8)
        img_bin = Image.fromarray(arr_bin, mode='L')
        
        enhancer = ImageEnhance.Contrast(img_bin)
        img_contrast = enhancer.enhance(1.5)
        
        # PSM selectivo basado en layout
        configs = get_psm_configs(layout)
        textos = []
        for config in configs:
            try:
                txt = pytesseract.image_to_string(img_contrast, lang='spa', config=config)
                if txt.strip():
                    textos.append(txt.strip())
            except Exception:
                pass
        
        return " ".join(dict.fromkeys(textos))
    except Exception as e:
        print(f"  [Aviso OCR v4] Error al procesar {ruta_img}: {e}")
        return preprocesar_imagen_ocr_v2(ruta_img)


def validar_coordenadas(lat_dms, lon_dms, texto_ocr, texto_dom):
    """
    Puntuación de calidad 0-100 para coordenadas extraídas.
    Criterios:
    - 20 pts: lat y lon presentes
    - 20 pts: rangos válidos CR (lat 8-12, lon 82-86)
    - 15 pts: parser extrae DMS limpio (sin artefactos °/backslash)
    - 15 pts: consistencia OCR vs DOM (mismos dígitos clave)
    - 15 pts: segundos con decimales razonables (0-59.99)
    - 15 pts: longitud tiene 2-3 dígitos grados (no 1 ni 4+)
    """
    score = 0
    
    if not lat_dms and not lon_dms:
        return 0
    
    # 20 pts: ambos presentes
    if lat_dms and lon_dms:
        score += 20
    elif lat_dms or lon_dms:
        score += 10
    
    # 20 pts: rangos válidos CR
    def extraer_grados(dms):
        if not dms:
            return None
        m = re.search(r'([0-9]{1,3})[°\s]', dms)
        return float(m.group(1)) if m else None
    
    lat_deg = extraer_grados(lat_dms)
    lon_deg = extraer_grados(lon_dms)
    
    if lat_deg and 8 <= lat_deg <= 12:
        score += 10
    if lon_deg and 82 <= lon_deg <= 86:
        score += 10
    
    # 15 pts: DMS limpio (sin backslashes, grados raros)
    def dms_limpio(dms):
        if not dms:
            return False
        if '\\' in dms:
            return False
        return bool(re.match(r'^[0-9]{1,2}[°\s]+[0-9]{2}[\'\s]+[0-9]{2}(?:\.[0-9]+)?["\s]*[NSOWE]$', dms))
    
    if dms_limpio(lat_dms):
        score += 7
    if dms_limpio(lon_dms):
        score += 8
    
    # 15 pts: consistencia OCR vs DOM
    def extraer_digitos_clave(texto):
        return re.findall(r'[0-9]{2,3}', texto)
    
    ocr_digits = set(extraer_digitos_clave(texto_ocr))
    dom_digits = set(extraer_digitos_clave(texto_dom))
    if ocr_digits and dom_digits:
        overlap = len(ocr_digits & dom_digits)
        score += min(15, overlap * 3)
    
    # 15 pts: segundos razonables
    def segundos_ok(dms):
        if not dms:
            return False
        m = re.search(r'([0-9]{2}(?:\.[0-9]+)?)["\s]*[NSOWE]$', dms)
        if m:
            try:
                seg = float(m.group(1))
                return 0 <= seg < 60
            except:
                return False
        return False
    
    if segundos_ok(lat_dms):
        score += 7
    if segundos_ok(lon_dms):
        score += 8
    
    # 15 pts: longitud 2-3 dígitos grados
    if lon_deg:
        lon_str = str(int(lon_deg))
        if len(lon_str) in [2, 3]:
            score += 15
    
    return min(100, score)


async def extraer_coordenadas_dom(page, url):
    """
    Fallback DOM Robusto (Paso 4): Extraer coordenadas directamente del HTML.
    Busca en: tablas, metadatos, scripts JSON, atributos data-*, texto visible.
    """
    lat_dms = ""
    lon_dms = ""
    
    try:
        # Obtener contenido de todos los frames
        full_html = ""
        for frame in page.frames:
            try:
                content = await frame.content()
                full_html += "\n" + content
            except Exception:
                pass
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(full_html, 'html.parser')
        
        # 1. Buscar en tablas con palabras clave
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                cell_text = ' '.join([c.get_text(strip=True) for c in cells])
                
                # Buscar patrones de coordenadas en la fila
                lat_match = re.search(r'[Ll]atitud[^0-9]*([0-9]{1,2}[°\s\d\'"\sNS]+)', cell_text)
                lon_match = re.search(r'[Ll]ongitud[^0-9]*([0-9]{1,3}[°\s\d\'"\sOW]+)', cell_text)
                
                if lat_match:
                    lat_dms = lat_match.group(1).strip()
                if lon_match:
                    lon_dms = lon_match.group(1).strip()
        
        # 2. Buscar en todo el texto visible (DOM text)
        all_text = soup.get_text(separator=' ', strip=True)
        
        # Patrones DMS más flexibles para DOM
        if not lat_dms:
            matches = re.findall(r'([0-9]{1,2})[°\s]+([0-9]{2})[\'\s]+([0-9]{2}(?:\.[0-9]+)?)["\s]*([NS])', all_text)
            for m in matches:
                deg = int(m[0])
                if 8 <= deg <= 12:
                    lat_dms = f"{m[0]}° {m[1]}' {m[2]}\" {m[3]}"
                    break
        
        if not lon_dms:
            matches = re.findall(r'([0-9]{1,3})[°\s]+([0-9]{2})[\'\s]+([0-9]{2}(?:\.[0-9]+)?)["\s]*([OW])', all_text)
            for m in matches:
                deg = int(m[0])
                if 82 <= deg <= 86:
                    lon_dms = f"{m[0]}° {m[1]}' {m[2]}\" {m[3]}"
                    break
        
        # 3. Buscar en scripts JSON / data attributes
        for script in soup.find_all('script'):
            if script.string:
                # Buscar coordenadas en JSON
                json_matches = re.findall(r'["\']?(?:lat|latitude|lon|longitude)["\']?\s*[:=]\s*([-]?\d+\.\d+)', script.string, re.IGNORECASE)
                if len(json_matches) >= 2:
                    try:
                        lat = float(json_matches[0])
                        lon = float(json_matches[1])
                        if 8 <= lat <= 12 and -86 <= lon <= -82:
                            # Convertir decimal a DMS para consistencia
                            from parser_coords_final import decimal_a_dms
                            lat_dms = decimal_a_dms(lat, 'LAT')
                            lon_dms = decimal_a_dms(lon, 'LON')
                            break
                    except Exception:
                        pass
        
        # 4. Buscar en meta tags y data attributes
        for meta in soup.find_all('meta'):
            content = meta.get('content', '')
            name = meta.get('name', '') + meta.get('property', '')
            if 'geo' in name.lower() or 'coord' in name.lower():
                coords = re.findall(r'[-]?\d+\.\d+', content)
                if len(coords) >= 2:
                    try:
                        lat = float(coords[0])
                        lon = float(coords[1])
                        if 8 <= lat <= 12 and -86 <= lon <= -82:
                            from parser_coords_final import decimal_a_dms
                            lat_dms = decimal_a_dms(lat, 'LAT')
                            lon_dms = decimal_a_dms(lon, 'LON')
                            break
                    except Exception:
                        pass
        
        # 5. Buscar en elementos con data-* attributes
        for elem in soup.find_all(attrs={'data-lat': True, 'data-lon': True}):
            try:
                lat = float(elem.get('data-lat', 0))
                lon = float(elem.get('data-lon', 0))
                if 8 <= lat <= 12 and -86 <= lon <= -82:
                    from parser_coords_final import decimal_a_dms
                    lat_dms = decimal_a_dms(lat, 'LAT')
                    lon_dms = decimal_a_dms(lon, 'LON')
                    break
            except Exception:
                pass
        
    except Exception as e:
        print(f"  [DOM Fallback] Error: {e}")
    
    return lat_dms, lon_dms


async def extraer_coordenadas_estacion(page, url, idx, carpeta_capturas):
    """
    Extrae coordenadas de una estación usando pipeline híbrido v6 + Fallback DOM.
    Retorna diccionario con coordenadas DMS y decimales.
    """
    registro = {
        'Indice': idx + 1,
        'URL': url,
        'Nombre_Estacion': '',
        'Latitud_DMS': '',
        'Latitud_Decimal': None,
        'Longitud_DMS': '',
        'Longitud_Decimal': None,
        'Altitud_msnm': '',
        'OCR_ROI_Coords_Texto': '',
        'OCR_Pipeline_Usado': '',
        'OCR_Score': 0,
        'DOM_Fallback_Usado': False,
        'Estado': 'Pendiente'
    }

    if not url or not url.startswith('http'):
        registro['Estado'] = 'URL no válida'
        return registro

    try:
        # Cargar la página web
        await page.goto(url, wait_until='domcontentloaded', timeout=25000)
        await page.wait_for_timeout(2000)

        # ESTABLECER ZOOM AL 135%
        await page.evaluate("document.body.style.zoom = '1.35'")
        await page.wait_for_timeout(600)

        # ZONA 1: COORDENADAS (clip fijo usado en scraper.py)
        clip_coords = {'x': 405, 'y': 208, 'width': 215, 'height': 156}
        ruta_roi_coords = os.path.join(carpeta_capturas, f"estacion_{idx + 1}_ROI_coords.png")
        await page.screenshot(path=ruta_roi_coords, clip=clip_coords)

        # EXTRACCIÓN DE TEXTO COMPLEMENTARIO DEL DOM
        texto_dom = ""
        for frame in page.frames:
            try:
                c = await frame.content()
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(c, 'html.parser')
                texto_dom += " " + ' '.join(soup.get_text(separator=' ').split())
            except Exception:
                pass
        
        # PIPELINE HÍBRIDO OCR: v1, v2, v3, v4
        ocr_v1 = ""
        ocr_v2 = ""
        ocr_v3 = ""
        ocr_v4 = ""
        
        if HAS_OCR:
            ocr_v2 = preprocesar_imagen_ocr_v2(ruta_roi_coords)
            ocr_v1 = preprocesar_imagen_ocr_v1(ruta_roi_coords)
            ocr_v3 = preprocesar_imagen_ocr_v3(ruta_roi_coords)
            ocr_v4 = preprocesar_imagen_ocr_v4_psm_selectivo(ruta_roi_coords)
            
            registro['OCR_ROI_Coords_Texto'] = ' '.join((ocr_v1 + " " + ocr_v2 + " " + ocr_v3 + " " + ocr_v4).split())

        # Parsear los 4 pipelines OCR
        def parsear_pipeline(ocr_texto, dom_texto):
            texto_ocr_corregido = corregir_texto_ocr(ocr_texto)
            texto_dom_corregido = corregir_texto_ocr(dom_texto)
            texto_total = f"{texto_dom_corregido} {texto_ocr_corregido}"
            
            lat_dms = extraer_dms(texto_ocr_corregido, 'LAT') or extraer_dms(texto_total, 'LAT')
            lon_dms = extraer_dms(texto_ocr_corregido, 'LON') or extraer_dms(texto_total, 'LON')
            
            return lat_dms, lon_dms
        
        lat_v1, lon_v1 = parsear_pipeline(ocr_v1, texto_dom)
        lat_v2, lon_v2 = parsear_pipeline(ocr_v2, texto_dom)
        lat_v3, lon_v3 = parsear_pipeline(ocr_v3, texto_dom)
        lat_v4, lon_v4 = parsear_pipeline(ocr_v4, texto_dom)

        # Validar y elegir mejor de los 4 pipelines OCR
        score_v1 = validar_coordenadas(lat_v1, lon_v1, ocr_v1, texto_dom)
        score_v2 = validar_coordenadas(lat_v2, lon_v2, ocr_v2, texto_dom)
        score_v3 = validar_coordenadas(lat_v3, lon_v3, ocr_v3, texto_dom)
        score_v4 = validar_coordenadas(lat_v4, lon_v4, ocr_v4, texto_dom)

        scores = {'v1': score_v1, 'v2': score_v2, 'v3': score_v3, 'v4': score_v4}
        mejor_pipeline = max(scores, key=scores.get)
        mejor_score = scores[mejor_pipeline]
        
        if mejor_pipeline == 'v1':
            lat_dms, lon_dms = lat_v1, lon_v1
        elif mejor_pipeline == 'v2':
            lat_dms, lon_dms = lat_v2, lon_v2
        elif mejor_pipeline == 'v3':
            lat_dms, lon_dms = lat_v3, lon_v3
        else:
            lat_dms, lon_dms = lat_v4, lon_v4

        registro['OCR_Pipeline_Usado'] = mejor_pipeline
        registro['OCR_Score'] = mejor_score

        # FALLBACK DOM: Si score OCR < 50, intentar extraer del HTML directamente
        if mejor_score < 50:
            print(f"  [DOM Fallback] Score OCR bajo ({mejor_score}), intentando extracción DOM...")
            lat_dom, lon_dom = await extraer_coordenadas_dom(page, url)
            
            if lat_dom or lon_dom:
                score_dom = validar_coordenadas(lat_dom, lon_dom, "", texto_dom)
                if score_dom > mejor_score:
                    lat_dms, lon_dms = lat_dom, lon_dom
                    registro['OCR_Pipeline_Usado'] = 'dom_fallback'
                    registro['OCR_Score'] = score_dom
                    registro['DOM_Fallback_Usado'] = True
                    print(f"  [DOM Fallback] ¡Éxito! Score: {score_dom}")
                else:
                    print(f"  [DOM Fallback] Score DOM ({score_dom}) no supera OCR ({mejor_score})")
            else:
                print(f"  [DOM Fallback] No se encontraron coordenadas en DOM")

        if lat_dms:
            registro['Latitud_DMS'] = lat_dms
            registro['Latitud_Decimal'] = dms_a_decimal(lat_dms)

        if lon_dms:
            registro['Longitud_DMS'] = lon_dms
            registro['Longitud_Decimal'] = dms_a_decimal(lon_dms)

        # Altitud msnm
        m_alt = re.search(r'Altitud:?\s*([0-9]+)\s*msnm', f"{ocr_v1} {ocr_v2} {ocr_v3} {ocr_v4} {texto_dom}", re.IGNORECASE)
        if m_alt:
            registro['Altitud_msnm'] = m_alt.group(1).strip()

        # Nombre de estación
        texto_total = f"{ocr_v1} {ocr_v2} {ocr_v3} {ocr_v4} {texto_dom}"
        m_nom = re.search(r'Estaci[oó]n\s+(?:Meteorol[oó]gica\s+)?([^\n\r"-]+)', texto_total, re.IGNORECASE)
        if m_nom:
            registro['Nombre_Estacion'] = m_nom.group(1).strip()

        registro['Estado'] = 'Éxito'

    except Exception as e:
        registro['Estado'] = f'Error: {str(e)}'

    return registro


async def main():
    archivo_entrada = 'Estaciones.csv'
    archivo_salida = 'coordenadas_estaciones_refinadas.csv'
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    carpeta_capturas = f'capturas_coords_{timestamp_str}'

    if not os.path.exists(carpeta_capturas):
        os.makedirs(carpeta_capturas)

    if not os.path.exists(archivo_entrada):
        print(f"Error: No se encontró el archivo '{archivo_entrada}'.")
        return

    try:
        df_estaciones = pd.read_csv(archivo_entrada, sep=';')
    except Exception as e:
        print(f"Error al leer el archivo CSV: {e}")
        return

    total = len(df_estaciones)
    resultados = []

    print(f"Iniciando extracción de coordenadas para {total} estaciones...")
    print(f"Pipeline híbrido v6: v1+v2+v3+v4 (PSM Selectivo) + Fallback DOM (score<50)")
    print(f"Capturas se guardarán en: {carpeta_capturas}")
    print(f"Archivo de salida: {archivo_salida}")
    print("-" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=3.0
        )
        page = await context.new_page()

        for idx, row in df_estaciones.iterrows():
            region = str(row.get('Region', '')).strip()
            url = str(row.get('Estacion', '')).strip()

            print(f"[{idx + 1}/{total}] Procesando: {url}")
            
            registro = await extraer_coordenadas_estacion(page, url, idx, carpeta_capturas)
            registro['Region'] = region
            resultados.append(registro)

            if registro['Latitud_Decimal'] is not None and registro['Longitud_Decimal'] is not None:
                dom_mark = " [DOM]" if registro.get('DOM_Fallback_Usado') else ""
                print(f"  [OK] Coordenadas: {registro['Latitud_Decimal']}, {registro['Longitud_Decimal']} "
                      f"({registro['Latitud_DMS']}, {registro['Longitud_DMS']}) "
                      f"[Pipeline: {registro['OCR_Pipeline_Usado']}, Score: {registro['OCR_Score']}]" + dom_mark)
            else:
                print(f"  [FAIL] {registro['Estado']} [Pipeline: {registro['OCR_Pipeline_Usado']}, Score: {registro['OCR_Score']}]")

            if (idx + 1) % 10 == 0:
                df_progresivo = pd.DataFrame(resultados)
                df_progresivo.to_csv(archivo_salida, index=False, encoding='utf-8-sig')
                print(f"  -> Progreso guardado en {archivo_salida}")

        await browser.close()

    df_final = pd.DataFrame(resultados)
    df_final.to_csv(archivo_salida, index=False, encoding='utf-8-sig')
    
    exitosos = len(df_final[df_final['Estado'] == 'Éxito'])
    con_coords = len(df_final[df_final['Latitud_Decimal'].notna() & df_final['Longitud_Decimal'].notna()])
    v1_usados = len(df_final[df_final['OCR_Pipeline_Usado'] == 'v1'])
    v2_usados = len(df_final[df_final['OCR_Pipeline_Usado'] == 'v2'])
    v3_usados = len(df_final[df_final['OCR_Pipeline_Usado'] == 'v3'])
    v4_usados = len(df_final[df_final['OCR_Pipeline_Usado'] == 'v4'])
    dom_usados = len(df_final[df_final['OCR_Pipeline_Usado'] == 'dom_fallback'])
    
    print("-" * 60)
    print(f"[OK] Proceso finalizado!")
    print(f"   Total estaciones: {total}")
    print(f"   Procesados con éxito: {exitosos}")
    print(f"   Con coordenadas válidas: {con_coords}")
    print(f"   Pipeline v1 usado: {v1_usados}")
    print(f"   Pipeline v2 usado: {v2_usados}")
    print(f"   Pipeline v3 usado: {v3_usados}")
    print(f"   Pipeline v4 (PSM Selectivo) usado: {v4_usados}")
    print(f"   Pipeline DOM Fallback usado: {dom_usados}")
    print(f"   Archivo generado: {archivo_salida}")
    print(f"   Capturas en: {carpeta_capturas}")


if __name__ == '__main__':
    asyncio.run(main())