import pandas as pd
import re
import os
import asyncio
import time
from datetime import datetime

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Instala Playwright con: pip install playwright && playwright install chromium")

try:
    import pytesseract
    from PIL import Image, ImageEnhance
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("Aviso: pytesseract/PIL no están instalados. Para usar OCR ejecuta: pip install pytesseract pillow")

def preprocesar_imagen_ocr(ruta_img):
    """
    Mejora la imagen para maximizar la tasa de acierto del motor Tesseract OCR.
    Aplica reescalado LANCZOS x2.5, escala de grises y aumento de contraste.
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
        print(f"  [Aviso OCR] Error al procesar {ruta_img}: {e}")
        return ""

def extraer_dms_robusto(texto, tipo='LAT'):
    """
    Extrae Latitud o Longitud en formato DMS desde la cadena OCR_ROI_Coords_Texto.
    Tolera artefactos comunes de OCR en el símbolo de grados (0, %, o, O, º, °, *, espacios).
    """
    if not texto or not isinstance(texto, str):
        return None
    
    t = texto.replace("´", "'").replace("`", "'").replace("’", "'").replace("”", '"').replace("“", '"')
    
    deg_symbols = r'[°ºoO%0\*\s]+'
    min_symbols = r'[\'\s]+'
    sec_symbols = r'[\"\s]*'
    
    if tipo == 'LAT':
        pattern = r'(?:Latitud:?\s*)?([0-9]{1,2})' + deg_symbols + r'([0-9]{1,2})' + min_symbols + r'([0-9]{1,2}(?:\.[0-9]+)?)' + sec_symbols + r'([NS])'
    else:
        pattern = r'(?:Longitud:?\s*)?([0-9]{1,3})' + deg_symbols + r'([0-9]{1,2})' + min_symbols + r'([0-9]{1,2}(?:\.[0-9]+)?)' + sec_symbols + r'([OWE])'
        
    m = re.search(pattern, t, re.IGNORECASE)
    if m:
        deg, mins, secs, direction = m.group(1), m.group(2), m.group(3), m.group(4).upper()
        return f'{deg}° {mins}\' {secs}" {direction}'
    return None

def dms_a_decimal(dms_str):
    """
    Convierte coordenadas en formato DMS (Grados, Minutos, Segundos) a grados decimales.
    Asigna signo negativo (-) para direcciones Oeste (O/W) o Sur (S).
    """
    if not dms_str or not isinstance(dms_str, str):
        return None
    
    clean_str = dms_str.replace("´", "'").replace("`", "'").replace("’", "'").replace("”", '"').replace("“", '"')
    pattern = r'([0-9]{1,3})[°ºoO%0\*\s]+([0-9]{1,2})[\'\s]+([0-9]{1,2}(?:\.[0-9]+)?)[\"\s]*([NSOWE])?'
    match = re.search(pattern, clean_str, re.IGNORECASE)
    
    if not match:
        return None
        
    deg = float(match.group(1))
    m = float(match.group(2))
    s = float(match.group(3))
    direction = match.group(4).upper() if match.group(4) else ''
    
    decimal = deg + (m / 60.0) + (s / 3600.0)
    if direction in ['O', 'W', 'S']:
        decimal = -decimal
        
    return round(decimal, 6)

def extraer_valor_lluvia(texto):
    """
    Extrae la cantidad numérica en mm de lluvia desde una cadena OCR.
    """
    if not texto:
        return None
    m = re.search(r'([0-9]+[\.,][0-9]+|\b[0-9]+\b)\s*mm', texto, re.IGNORECASE)
    if m:
        return m.group(1).replace(',', '.').strip()
    m2 = re.search(r'([0-9]+[\.,][0-9]+)', texto)
    if m2:
        return m2.group(1).replace(',', '.').strip()
    return None

async def procesar_estaciones_final():
    archivo_entrada = 'Estaciones.csv'
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Nombres de archivos definidos
    archivo_diario_csv = 'lluviadiaria.csv'
    archivo_diario_excel = 'lluviadiaria.xlsx'
    archivo_hist_csv = 'histlluviadiaria.csv'
    archivo_hist_excel = 'histlluviadiaria.xlsx'

    carpeta_capturas = f'capturas_zoom135_{timestamp_str}'

    if not os.path.exists(carpeta_capturas):
        os.makedirs(carpeta_capturas)

    if not os.path.exists(archivo_entrada):
        print(f"Error: No se encontró el archivo '{archivo_entrada}'. Colócalo en la misma carpeta.")
        return

    try:
        df_estaciones = pd.read_csv(archivo_entrada, sep=';')
    except Exception as e:
        print(f"Error al leer el archivo CSV: {e}")
        return

    resultados = []
    total = len(df_estaciones)
    fecha_proceso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=2.0
        )
        page = await context.new_page()

        print(f"Iniciando extracción y acumulación histórica para {total} estaciones...")

        for idx, row in df_estaciones.iterrows():
            region = str(row.get('Region', '')).strip()
            url = str(row.get('Estacion', '')).strip()

            registro = {
                'Fecha_Captura': fecha_proceso,
                'Region': region,
                'URL': url,
                'Nombre_Estacion': '',
                'Latitud_DMS': '',
                'Latitud_Decimal': None,
                'Longitud_DMS': '',
                'Longitud_Decimal': None,
                'Altitud_msnm': '',
                'Lluvia_Ayer_7am_a_7am_mm': '',
                'Origen_Lluvia_ROI': '',
                'Lluvia_Desde_7am_mm': '',
                'Precip_Ultima_Hora_mm': '',
                'Temperatura_Actual_C': '',
                'Sensacion_Termica_C': '',
                'OCR_ROI_Coords_Texto': '',
                'OCR_ROI_Lluvia_Texto': '',
                'OCR_ROI_Lluvia_Op_Texto': '',
                'Ruta_Captura_Imagen': '',
                'Ruta_ROI_Coords': '',
                'Ruta_ROI_Lluvia': '',
                'Ruta_ROI_Lluvia_Op': '',
                'Estado': 'Pendiente'
            }

            if not url or not url.startswith('http'):
                registro['Estado'] = 'URL no válida'
                resultados.append(registro)
                continue

            print(f"[{idx + 1}/{total}] Procesando estación: {url}")

            try:
                # 1. Cargar la página web
                await page.goto(url, wait_until='domcontentloaded', timeout=25000)
                await page.wait_for_timeout(2000)

                # 2. ESTABLECER ZOOM AL 135%
                await page.evaluate("document.body.style.zoom = '1.35'")
                await page.wait_for_timeout(600)

                # 3. CAPTURA DE PANTALLA COMPLETA
                nombre_img_full = f"estacion_{idx + 1}_full_135pct.png"
                ruta_img_full = os.path.join(carpeta_capturas, nombre_img_full)
                await page.screenshot(path=ruta_img_full, full_page=False)
                registro['Ruta_Captura_Imagen'] = ruta_img_full

                # --- 4. ZONA 1: COORDENADAS ---
                clip_coords = {'x': 405, 'y': 208, 'width': 215, 'height': 156}
                ruta_roi_coords = os.path.join(carpeta_capturas, f"estacion_{idx + 1}_ROI_coords.png")
                await page.screenshot(path=ruta_roi_coords, clip=clip_coords)
                registro['Ruta_ROI_Coords'] = ruta_roi_coords

                # --- 5. ZONA 2: LLUVIA DE AYER (FORMATO PRINCIPAL) ---
                clip_lluvia = {'x': 870, 'y': 862, 'width': 205, 'height': 175}
                ruta_roi_lluvia = os.path.join(carpeta_capturas, f"estacion_{idx + 1}_ROI_lluvia.png")
                await page.screenshot(path=ruta_roi_lluvia, clip=clip_lluvia)
                registro['Ruta_ROI_Lluvia'] = ruta_roi_lluvia

                # --- 6. ZONA 3: LLUVIA DE AYER OP (FORMATO OPCIONAL) ---
                clip_lluvia_op = {'x': 690, 'y': 872, 'width': 266, 'height': 165}
                ruta_roi_lluvia_op = os.path.join(carpeta_capturas, f"estacion_{idx + 1}_ROI_lluvia_op.png")
                await page.screenshot(path=ruta_roi_lluvia_op, clip=clip_lluvia_op)
                registro['Ruta_ROI_Lluvia_Op'] = ruta_roi_lluvia_op

                # --- 7. PROCESAMIENTO OCR EN LOS 3 ROIs ---
                ocr_coords_txt = ""
                ocr_lluvia_txt = ""
                ocr_lluvia_op_txt = ""

                if HAS_OCR:
                    ocr_coords_txt = preprocesar_imagen_ocr(ruta_roi_coords)
                    ocr_lluvia_txt = preprocesar_imagen_ocr(ruta_roi_lluvia)
                    ocr_lluvia_op_txt = preprocesar_imagen_ocr(ruta_roi_lluvia_op)

                    registro['OCR_ROI_Coords_Texto'] = ' '.join(ocr_coords_txt.split())
                    registro['OCR_ROI_Lluvia_Texto'] = ' '.join(ocr_lluvia_txt.split())
                    registro['OCR_ROI_Lluvia_Op_Texto'] = ' '.join(ocr_lluvia_op_txt.split())

                # --- 8. EXTRACCIÓN DE TEXTO COMPLEMENTARIO DEL DOM ---
                texto_dom = ""
                for frame in page.frames:
                    try:
                        c = await frame.content()
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(c, 'html.parser')
                        texto_dom += " " + ' '.join(soup.get_text(separator=' ').split())
                    except Exception:
                        pass

                texto_total = f"{texto_dom} {ocr_coords_txt} {ocr_lluvia_txt} {ocr_lluvia_op_txt}"

                # --- A. PARSEO Y CONVERSIÓN DE COORDENADAS ---
                lat_dms = extraer_dms_robusto(ocr_coords_txt, 'LAT') or extraer_dms_robusto(texto_total, 'LAT')
                lon_dms = extraer_dms_robusto(ocr_coords_txt, 'LON') or extraer_dms_robusto(texto_total, 'LON')

                if lat_dms:
                    registro['Latitud_DMS'] = lat_dms
                    registro['Latitud_Decimal'] = dms_a_decimal(lat_dms)

                if lon_dms:
                    registro['Longitud_DMS'] = lon_dms
                    registro['Longitud_Decimal'] = dms_a_decimal(lon_dms)

                # Altitud msnm
                m_alt = re.search(r'Altitud:?\s*([0-9]+)\s*msnm', f"{ocr_coords_txt} {texto_dom}", re.IGNORECASE)
                if m_alt:
                    registro['Altitud_msnm'] = m_alt.group(1).strip()

                # --- B. LÓGICA DE PRIORIDAD PARA LLUVIA DE AYER (ROI 1 -> ROI 2 Op -> DOM) ---
                lluvia_val = extraer_valor_lluvia(ocr_lluvia_txt)
                if lluvia_val:
                    registro['Lluvia_Ayer_7am_a_7am_mm'] = lluvia_val
                    registro['Origen_Lluvia_ROI'] = 'ROI_Lluvia_Estandar'
                else:
                    lluvia_op_val = extraer_valor_lluvia(ocr_lluvia_op_txt)
                    if lluvia_op_val:
                        registro['Lluvia_Ayer_7am_a_7am_mm'] = lluvia_op_val
                        registro['Origen_Lluvia_ROI'] = 'ROI_Lluvia_Opcional'
                    else:
                        m_lluvia_dom = re.search(r'De\s+7\s*a\.?m\.?\s+de\s+ayer\s+a\s+7\s*a\.?m\.?\s+de\s+hoy:?\s*([0-9\.,]+)\s*mm', texto_dom, re.IGNORECASE)
                        if m_lluvia_dom:
                            registro['Lluvia_Ayer_7am_a_7am_mm'] = m_lluvia_dom.group(1).replace(',', '.').strip()
                            registro['Origen_Lluvia_ROI'] = 'DOM_HTML'

                # --- C. OTROS CAMPOS DE LA ESTACIÓN ---
                m_nom = re.search(r'Estació[nñ]\s+(?:Meteorológica\s+)?([^\n\r–-]+)', texto_total, re.IGNORECASE)
                if m_nom:
                    registro['Nombre_Estacion'] = m_nom.group(1).strip()

                m_lluvia_hoy = re.search(r'Desde\s+las?\s+7\s*a\.?m\.?:?\s*([0-9\.,]+)\s*mm', texto_total, re.IGNORECASE)
                if m_lluvia_hoy:
                    registro['Lluvia_Desde_7am_mm'] = m_lluvia_hoy.group(1).replace(',', '.').strip()

                m_temp = re.search(r'Temperatura\s+Actual:?\s*([0-9\.,]+)\s*°?C', texto_total, re.IGNORECASE)
                if m_temp:
                    registro['Temperatura_Actual_C'] = m_temp.group(1).replace(',', '.').strip()

                m_sens = re.search(r'Sensaci[oó]n\s+t[eé]rmica(?:\s+Actual)?:?\s*([0-9\.,]+)\s*°?C', texto_total, re.IGNORECASE)
                if m_sens:
                    registro['Sensacion_Termica_C'] = m_sens.group(1).replace(',', '.').strip()

                registro['Estado'] = 'Éxito'

            except Exception as e:
                registro['Estado'] = f'Error: {str(e)}'

            resultados.append(registro)

            # Guardado progresivo del lote del día en lluviadiaria.csv
            for intento in range(3):
                try:
                    df_progresivo = pd.DataFrame(resultados)
                    df_progresivo.to_csv(archivo_diario_csv, index=False, encoding='utf-8-sig')
                    break
                except PermissionError:
                    time.sleep(1)

        await browser.close()

    # Dataframe con los datos extraídos en la ejecución actual
    df_actual = pd.DataFrame(resultados)

    # 1. Guardar archivos del día actual (lluviadiaria.csv y lluviadiaria.xlsx)
    df_actual.to_csv(archivo_diario_csv, index=False, encoding='utf-8-sig')
    try:
        df_actual.to_excel(archivo_diario_excel, index=False)
    except Exception as e:
        print(f"Aviso al guardar {archivo_diario_excel}: {e}")

    # 2. Acumular/Apendizar al archivo histórico CSV (histlluviadiaria.csv)
    if os.path.exists(archivo_hist_csv):
        try:
            df_hist_csv = pd.read_csv(archivo_hist_csv)
            df_hist_csv_updated = pd.concat([df_hist_csv, df_actual], ignore_index=True)
        except Exception:
            df_hist_csv_updated = df_actual
    else:
        df_hist_csv_updated = df_actual

    df_hist_csv_updated.to_csv(archivo_hist_csv, index=False, encoding='utf-8-sig')

    # 3. Acumular/Apendizar al archivo histórico Excel (histlluviadiaria.xlsx)
    if os.path.exists(archivo_hist_excel):
        try:
            df_hist_excel = pd.read_excel(archivo_hist_excel)
            df_hist_excel_updated = pd.concat([df_hist_excel, df_actual], ignore_index=True)
        except Exception:
            df_hist_excel_updated = df_actual
    else:
        df_hist_excel_updated = df_actual

    try:
        df_hist_excel_updated.to_excel(archivo_hist_excel, index=False)
    except Exception as e:
        print(f"Aviso al guardar {archivo_hist_excel}: {e}")

    print(f"\n¡Proceso finalizado! Datos del día guardados en '{archivo_diario_csv}' y '{archivo_diario_excel}'.")
    print(f"Acumulación histórica actualizada en '{archivo_hist_csv}' y '{archivo_hist_excel}'.")

if __name__ == '__main__':
    asyncio.run(procesar_estaciones_final())