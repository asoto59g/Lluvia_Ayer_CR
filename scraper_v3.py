#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scraper_v3.py - Extractor Meteorológico de Lluvia IMN Costa Rica (Versión 3)
Diseñado para ejecución local y GitHub Actions (Cron diario a las 9:00 AM UTC-6).
Compatible con generador de mapas Thiessen / Streamlit leyendo desde histlluviadiaria.csv.
"""

import os
import sys
import io
import re
import time
import asyncio
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from pathlib import Path

import pandas as pd
import numpy as np
from PIL import Image, ImageEnhance

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Error: Requiere Playwright. Instalar con: pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("Aviso: pytesseract no instalado. Instalar con: pip install pytesseract pillow")

# ============================================================
# CONFIGURACIÓN
# ============================================================

@dataclass
class Config:
    # Archivos de datos
    archivo_estaciones: str = "Estaciones.csv"
    archivo_diario_csv: str = "lluviadiaria.csv"
    archivo_hist_csv: str = "histlluviadiaria.csv"
    
    # Parámetros de navegación Playwright
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    device_scale_factor: float = 2.0
    zoom_level: str = "1.35"
    timeout_ms: int = 20000
    wait_after_load_ms: int = 1800
    wait_after_zoom_ms: int = 500
    
    # Concurrencia segura (Worker Queue Pattern)
    num_workers: int = 3  # Ideal para runners de 2 vCPUs (GitHub Actions)
    max_retries: int = 2
    
    # Coordenadas de recortes (ROIs) a zoom 1.35x y DSF 2.0
    roi_lluvia: Dict[str, int] = None
    roi_lluvia_op: Dict[str, int] = None
    
    # Guardado de capturas a disco (False ahorra cientos de MBs en GitHub)
    guardar_imagenes_disco: bool = False
    carpeta_capturas: str = "capturas_recientes"
    
    # Tesseract OCR
    ocr_lang: str = "spa"

    def __post_init__(self):
        if self.roi_lluvia is None:
            self.roi_lluvia = {"x": 870, "y": 862, "width": 205, "height": 175}
        if self.roi_lluvia_op is None:
            self.roi_lluvia_op = {"x": 690, "y": 872, "width": 266, "height": 165}


CONFIG = Config()

# ============================================================
# LOGGING
# ============================================================

def setup_logger():
    logger = logging.getLogger("scraper_v3")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

LOGGER = setup_logger()

# ============================================================
# ESTRUCTURAS DE DATOS
# ============================================================

@dataclass
class EstacionInfo:
    Indice: int
    URL: str
    Nombre_Estacion: str
    Latitud_DMS: str
    Longitud_DMS: str
    Altitud_msnm: str
    Region: str
    Latitud_Decimal: float
    Longitud_Decimal: float

@dataclass
class RegistroLluvia:
    Fecha_Captura: str               # Timestamp ISO corrida (ej. 2026-09-30 09:05:00)
    Fecha_Datos: str                 # Fecha meteorológica de los datos (ayer, YYYY-MM-DD)
    Indice: int
    Nombre_Estacion: str
    Region: str
    Latitud_Decimal: float
    Longitud_Decimal: float
    Altitud_msnm: str
    URL: str
    Lluvia_Ayer_7am_a_7am_mm: Optional[float]
    Origen_Lluvia_ROI: str           # ROI_Lluvia_Estandar, ROI_Lluvia_Opcional, DOM_HTML, No_Detectado
    Lluvia_Desde_7am_mm: Optional[float]
    Temperatura_Actual_C: Optional[float]
    Sensacion_Termica_C: Optional[float]
    OCR_Texto: str
    Estado: str                      # Éxito, Sin_Dato, Error_Timeout, etc.
    Duracion_Segundos: float

# ============================================================
# PREPROCESAMIENTO Y OCR OPTIMIZADO (EN MEMORIA)
# ============================================================

def optimizar_imagen_para_ocr(img_pil: Image.Image) -> Image.Image:
    """
    Preprocesamiento LANCZOS 2.5x + Escala de grises + Contraste 2.0x.
    Preserva los gradientes de dígitos pequeños sin pérdida destructiva por binarización.
    """
    w, h = img_pil.size
    img_large = img_pil.resize((int(w * 2.5), int(h * 2.5)), Image.Resampling.LANCZOS)
    img_gray = img_large.convert("L")
    enhancer = ImageEnhance.Contrast(img_gray)
    return enhancer.enhance(2.0)


def ejecutar_ocr_en_memoria(img_bytes: bytes, lang: str = "spa") -> str:
    """Ejecuta Tesseract en memoria sin tocar disco."""
    if not HAS_OCR or not img_bytes:
        return ""
    try:
        img_raw = Image.open(io.BytesIO(img_bytes))
        img_prep = optimizar_imagen_para_ocr(img_raw)
        texto = pytesseract.image_to_string(img_prep, lang=lang, config="--psm 6")
        if len(texto.strip()) < 3:
            texto = pytesseract.image_to_string(img_prep, lang=lang, config="--psm 11")
        return texto.strip()
    except Exception as e:
        LOGGER.debug(f"Error OCR: {e}")
        return ""


def extraer_valor_lluvia_seguro(texto: str) -> Optional[float]:
    """
    Extrae y valida el valor numérico en mm de lluvia (rango Costa Rica 0.0 - 500.0 mm).
    Escanea las líneas de abajo hacia arriba (donde típicamente se sitúa la cifra de precipitación).
    """
    if not texto:
        return None

    lines = [line.strip() for line in texto.splitlines() if line.strip()]
    for line in reversed(lines):
        # 1. Buscar número con decimales (ej. 37,2 o 0.0 o 14,4 mm)
        m_dec = re.search(r'([0-9]{1,3}[\.,][0-9]{1,2})\s*(?:mm)?', line, re.IGNORECASE)
        if m_dec:
            try:
                val = float(m_dec.group(1).replace(",", "."))
                if 0.0 <= val <= 500.0:
                    return val
            except ValueError:
                pass

        # 2. Buscar número entero seguido de mm (ej. 15 mm, 0 mm)
        m_int = re.search(r'\b([0-9]{1,3})\s*mm\b', line, re.IGNORECASE)
        if m_int:
            try:
                val = float(m_int.group(1))
                if 0.0 <= val <= 500.0:
                    return val
            except ValueError:
                pass

    return None

# ============================================================
# LECTURA DEL CSV BASE (Estaciones.csv)
# ============================================================

def cargar_estaciones_base(ruta_csv: str) -> List[EstacionInfo]:
    """Carga y valida las 138 estaciones base desde Estaciones.csv."""
    if not os.path.exists(ruta_csv):
        raise FileNotFoundError(f"No se encontró el archivo base de estaciones: {ruta_csv}")
    
    # Probar encodings comunes (latin-1 / cp1252 / utf-8)
    df = None
    for enc in ["latin-1", "cp1252", "utf-8", "utf-8-sig"]:
        try:
            df = pd.read_csv(ruta_csv, encoding=enc)
            break
        except Exception:
            continue
            
    if df is None:
        raise ValueError(f"No fue posible leer {ruta_csv} con encodings soportados.")

    estaciones = []
    for _, row in df.iterrows():
        try:
            lat = float(str(row["Latitud_Decimal"]).replace(",", ".").strip())
            lon = float(str(row["Longitud_Decimal"]).replace(",", ".").strip())
            idx = int(row.get("Indice", len(estaciones) + 1))
        except (ValueError, KeyError) as e:
            LOGGER.warning(f"Fila omitida por coordenadas inválidas: {row.to_dict()} ({e})")
            continue

        estaciones.append(EstacionInfo(
            Indice=idx,
            URL=str(row.get("URL", "")).strip(),
            Nombre_Estacion=str(row.get("Nombre_Estacion", "")).strip(),
            Latitud_DMS=str(row.get("Latitud_DMS", "")).strip(),
            Longitud_DMS=str(row.get("Longitud_DMS", "")).strip(),
            Altitud_msnm=str(row.get("Altitud_msnm", "")).strip(),
            Region=str(row.get("Region", "")).strip(),
            Latitud_Decimal=lat,
            Longitud_Decimal=lon
        ))

    return estaciones

# ============================================================
# WORKER PIPELINE (PLAYWRIGHT + LAZY OCR)
# ============================================================

async def procesar_estacion_worker(
    page,
    estacion: EstacionInfo,
    config: Config,
    fecha_captura: str,
    fecha_datos: str
) -> RegistroLluvia:
    """Procesa una estación en una página Playwright aislada y limpia."""
    t0 = time.time()
    url = estacion.URL
    
    registro = RegistroLluvia(
        Fecha_Captura=fecha_captura,
        Fecha_Datos=fecha_datos,
        Indice=estacion.Indice,
        Nombre_Estacion=estacion.Nombre_Estacion,
        Region=estacion.Region,
        Latitud_Decimal=estacion.Latitud_Decimal,
        Longitud_Decimal=estacion.Longitud_Decimal,
        Altitud_msnm=estacion.Altitud_msnm,
        URL=url,
        Lluvia_Ayer_7am_a_7am_mm=None,
        Origen_Lluvia_ROI="No_Detectado",
        Lluvia_Desde_7am_mm=None,
        Temperatura_Actual_C=None,
        Sensacion_Termica_C=None,
        OCR_Texto="",
        Estado="Pendiente",
        Duracion_Segundos=0.0
    )

    if not url or not url.startswith("http"):
        registro.Estado = "URL_Invalida"
        registro.Duracion_Segundos = round(time.time() - t0, 2)
        return registro

    try:
        # 1. Navegación con reintentos
        cargado = False
        for intento in range(config.max_retries):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)
                cargado = True
                break
            except Exception:
                if intento < config.max_retries - 1:
                    await asyncio.sleep(1.0)
                    
        if not cargado:
            registro.Estado = "Error_Timeout"
            registro.Duracion_Segundos = round(time.time() - t0, 2)
            return registro

        # 2. Aplicar zoom y pequeña pausa
        await page.wait_for_timeout(config.wait_after_load_ms)
        await page.evaluate(f"document.body.style.zoom = '{config.zoom_level}'")
        await page.wait_for_timeout(config.wait_after_zoom_ms)

        # 3. FAST PATH: ROI Estándar de lluvia directamente a memoria
        img_bytes_std = await page.screenshot(clip=config.roi_lluvia, type="png")
        ocr_std = ejecutar_ocr_en_memoria(img_bytes_std, lang=config.ocr_lang)
        lluvia_val = extraer_valor_lluvia_seguro(ocr_std)
        
        texto_acumulado = ocr_std
        origen_detectado = ""

        if lluvia_val is not None:
            registro.Lluvia_Ayer_7am_a_7am_mm = lluvia_val
            registro.Origen_Lluvia_ROI = "ROI_Lluvia_Estandar"
            origen_detectado = "ROI_Lluvia_Estandar"
        else:
            # 4. LAZY ESCALATION: ROI Opcional solo si el estándar no dio resultado
            img_bytes_op = await page.screenshot(clip=config.roi_lluvia_op, type="png")
            ocr_op = ejecutar_ocr_en_memoria(img_bytes_op, lang=config.ocr_lang)
            texto_acumulado += " | " + ocr_op
            lluvia_val_op = extraer_valor_lluvia_seguro(ocr_op)
            
            if lluvia_val_op is not None:
                registro.Lluvia_Ayer_7am_a_7am_mm = lluvia_val_op
                registro.Origen_Lluvia_ROI = "ROI_Lluvia_Opcional"
                origen_detectado = "ROI_Lluvia_Opcional"
            else:
                # 5. DOM FALLBACK RÁPIDO (solo texto explícito)
                try:
                    c = await page.content()
                    m_dom = re.search(r'De\s+7\s*a\.?m\.?\s+de\s+ayer\s+a\s+7\s*a\.?m\.?\s+de\s+hoy:?\s*([0-9\.,]+)\s*mm', c, re.IGNORECASE)
                    if m_dom:
                        val_dom = float(m_dom.group(1).replace(",", ".").strip())
                        registro.Lluvia_Ayer_7am_a_7am_mm = val_dom
                        registro.Origen_Lluvia_ROI = "DOM_HTML"
                        origen_detectado = "DOM_HTML"
                except Exception:
                    pass
                # 6. FULL-PANEL FALLBACK OCR (captura completa)
                if registro.Lluvia_Ayer_7am_a_7am_mm is None:
                    img_bytes_full = await page.screenshot(type='png')
                    ocr_full = ejecutar_ocr_en_memoria(img_bytes_full, lang=config.ocr_lang)
                    texto_acumulado += " | " + ocr_full
                    lluvia_val_full = extraer_valor_lluvia_seguro(ocr_full)
                    if lluvia_val_full is not None:
                        registro.Lluvia_Ayer_7am_a_7am_mm = lluvia_val_full
                        registro.Origen_Lluvia_ROI = "ROI_Full_Panel"
                        origen_detectado = "ROI_Full_Panel"

        # 6. Extracción de datos meteorológicos adicionales del DOM si están disponibles
        try:
            page_text = await page.inner_text("body")
            m_hoy = re.search(r'Desde\s+las?\s+7\s*a\.?m\.?:?\s*([0-9\.,]+)\s*mm', page_text, re.IGNORECASE)
            if m_hoy:
                registro.Lluvia_Desde_7am_mm = float(m_hoy.group(1).replace(",", ".").strip())
                
            m_temp = re.search(r'Temperatura\s+Actual:?\s*([0-9\.,]+)\s*°?C', page_text, re.IGNORECASE)
            if m_temp:
                registro.Temperatura_Actual_C = float(m_temp.group(1).replace(",", ".").strip())
        except Exception:
            pass

        # 7. Guardado opcional a disco si fue configurado
        if config.guardar_imagenes_disco:
            out_dir = Path(config.carpeta_capturas)
            out_dir.mkdir(parents=True, exist_ok=True)
            with open(out_dir / f"estacion_{estacion.Indice}_ROI_lluvia.png", "wb") as f:
                f.write(img_bytes_std)

        registro.OCR_Texto = texto_acumulado[:150]
        registro.Estado = "Éxito" if registro.Lluvia_Ayer_7am_a_7am_mm is not None else "Sin_Dato_Lluvia"

    except Exception as e:
        registro.Estado = f"Error: {type(e).__name__}"
        LOGGER.debug(f"Excepción en estación {estacion.Indice} ({url}): {e}")

    registro.Duracion_Segundos = round(time.time() - t0, 2)
    return registro


async def worker_loop(
    worker_id: int,
    browser,
    queue: asyncio.Queue,
    resultados: List[RegistroLluvia],
    config: Config,
    fecha_captura: str,
    fecha_datos: str,
    total_estaciones: int
):
    """Worker dedicado con su propio Context y Page aislado."""
    context = await browser.new_context(
        viewport={"width": config.viewport_width, "height": config.viewport_height},
        device_scale_factor=config.device_scale_factor
    )
    page = await context.new_page()

    try:
        while not queue.empty():
            try:
                item_idx, estacion = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            reg = await procesar_estacion_worker(page, estacion, config, fecha_captura, fecha_datos)
            resultados.append(reg)
            queue.task_done()

            # Logging conciso
            lluvia_str = f"{reg.Lluvia_Ayer_7am_a_7am_mm:.1f} mm" if reg.Lluvia_Ayer_7am_a_7am_mm is not None else "N/D"
            LOGGER.info(
                f"[{item_idx}/{total_estaciones}] (W{worker_id}) {estacion.Nombre_Estacion[:28]:<28} "
                f"-> Lluvia: {lluvia_str:<8} [{reg.Origen_Lluvia_ROI}] ({reg.Duracion_Segundos}s)"
            )
    finally:
        await context.close()

# ============================================================
# PERSISTENCIA Y ACTUALIZACIÓN HISTÓRICA DEDUPLICADA
# ============================================================

def guardar_archivos_salida(registros: List[RegistroLluvia], config: Config):
    """
    Guarda lluviadiaria.csv y actualiza histlluviadiaria.csv garantizando idempotencia.
    Deduplica por (Fecha_Datos, URL) para evitar duplicar registros si se corre varias veces el mismo día.
    """
    df_nuevo = pd.DataFrame([asdict(r) for r in registros])
    df_nuevo.sort_values(by="Indice", inplace=True)

    # 1. Guardar archivo diario del día
    df_nuevo.to_csv(config.archivo_diario_csv, index=False, encoding="utf-8-sig")
    LOGGER.info(f"Archivo diario guardado exitosamente: '{config.archivo_diario_csv}' ({len(df_nuevo)} registros)")

    # 2. Actualizar o crear histórico
    if os.path.exists(config.archivo_hist_csv):
        try:
            df_hist = pd.read_csv(config.archivo_hist_csv, encoding="utf-8-sig")
            
            # Si no existía Fecha_Datos en registros antiguos, poblar con base en Fecha_Captura
            if "Fecha_Datos" not in df_hist.columns and "Fecha_Captura" in df_hist.columns:
                df_hist["Fecha_Datos"] = pd.to_datetime(df_hist["Fecha_Captura"], errors="coerce").dt.strftime("%Y-%m-%d")

            # Concatenar y deduplicar manteniendo la última corrida para la misma fecha y URL
            df_combinado = pd.concat([df_hist, df_nuevo], ignore_index=True)
            df_combinado.drop_duplicates(subset=["Fecha_Datos", "URL"], keep="last", inplace=True)
            df_hist_final = df_combinado
        except Exception as e:
            LOGGER.warning(f"Error al leer histórico existente ({e}). Se creará con los datos nuevos.")
            df_hist_final = df_nuevo
    else:
        df_hist_final = df_nuevo

    # Guardar de forma segura: escribir primero a un archivo temporal y luego reemplazar
    from pathlib import Path
    temp_path = Path(config.archivo_hist_csv).with_suffix('.tmp')
    try:
        df_hist_final.to_csv(temp_path, index=False, encoding="utf-8-sig")
        temp_path.replace(config.archivo_hist_csv)
        LOGGER.info(f"Histórico actualizado exitosamente (uso archivo temporal): '{config.archivo_hist_csv}' ({len(df_hist_final)} filas totales)")
    except Exception as save_err:
        LOGGER.error(f"Error al guardar histórico en archivo temporal: {save_err}")
        # Como fallback, intentar sobrescribir directamente
        try:
            df_hist_final.to_csv(config.archivo_hist_csv, index=False, encoding="utf-8-sig")
            LOGGER.info(f"Histórico sobrescrito directamente después de fallo temporal: '{config.archivo_hist_csv}' ({len(df_hist_final)} filas)")
        except Exception as e2:
            LOGGER.critical(f"Fallo crítico al guardar histórico: {e2}")

# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

async def ejecutar_scraper_v3(limite: Optional[int] = None):
    inicio_total = time.time()
    config = CONFIG
    
    # Fechas de referencia
    ahora = datetime.now()
    fecha_captura = ahora.strftime("%Y-%m-%d %H:%M:%S")
    # Lluvia 24h corresponde a ayer (fecha de cierre de la medición 7am a 7am)
    fecha_datos = (ahora - timedelta(days=1)).strftime("%Y-%m-%d")

    LOGGER.info("=" * 70)
    LOGGER.info(" INICIANDO SCRAPER DE LLUVIA V3 (IMN COSTA RICA)")
    LOGGER.info(f" Fecha de corrida: {fecha_captura} | Fecha de datos: {fecha_datos}")
    LOGGER.info(f" Workers: {config.num_workers} | Fast-Path OCR: Activo")
    LOGGER.info("=" * 70)

    # 1. Cargar estaciones
    estaciones = cargar_estaciones_base(config.archivo_estaciones)
    if limite and limite > 0:
        estaciones = estaciones[:limite]
        LOGGER.info(f"Modo prueba activo: limitado a las primeras {limite} estaciones.")
    total_estaciones = len(estaciones)
    LOGGER.info(f"Se procesarán {total_estaciones} estaciones.")

    # 2. Llenar la cola de tareas
    queue = asyncio.Queue()
    for idx, est in enumerate(estaciones, start=1):
        queue.put_nowait((idx, est))

    resultados: List[RegistroLluvia] = []

    # 3. Lanzar pool de workers con Playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=config.headless,
            args=["--disable-dev-shm-usage", "--no-sandbox"]  # Flags optimizados para GitHub Actions Linux
        )

        workers = [
            asyncio.create_task(
                worker_loop(w_id, browser, queue, resultados, config, fecha_captura, fecha_datos, total_estaciones)
            )
            for w_id in range(1, config.num_workers + 1)
        ]

        await asyncio.gather(*workers)
        await browser.close()

    # 4. Guardar archivos
    guardar_archivos_salida(resultados, config)

    # 5. Métricas de resumen
    tiempo_total = round(time.time() - inicio_total, 1)
    con_lluvia = [r for r in resultados if r.Lluvia_Ayer_7am_a_7am_mm is not None]
    con_precip = [r for r in con_lluvia if r.Lluvia_Ayer_7am_a_7am_mm > 0.0]
    max_lluvia = max([r.Lluvia_Ayer_7am_a_7am_mm for r in con_lluvia], default=0.0)

    LOGGER.info("=" * 70)
    LOGGER.info(" RESUMEN DE EJECUCIÓN SCRAPER V3")
    LOGGER.info(f" Total procesadas: {len(resultados)} / {total_estaciones}")
    LOGGER.info(f" Estaciones con dato de lluvia: {len(con_lluvia)} ({len(con_lluvia)/total_estaciones*100:.1f}%)")
    LOGGER.info(f" Estaciones con lluvia > 0 mm: {len(con_precip)}")
    LOGGER.info(f" Lluvia máxima detectada: {max_lluvia:.1f} mm")
    LOGGER.info(f" Tiempo total: {tiempo_total} segundos (~{tiempo_total/60:.1f} minutos)")
    LOGGER.info("=" * 70)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Scraper meteorológico IMN Lluvia de Ayer (V3)")
    parser.add_argument("--limit", type=int, default=None, help="Limitar a N estaciones para pruebas rápidas")
    args = parser.parse_args()
    asyncio.run(ejecutar_scraper_v3(limite=args.limit))

