import pandas as pd
import numpy as np
import re
import os
import asyncio
import time
import logging
from datetime import datetime
from dataclasses import dataclass, asdict, fields, field
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

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
    print("Aviso: pytesseract/PIL no est醤 instalados. Para usar OCR ejecuta: pip install pytesseract pillow")

try:
    from scipy.ndimage import uniform_filter
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

    HAS_OCR = False
    print("Aviso: pytesseract/PIL no están instalados. Para usar OCR ejecuta: pip install pytesseract pillow")

# ============================================================
# CONFIGURACIÓN
# ============================================================

@dataclass
class Config:
    """Configuración centralizada del scraper."""
    # Archivos
    archivo_entrada: str = "Estaciones.csv"
    archivo_diario_csv: str = "lluviadiaria.csv"
    archivo_hist_csv: str = "histlluviadiaria.csv"
    
    # Carpeta capturas
    carpeta_capturas_base: str = "capturas_lluvia"
    
    # Playwright
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    device_scale_factor: float = 2.0
    zoom_level: str = "1.35"
    goto_timeout_ms: int = 25000
    wait_after_load_ms: int = 2000
    wait_after_zoom_ms: int = 600
    
    # ROIs para lluvia (coordenadas x, y, width, height)
    roi_lluvia: Dict[str, int] = None
    roi_lluvia_op: Dict[str, int] = None
    
    # Concurrencia
    max_concurrent_stations: int = 4
    
    # Reintentos
    max_retries_goto: int = 2
    max_retries_csv_write: int = 3
    
    # OCR
    ocr_lang: str = "spa"
    ocr_psm_primary: int = 6
    ocr_psm_fallback: int = 11
    ocr_upscale_factor: float = 2.5
    ocr_contrast_factor: float = 2.0

    # OCR Avanzado (Fase 1)
    ocr_enable_multi_pipeline: bool = True
    ocr_enable_layout_detection: bool = True
    ocr_enable_sauvola: bool = False
    ocr_min_score_threshold: int = 50
    ocr_pipelines: List[str] = field(default_factory=lambda: ["v1", "v2", "v4"])

    # Logging JSONL (Fase 6.3)
    log_jsonl_enabled: bool = True
    log_jsonl_path: str = "logs_scraper.jsonl"

    # Cache capturas (Fase 6.4)
    cache_enabled: bool = True

    def __post_init__(self):
        if self.roi_lluvia is None:
            self.roi_lluvia = {"x": 870, "y": 862, "width": 205, "height": 175}
        if self.roi_lluvia_op is None:
            self.roi_lluvia_op = {"x": 690, "y": 872, "width": 266, "height": 165}


# Configuración global
CONFIG = Config()
import json
import time
from datetime import datetime


def log_jsonl(evento: str, data: dict, config: Config = CONFIG):
    """Escribe una línea JSONL al archivo de log estructurado."""
    if not config.log_jsonl_enabled:
        return
    
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'evento': evento,
        **data
    }
    try:
        with open(config.log_jsonl_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    except Exception as e:
        LOGGER.debug(f'[JSONL] Error escribiendo log: {e}')


def log_estacion_procesada(registro, config: Config = CONFIG, duracion_ms: int = 0, 
                           ocr_results=None, dom_result=None):
    """Log completo de una estación procesada."""
    log_jsonl('estacion_procesada', {
        'indice': registro.Indice,
        'nombre': registro.Nombre_Estacion,
        'url': registro.URL,
        'fecha_captura': registro.Fecha_Captura,
        'estado': registro.Estado,
        'lluvia_mm': registro.Lluvia_Ayer_7am_a_7am_mm,
        'origen_lluvia': registro.Origen_Lluvia_ROI,
        'lluvia_score': registro.Lluvia_Score,
        'lluvia_pipeline': registro.Lluvia_Pipeline,
        'temperatura_c': registro.Temperatura_Actual_C,
        'duracion_ms': duracion_ms,
        'pipelines_ejecutados': [r.pipeline for r in ocr_results] if ocr_results else [],
        'dom_usado': dom_result is not None and bool(dom_result[0]) if dom_result else False,
        'dom_score': dom_result[1] if dom_result else 0,
        'captura_path': registro.Ruta_Captura_Imagen,
    }, config)



# ============================================================
# CACHE DE CAPTURAS (Fase 6.4)
# ============================================================
import hashlib
import pickle
from pathlib import Path

_cache_dir = Path("cache_capturas")
_cache_dir.mkdir(exist_ok=True)
_cache_index_path = _cache_dir / "index.pkl"
_cache_ttl_days = 7  # Time to live

def _cargar_cache_index():
    """Carga el índice de cache desde disco."""
    if _cache_index_path.exists():
        try:
            with open(_cache_index_path, 'rb') as f:
                return pickle.load(f)
        except Exception:
            pass
    return {}


def _guardar_cache_index(index):
    """Guarda el índice de cache a disco."""
    try:
        with open(_cache_index_path, 'wb') as f:
            pickle.dump(index, f)
    except Exception as e:
        LOGGER.debug(f"[Cache] Error guardando índice: {e}")

def _hash_archivo(ruta):
    """Calcula SHA256 de un archivo."""
    h = hashlib.sha256()
    try:
        with open(ruta, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None

def cache_obtener(ruta_img):
    """
    Busca en cache si la imagen ya fue procesada y no ha cambiado.
    Retorna dict con resultados OCR previos o None si no hay cache válido.
    """
    if not CONFIG.cache_enabled:
        return None
    
    hash_img = _hash_archivo(ruta_img)
    if not hash_img:
        return None
    
    index = _cargar_cache_index()
    if hash_img in index:
        entry = index[hash_img]
        # Verificar TTL
        import time
        if time.time() - entry.get('timestamp', 0) < _cache_ttl_days * 86400:
            LOGGER.info(f"  [Cache] Hit para {Path(ruta_img).name} (hash: {hash_img[:12]}...)")
            return entry.get('ocr_results')
        else:
            # Expirado
            del index[hash_img]
            _guardar_cache_index(index)
    
    LOGGER.info(f"  [Cache] Miss para {Path(ruta_img).name} (hash: {hash_img[:12]}...)")
    return None

def cache_guardar(ruta_img, ocr_results):
    """Guarda resultados OCR en cache asociados al hash de la imagen."""
    if not CONFIG.cache_enabled:
        return
    
    hash_img = _hash_archivo(ruta_img)
    if not hash_img:
        return
    
    index = _cargar_cache_index()
    index[hash_img] = {
        'timestamp': time.time(),
        'archivo': str(ruta_img),
        'ocr_results': ocr_results
    }
    _guardar_cache_index(index)
    LOGGER.debug(f"  [Cache] Guardado {Path(ruta_img).name} (hash: {hash_img[:12]}...)")




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
        
        # Contar líneas separadas (gaps verticales > 3px)
        gaps = np.diff(text_rows) > 3
        num_lineas = np.sum(gaps) + 1
        
        # Proyección vertical (suma por columna)
        v_proj = np.sum(arr_bin, axis=0)
        text_cols = np.where(v_proj > h * 0.05)[0]
        
        if len(text_cols) == 0:
            return 'auto'
        
        # Ancho y alto ocupado por texto
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
        'sparse':      ['--psm 8', '--psm 7', '--psm 13', '--psm 6'],
        'block':       ['--psm 6', '--psm 4', '--psm 3', '--psm 13'],
        'auto':        ['--psm 13', '--psm 6', '--psm 7', '--psm 8']
    }
    return configs_map.get(layout, configs_map['auto'])

def preprocesar_imagen_ocr_v2(ruta_img, config):
    """
    Pipeline v2: Otsu global + multi-PSM fijo.
    Resize 2.0x, binarización Otsu, contraste 1.5x, PSM 7/6/8/13.
    """
    if not os.path.exists(ruta_img):
        return ""
    try:
        img = Image.open(ruta_img)
        w, h = img.size
        img_large = img.resize((int(w * 2.0), int(h * 2.0)), Image.Resampling.LANCZOS)
        img_gray = img_large.convert('L')
        
        arr = np.array(img_gray)
        # Otsu threshold
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
        for cfg in configs:
            try:
                txt = pytesseract.image_to_string(img_contrast, lang=config.ocr_lang, config=cfg)
                if txt.strip():
                    textos.append(txt.strip())
            except Exception:
                pass
        
        return " ".join(dict.fromkeys(textos))  # deduplicar manteniendo orden
    except Exception as e:
        LOGGER.warning(f"  [Aviso OCR v2] Error al procesar {ruta_img}: {e}")
        return ""

def preprocesar_imagen_ocr_v4_psm_selectivo(ruta_img, config):
    """
    Pipeline v4 (PSM Selectivo): Detección automática de layout + PSM óptimo.
    Resize 2.5x, Otsu global, contraste 1.5x, PSM según layout.
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
        
        # Otsu global (mismo que v2)
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
        for cfg in configs:
            try:
                txt = pytesseract.image_to_string(img_contrast, lang=config.ocr_lang, config=cfg)
                if txt.strip():
                    textos.append(txt.strip())
            except Exception:
                pass
        
        return " ".join(dict.fromkeys(textos))
    except Exception as e:
        LOGGER.warning(f"  [Aviso OCR v4] Error al procesar {ruta_img}: {e}")
        return ""

def preprocesar_imagen_ocr_v3_sauvola(ruta_img, config):
    """
    Pipeline v3: Binarización adaptativa Sauvola (requiere scipy).
    Mejor para iluminación no uniforme, texto pequeño, fondos complejos.
    Retorna texto combinado de múltiples ventanas.
    """
    if not HAS_SCIPY:
        LOGGER.warning("  [OCR v3] SciPy no disponible, saltando Sauvola")
        return ""
    
    if not os.path.exists(ruta_img):
        return ""
    try:
        from scipy.ndimage import uniform_filter
        
        img = Image.open(ruta_img)
        w, h = img.size
        img_large = img.resize((int(w * 2.5), int(h * 2.5)), Image.Resampling.LANCZOS)
        img_gray = img_large.convert('L')
        
        arr = np.array(img_gray, dtype=np.float32) / 255.0  # Normalize 0-1
        
        # Sauvola threshold: T = m * (1 + k * ((s / R) - 1))
        # window_size: 15-25 para texto pequeño, k=0.2-0.5, R=128 (desv std max)
        window_size = 25
        k = 0.3
        R = 0.5  # since normalized 0-1
        
        # Local mean
        mean = uniform_filter(arr, size=window_size)
        # Local std dev
        sqmean = uniform_filter(arr * arr, size=window_size)
        std = np.sqrt(np.maximum(sqmean - mean * mean, 0))
        
        # Sauvola formula
        threshold = mean * (1 + k * ((std / R) - 1))
        
        arr_bin = np.where(arr > threshold, 1.0, 0.0)
        img_bin = Image.fromarray((arr_bin * 255).astype(np.uint8), mode='L')
        
        enhancer = ImageEnhance.Contrast(img_bin)
        img_contrast = enhancer.enhance(1.5)
        
        # PSM configs for block layout (typical for Sauvola results)
        configs = ['--psm 6', '--psm 4', '--psm 3', '--psm 13']
        textos = []
        for cfg in configs:
            try:
                txt = pytesseract.image_to_string(img_contrast, lang=config.ocr_lang, config=cfg)
                if txt.strip():
                    textos.append(txt.strip())
            except Exception:
                pass
        
        return " ".join(dict.fromkeys(textos))
    except Exception as e:
        LOGGER.warning(f"  [Aviso OCR v3] Error al procesar {ruta_img}: {e}")
        return ""


def run_all_pipelines(ruta_img, config):
    """
    Ejecuta todos los pipelines OCR habilitados y retorna lista de OCRResult.
    """
    from scraper_v2 import OCRResult
    
    results = []
    
    # Pipeline v1 (original)
    if "v1" in config.ocr_pipelines:
        texto = preprocesar_imagen_ocr_v1(ruta_img, config)
        results.append(OCRResult(
            pipeline="v1",
            layout="auto",
            psm_used=config.ocr_psm_primary,
            texto=texto
        ))
    
    # Pipeline v2 (Otsu)
    if "v2" in config.ocr_pipelines:
        texto = preprocesar_imagen_ocr_v2(ruta_img, config)
        results.append(OCRResult(
            pipeline="v2",
            layout="auto",
            psm_used=7,  # first PSM tried
            texto=texto
        ))
    
    # Pipeline v4 (PSM Selectivo)
    if "v4" in config.ocr_pipelines:
        layout = detectar_layout_texto(ruta_img)
        texto = preprocesar_imagen_ocr_v4_psm_selectivo(ruta_img, config)
        psm_used = int(get_psm_configs(layout)[0].split()[1]) if get_psm_configs(layout) else 6
        results.append(OCRResult(
            pipeline="v4",
            layout=layout,
            psm_used=psm_used,
            texto=texto
        ))
    
    # Pipeline v3 (Sauvola) - opcional, requiere scipy
    if "v3" in config.ocr_pipelines and config.ocr_enable_sauvola and HAS_SCIPY:
        texto = preprocesar_imagen_ocr_v3_sauvola(ruta_img, config)
        results.append(OCRResult(
            pipeline="v3",
            layout="auto",
            psm_used=6,  # default
            texto=texto
        ))
    
    return results

def validar_lluvia(valor: str, ocr_texto: str, dom_texto: str) -> int:
    """
    Puntuación de calidad 0-100 para valor de lluvia extraído.
    Criterios:
    - 25 pts: valor presente y numérico
    - 20 pts: rango válido CR (0-999 mm)
    - 20 pts: formato decimal limpio (sin artefactos OCR)
    - 15 pts: consistencia OCR vs DOM (dígitos clave compartidos)
    - 10 pts: unidad 'mm' presente cerca del valor
    - 10 pts: contexto palabras clave (ayer, hoy, 7am, lluvia)
    """
    score = 0
    
    if not valor:
        return 0
    
    # 25 pts: valor presente y numérico
    try:
        v = float(valor.replace(',', '.'))
        score += 25
    except ValueError:
        return 0
    
    # 20 pts: rango válido CR (0-999 mm diario) - RECHAZAR negativos y >999
    if 0 <= v <= 999:
        score += 20
    else:
        # Negativos o >999 no son lluvia válida
        return 0
    
    # 20 pts: formato decimal limpio
    # Penalizar si el valor original tiene caracteres raros
    if re.match(r'^[0-9]+[\.,]?[0-9]*$', valor.strip()):
        score += 20
    elif re.match(r'^[0-9]+[\.,][0-9]+$', valor.strip()):
        score += 15  # decimal OK
    else:
        score += 5   # formato raro
    
    # 15 pts: consistencia OCR vs DOM - dígitos clave compartidos
    def extraer_digitos_clave(texto):
        return set(re.findall(r'[0-9]{2,3}', texto))
    
    ocr_digits = extraer_digitos_clave(ocr_texto)
    dom_digits = extraer_digitos_clave(dom_texto)
    valor_digits = set(re.findall(r'[0-9]{1,3}', valor))
    
    if ocr_digits and dom_digits:
        overlap = len(ocr_digits & dom_digits)
        score += min(15, overlap * 5)
    elif ocr_digits and valor_digits:
        # Al menos coincide con lo que sacó el OCR
        overlap = len(ocr_digits & valor_digits)
        score += min(10, overlap * 5)
    
    # 10 pts: unidad 'mm' presente cerca del valor en OCR
    if re.search(r'' + re.escape(valor.replace('.', '[\.,]')) + r'\s*mm', ocr_texto, re.IGNORECASE):
        score += 10
    elif 'mm' in ocr_texto.lower():
        score += 5
    
    # 10 pts: contexto palabras clave
    keywords = ['ayer', 'hoy', '7am', '7 am', 'lluvia', 'precip', 'desd']
    texto_completo = (ocr_texto + ' ' + dom_texto).lower()
    keyword_count = sum(1 for kw in keywords if kw in texto_completo)
    score += min(10, keyword_count * 2)
    
    return min(100, score)


def _es_lluvia_valida(valor: str) -> bool:
    """Valida que el valor extraído sea una lluvia plausible (0-999 mm)."""
    try:
        v = float(valor.replace(',', '.'))
        return 0 <= v <= 999
    except ValueError:
        return False






# ============================================================
# LOGGING
# ============================================================

def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configura logging estructurado."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )
    return logging.getLogger(__name__)

LOGGER = setup_logging()

# ============================================================
# MODELOS DE DATOS
# ============================================================

@dataclass
class StationBase:
    """Campos base desde Estaciones.csv"""
    Indice: str = ""
    URL: str = ""
    Nombre_Estacion: str = ""
    Latitud_DMS: str = ""
    Longitud_DMS: str = ""
    Altitud_msnm: str = ""
    Region: str = ""
    Latitud_Decimal: str = ""
    Longitud_Decimal: str = ""

@dataclass
class StationScraped:
    """Campos extraídos en tiempo real"""
    Fecha_Captura: str
    Lluvia_Ayer_7am_a_7am_mm: str = ""
    Origen_Lluvia_ROI: str = ""
    Lluvia_Desde_7am_mm: str = ""
    Precip_Ultima_Hora_mm: str = ""
    Temperatura_Actual_C: str = ""
    Sensacion_Termica_C: str = ""
    OCR_ROI_Lluvia_Texto: str = ""
    OCR_ROI_Lluvia_Op_Texto: str = ""
    Ruta_Captura_Imagen: str = ""
    Ruta_ROI_Lluvia: str = ""
    Ruta_ROI_Lluvia_Op: str = ""
    Estado: str = "Pendiente"
    # Nuevos campos OCR avanzado (Fase 3)
    Lluvia_Score: int = 0
    Lluvia_Pipeline: str = ""

@dataclass
class StationRecord(StationBase, StationScraped):
    """Registro completo = base + scraped"""
    pass


@dataclass
class OCRResult:
    """Resultado de un pipeline OCR individual."""
    pipeline: str           # v1, v2, v3, v4, dom_fallback
    layout: str             # single_line, sparse, block, auto
    psm_used: int           # PSM que dio mejor resultado
    texto: str              # Texto crudo OCR
    score: int = 0          # Score de validación 0-100
    lat_dms: str = ""       # Para coords (v6)
    lon_dms: str = ""       # Para coords (v6)
    lluvia_mm: str = ""     # Para lluvia (v2)

def station_base_from_row(row: pd.Series) -> StationBase:
    """Convierte una fila del CSV base a StationBase."""
    return StationBase(
        Indice=str(row.get("Indice", "")).strip(),
        URL=str(row.get("URL", "")).strip(),
        Nombre_Estacion=str(row.get("Nombre_Estacion", "")).strip(),
        Latitud_DMS=str(row.get("Latitud_DMS", "")).strip(),
        Longitud_DMS=str(row.get("Longitud_DMS", "")).strip(),
        Altitud_msnm=str(row.get("Altitud_msnm", "")).strip(),
        Region=str(row.get("Region", "")).strip(),
        Latitud_Decimal=str(row.get("Latitud_Decimal", "")).strip(),
        Longitud_Decimal=str(row.get("Longitud_Decimal", "")).strip(),
    )

def record_to_dict(record: StationRecord) -> Dict[str, Any]:
    """Convierte StationRecord a dict para DataFrame."""
    return asdict(record)

# ============================================================
# UTILIDADES OCR
# ============================================================

def preprocesar_imagen_ocr_v1(ruta_img: str, config: Config = CONFIG) -> str:
    """
    Pipeline v1 (original): DSF=2.0, resize 2.5x, escala de grises, contraste 2.0x, PSM 6/11.
    """
    if not os.path.exists(ruta_img):
        return ""
    try:
        with Image.open(ruta_img) as img:
            w, h = img.size
            img_large = img.resize(
                (int(w * config.ocr_upscale_factor), int(h * config.ocr_upscale_factor)),
                Image.Resampling.LANCZOS
            )
            img_gray = img_large.convert('L')
            enhancer = ImageEnhance.Contrast(img_gray)
            img_contrast = enhancer.enhance(config.ocr_contrast_factor)
            
            texto = pytesseract.image_to_string(
                img_contrast, 
                lang=config.ocr_lang, 
                config=f'--psm {config.ocr_psm_primary}'
            )
            if len(texto.strip()) < 5:
                texto += " " + pytesseract.image_to_string(
                    img_contrast, 
                    config=f'--psm {config.ocr_psm_fallback}'
                )
        return texto
    except Exception as e:
        LOGGER.warning(f"Error OCR en {ruta_img}: {e}")
        return ""

def extraer_valor_lluvia(texto: str) -> Optional[str]:
    """
    Extrae cantidad numérica en mm de lluvia desde texto OCR.

    Estrategia:
    1. Busca patrón explícito: 'De 7 am de ayer a 7 am de hoy: X mm'
    2. Busca número seguido de 'mm' cerca de palabras clave
    3. Busca número después de 'hoy:' (común en OCR)
    4. Fallback: primer decimal razonable
    """
    if not texto:
        return None

    t = ' '.join(texto.split())  # normalizar espacios

    # 1. PATRÓN EXPLÍCITO: etiqueta completa + valor
    patrones_explicitos = [
        r'[Dd]e\s+7\s*[aA]\.?[mM]\.?\s+de\s+ayer\s+a\s+7\s*[aA]\.?[mM]\.?\s+de\s+hoy[:;]?\s*([0-9]+[\.,][0-9]+|\b[0-9]+\b)',
        r'[Dd]e\s+7\s*a\.?\s*m\.?\s+de\s+ayer\s+a\s+7\s*a\.?\s*m\.?\s+de\s+hoy[:;]?\s*([0-9]+[\.,][0-9]+|\b[0-9]+\b)',
        r'7\s*[aA]\.?[mM]\.?\s+ayer\s+7\s*[aA]\.?[mM]\.?\s+hoy[:;]?\s*([0-9]+[\.,][0-9]+|\b[0-9]+\b)',
    ]
    for pat in patrones_explicitos:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            val = m.group(1).replace(',', '.').strip()
            if _es_lluvia_valida(val):
                return val

    # 2. BUSCAR 'mm' CERCA DE PALABRAS CLAVE
    m = re.search(r'([0-9]+[\.,][0-9]+|\b[0-9]+\b)\s*mm', t, re.IGNORECASE)
    if m:
        val = m.group(1).replace(',', '.').strip()
        if _es_lluvia_valida(val):
            return val

    # 3. BUSCAR NÚMERO DESPUÉS DE 'hoy:' O 'hoy ;'
    m = re.search(r'hoy[:;]\s*([0-9]+[\.,][0-9]+|\b[0-9]+\b)', t, re.IGNORECASE)
    if m:
        val = m.group(1).replace(',', '.').strip()
        if _es_lluvia_valida(val):
            return val

    # 4. FALLBACK: primer decimal razonable
    m = re.search(r'([0-9]+[\.,][0-9]+)', t)
    if m:
        val = m.group(1).replace(',', '.').strip()
        if _es_lluvia_valida(val):
            return val

    return None


    return None

# ============================================================
# PARSERS DE TEXTO (DOM + OCR)
# ============================================================

class DataParser:
    """Extrae campos meteorológicos desde texto combinado (DOM + OCR)."""
    
    @staticmethod
    def parse_all(texto_total: str, ocr_lluvia: str, ocr_lluvia_op: str, 
                   ocr_results_lluvia: list = None, ocr_results_lluvia_op: list = None, 
                   dom_lluvia_val: str = None, dom_lluvia_score: int = None) -> Dict[str, Any]:
        """
        Extrae campos meteorológicos desde texto combinado (DOM + OCR).
        Ahora usa multi-pipeline OCR con scoring para selección robusta.
        Retorna dict con valores + metadatos (score, pipeline_usado).
        """
        from scraper_v2 import validar_lluvia, extraer_valor_lluvia
        
        resultado = {}
        
        # ===== LLUVIA AYER 7AM-7AM: Multi-pipeline + Scoring =====
        best_lluvia = None
        best_score = -1
        best_origin = ""
        best_pipeline = ""
        
        # Candidatos: cada pipeline del ROI estándar
        if ocr_results_lluvia:
            for ocr_res in ocr_results_lluvia:
                val = extraer_valor_lluvia(ocr_res.texto)
                if val:
                    score = validar_lluvia(val, ocr_res.texto, texto_total)
                    if score > best_score:
                        best_score = score
                        best_lluvia = val
                        best_origin = "ROI_Lluvia_Estandar"
                        best_pipeline = ocr_res.pipeline
        
        # Candidatos: cada pipeline del ROI opcional
        if ocr_results_lluvia_op:
            for ocr_res in ocr_results_lluvia_op:
                val = extraer_valor_lluvia(ocr_res.texto)
                if val:
                    score = validar_lluvia(val, ocr_res.texto, texto_total)
                    if score > best_score:
                        best_score = score
                        best_lluvia = val
                        best_origin = "ROI_Lluvia_Opcional"
                        best_pipeline = ocr_res.pipeline
        
        #         # Fallback DOM: extraer_lluvia_dom (DOM estructurado)
        # Se pasa el resultado via par髇metros opcionales dom_lluvia_val / dom_lluvia_score
        if dom_lluvia_val is not None and dom_lluvia_val:
            val = dom_lluvia_val
            score = dom_lluvia_score if dom_lluvia_score is not None else validar_lluvia(val, '', texto_total)
            if score > best_score:
                best_score = score
                best_lluvia = val
                best_origin = "DOM_Estructurado"
                best_pipeline = "dom_fallback"
        
        # Fallback legacy: single OCR strings (compatibilidad)
        if best_lluvia is None:
            for ocr_text, origin in [(ocr_lluvia, "ROI_Lluvia_Estandar"), (ocr_lluvia_op, "ROI_Lluvia_Opcional")]:
                val = extraer_valor_lluvia(ocr_text)
                if val:
                    score = validar_lluvia(val, ocr_text, texto_total)
                    if score > best_score:
                        best_score = score
                        best_lluvia = val
                        best_origin = origin
                        best_pipeline = "legacy"
        
        if best_lluvia:
            resultado["Lluvia_Ayer_7am_a_7am_mm"] = best_lluvia
            resultado["Origen_Lluvia_ROI"] = best_origin
            resultado["Lluvia_Score"] = best_score
            resultado["Lluvia_Pipeline"] = best_pipeline
        
        # ===== LLUVIA DESDE 7AM HOY (sin cambios, solo regex) =====
        m = re.search(r'Desde\s+las?\s+7\s*a\.?m\.?:?\s*([0-9\.,]+)\s*mm', texto_total, re.IGNORECASE)
        if m:
            resultado["Lluvia_Desde_7am_mm"] = m.group(1).replace(',', '.').strip()
        
        # ===== TEMPERATURA ACTUAL =====
        m = re.search(r'Temperatura\s+Actual:?\s*([0-9\.,]+)\s*°?C', texto_total, re.IGNORECASE)
        if m:
            resultado["Temperatura_Actual_C"] = m.group(1).replace(',', '.').strip()
        
        # ===== SENSIACIÓN TÉRMICA =====
        m = re.search(r'Sensaci[oó]n\s+t[eé]rmica(?:\s+Actual)?:?\s*([0-9\.,]+)\s*°?C', texto_total, re.IGNORECASE)
        if m:
            resultado["Sensacion_Termica_C"] = m.group(1).replace(',', '.').strip()
        
        return resultado

# ============================================================
# EXTRACCIÓN DOM
# ============================================================

async def extraer_texto_dom(page) -> str:
    """Extrae todo el texto visible de la página (incluyendo frames)."""
    textos = []
    for frame in page.frames:
        try:
            content = await frame.content()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            texto = ' '.join(soup.get_text(separator=' ').split())
            if texto:
                textos.append(texto)
        except Exception:
            pass
    return " ".join(textos)

async def extraer_lluvia_dom(page) -> tuple[str, int]:
    """
    Busca valor de lluvia en el DOM estructurado.
    Retorna (valor_str, score) o ("", 0).
    Estrategias:
    1. Tablas HTML con palabras clave
    2. JSON embebido en scripts
    3. Meta tags geo/coord/weather
    4. Elementos con data-* attributes
    5. Texto visible con regex específico
    """
    try:
        # Estrategia 1: Tablas HTML
        for frame in page.frames:
            try:
                frame_content = await frame.content()
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(frame_content, 'html.parser')
                
                for table in soup.find_all('table'):
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        cell_texts = [c.get_text(strip=True).lower() for c in cells]
                        
                        for i, cell in enumerate(cell_texts):
                            if any(kw in cell for kw in ['lluvia', 'precip', '7am', '7 am', 'ayer']):
                                for j in range(i+1, len(cell_texts)):
                                    val = extraer_valor_lluvia(cell_texts[j])
                                    if val:
                                        return val, 75
                                val = extraer_valor_lluvia(cells[i].get_text())
                                if val:
                                    return val, 70
            except Exception:
                pass
        
        # Estrategia 2: JSON en scripts (simplified)
        for frame in page.frames:
            try:
                frame_content = await frame.content()
                import re
                soup = BeautifulSoup(frame_content, 'html.parser')
                for script in soup.find_all('script'):
                    if script.string and ('rain' in script.string.lower() or 'precip' in script.string.lower()):
                        matches = re.findall(r'[0-9]+[\.,][0-9]+', script.string)
                        for m in matches:
                            val = m.replace(',', '.')
                            try:
                                if 0 <= float(val) <= 999:
                                    return val, 80
                            except ValueError:
                                pass
            except Exception:
                pass
        
        # Estrategia 3: Meta tags
        for frame in page.frames:
            try:
                frame_content = await frame.content()
                soup = BeautifulSoup(frame_content, 'html.parser')
                for meta in soup.find_all('meta'):
                    name = meta.get('name', '') or meta.get('property', '')
                    content_val = meta.get('content', '')
                    if any(kw in name.lower() for kw in ['weather', 'rain', 'precip', 'geo']):
                        val = extraer_valor_lluvia(content_val)
                        if val:
                            return val, 65
            except Exception:
                pass
        
        # Estrategia 4: data-* attributes
        for frame in page.frames:
            try:
                frame_content = await frame.content()
                soup = BeautifulSoup(frame_content, 'html.parser')
                for elem in soup.find_all(attrs={'data-rain': True}):
                    val = extraer_valor_lluvia(elem.get('data-rain', ''))
                    if val:
                        return val, 70
                for elem in soup.find_all(attrs={'data-precipitation': True}):
                    val = extraer_valor_lluvia(elem.get('data-precipitation', ''))
                    if val:
                        return val, 70
            except Exception:
                pass
        
        # Estrategia 5: Regex específico en texto visible
        texto_completo = ""
        for frame in page.frames:
            try:
                frame_content = await frame.content()
                soup = BeautifulSoup(frame_content, 'html.parser')
                texto_completo += " " + ' '.join(soup.get_text(separator=' ').split())
            except Exception:
                pass
        
        m = re.search(r'De\s+7\s*a\.?m\.?\s+de\s+ayer\s+a\s+7\s*a\.?m\.?\s+de\s+hoy:?\s*([0-9\.,]+)\s*mm', texto_completo, re.IGNORECASE)
        if m:
            return m.group(1).replace(',', '.').strip(), 70
        
        m = re.search(r'([0-9]+[\.,][0-9]+|\b[0-9]+\b)\s*mm', texto_completo, re.IGNORECASE)
        if m:
            val = m.group(1).replace(',', '.').strip()
            try:
                if 0 <= float(val) <= 999:
                    return val, 50
            except ValueError:
                pass
        
    except Exception as e:
        LOGGER.debug(f"  [DOM Fallback] Error: {e}")
    
    return "", 0


async def procesar_estacion(
    page,
    base: StationBase,
    semaphore: asyncio.Semaphore,
    config: Config,
    carpeta_capturas: Path,
    idx: int,
    total: int,
    fecha_proceso: str
) -> StationRecord:
    """Procesa una sola estación con control de concurrencia."""
    async with semaphore:
        registro = StationRecord(
            **asdict(base),
            Fecha_Captura=fecha_proceso,
            Estado="Pendiente"
        )

        if not base.URL or not base.URL.startswith("http"):
            registro.Estado = "URL no válida"
            LOGGER.warning(f"[{idx}/{total}] URL inválida: {base.URL}")
            return registro

        LOGGER.info(f"[{idx}/{total}] Procesando: {base.URL}")

        try:
            for intento in range(config.max_retries_goto + 1):
                try:
                    await page.goto(base.URL, wait_until="domcontentloaded", timeout=config.goto_timeout_ms)
                    break
                except Exception as e:
                    if intento == config.max_retries_goto:
                        raise
                    LOGGER.warning(f"  Reintento {intento + 1}/{config.max_retries_goto} para {base.URL}: {e}")
                    await asyncio.sleep(2)

            await page.wait_for_timeout(config.wait_after_load_ms)

            await page.evaluate(f"document.body.style.zoom = '{config.zoom_level}'")
            await page.wait_for_timeout(config.wait_after_zoom_ms)

            nombre_img_full = f"estacion_{idx}_full_{config.zoom_level.replace('.', 'pct')}.png"
            ruta_img_full = carpeta_capturas / nombre_img_full
            await page.screenshot(path=str(ruta_img_full), full_page=False)
            registro.Ruta_Captura_Imagen = str(ruta_img_full)

            clip_lluvia = config.roi_lluvia
            ruta_roi_lluvia = carpeta_capturas / f"estacion_{idx}_ROI_lluvia.png"
            await page.screenshot(path=str(ruta_roi_lluvia), clip=clip_lluvia)
            registro.Ruta_ROI_Lluvia = str(ruta_roi_lluvia)

            clip_lluvia_op = config.roi_lluvia_op
            ruta_roi_lluvia_op = carpeta_capturas / f"estacion_{idx}_ROI_lluvia_op.png"
            await page.screenshot(path=str(ruta_roi_lluvia_op), clip=clip_lluvia_op)
            registro.Ruta_ROI_Lluvia_Op = str(ruta_roi_lluvia_op)

            # ===== OCR MULTI-PIPELINE (Fase 2+3) =====
            ocr_results_lluvia = []
            ocr_results_lluvia_op = []
            ocr_lluvia_txt = ""
            ocr_lluvia_op_txt = ""
            
            if HAS_OCR and config.ocr_enable_multi_pipeline:
                # ===== Cache check para ROI estándar =====
                cached_ocr = None
                if config.cache_enabled:
                    cached_ocr = cache_obtener(str(ruta_roi_lluvia))
                
                if cached_ocr is not None:
                    ocr_results_lluvia = cached_ocr
                    ocr_lluvia_txt = " ".join([r.texto for r in ocr_results_lluvia if r.texto])
                    registro.OCR_ROI_Lluvia_Texto = " ".join(ocr_lluvia_txt.split())
                    LOGGER.info(f"  [Cache] Usando OCR cacheado para ROI estándar")
                else:
                    # Ejecutar todos los pipelines en ambos ROIs
                    ocr_results_lluvia = run_all_pipelines(str(ruta_roi_lluvia), config)
                    # Guardar en cache
                    if config.cache_enabled:
                        cache_guardar(str(ruta_roi_lluvia), ocr_results_lluvia)
                    ocr_lluvia_txt = " ".join([r.texto for r in ocr_results_lluvia if r.texto])
                    registro.OCR_ROI_Lluvia_Texto = " ".join(ocr_lluvia_txt.split())
                
                # ===== Cache check para ROI opcional =====
                cached_ocr_op = None
                if config.cache_enabled:
                    cached_ocr_op = cache_obtener(str(ruta_roi_lluvia_op))
                
                if cached_ocr_op is not None:
                    ocr_results_lluvia_op = cached_ocr_op
                    ocr_lluvia_op_txt = " ".join([r.texto for r in ocr_results_lluvia_op if r.texto])
                    registro.OCR_ROI_Lluvia_Op_Texto = " ".join(ocr_lluvia_op_txt.split())
                    LOGGER.info(f"  [Cache] Usando OCR cacheado para ROI opcional")
                else:
                    ocr_results_lluvia_op = run_all_pipelines(str(ruta_roi_lluvia_op), config)
                    if config.cache_enabled:
                        cache_guardar(str(ruta_roi_lluvia_op), ocr_results_lluvia_op)
                    ocr_lluvia_op_txt = " ".join([r.texto for r in ocr_results_lluvia_op if r.texto])
                    registro.OCR_ROI_Lluvia_Op_Texto = " ".join(ocr_lluvia_op_txt.split())
            elif HAS_OCR:
                # Fallback legacy: solo v1
                ocr_lluvia_txt = preprocesar_imagen_ocr_v1(str(ruta_roi_lluvia), config)
                ocr_lluvia_op_txt = preprocesar_imagen_ocr_v1(str(ruta_roi_lluvia_op), config)
                registro.OCR_ROI_Lluvia_Texto = " ".join(ocr_lluvia_txt.split())
                registro.OCR_ROI_Lluvia_Op_Texto = " ".join(ocr_lluvia_op_txt.split())

            texto_dom = await extraer_texto_dom(page)
            texto_total = f"{texto_dom} {ocr_lluvia_txt} {ocr_lluvia_op_txt}"
            # ===== DOM Fallback: extraer_lluvia_dom (async) =====
            dom_lluvia_val = ""
            dom_lluvia_score = 0
            if hasattr(page, 'frames'):  # page is available
                try:
                    dom_lluvia_val, dom_lluvia_score = await extraer_lluvia_dom(page)
                    if dom_lluvia_val:
                        LOGGER.info(f"  [DOM Fallback] Lluvia encontrada: {dom_lluvia_val} mm (score: {dom_lluvia_score})")
                except Exception as e:
                    LOGGER.debug(f"  [DOM Fallback] Error: {e}")
            

            # Pasar resultados OCR al parser para scoring
            # ===== Umbral adaptativo: si todos los OCR scores bajos, forzar DOM =====
            max_ocr_score = 0
            if ocr_results_lluvia:
                for r in ocr_results_lluvia:
                    val = extraer_valor_lluvia(r.texto)
                    if val:
                        s = validar_lluvia(val, r.texto, texto_total)
                        max_ocr_score = max(max_ocr_score, s)
            if ocr_results_lluvia_op:
                for r in ocr_results_lluvia_op:
                    val = extraer_valor_lluvia(r.texto)
                    if val:
                        s = validar_lluvia(val, r.texto, texto_total)
                        max_ocr_score = max(max_ocr_score, s)
            
            force_dom = max_ocr_score < config.ocr_min_score_threshold
            if force_dom and hasattr(page, 'frames'):
                LOGGER.info(f"  [Adaptativo] Max OCR score ({max_ocr_score}) < umbral ({config.ocr_min_score_threshold}), forzando DOM fallback")
                try:
                    dom_lluvia_val, dom_lluvia_score = await extraer_lluvia_dom(page)
                except Exception as e:
                    LOGGER.debug(f"  [DOM Fallback] Error: {e}")
            
            parsed = DataParser.parse_all(
                texto_total, ocr_lluvia_txt, ocr_lluvia_op_txt,
                ocr_results_lluvia=ocr_results_lluvia,
                ocr_results_lluvia_op=ocr_results_lluvia_op,
                dom_lluvia_val=dom_lluvia_val,
                dom_lluvia_score=dom_lluvia_score
            )
            for key, value in parsed.items():
                setattr(registro, key, value)

            registro.Estado = "Éxito"

        except Exception as e:
            registro.Estado = f"Error: {type(e).__name__}: {e}"
            LOGGER.error(f"  Error procesando {base.URL}: {e}")

        return registro


# ============================================================
# GUARDADO DE DATOS
# ============================================================

def guardar_diario_csv(registros: List[StationRecord], config: Config) -> pd.DataFrame:
    """Guarda los registros del día actual en CSV y Excel diario."""
    df = pd.DataFrame([record_to_dict(r) for r in registros])
    
    for intento in range(config.max_retries_csv_write):
        try:
            df.to_csv(config.archivo_diario_csv, index=False, encoding="utf-8-sig")
            break
        except PermissionError:
            if intento == config.max_retries_csv_write - 1:
                raise
            time.sleep(1)
    
    try:
        archivo_excel = config.archivo_diario_csv.replace(".csv", ".xlsx")
        df.to_excel(archivo_excel, index=False)
    except Exception as e:
        LOGGER.warning(f"No se pudo guardar Excel diario: {e}")
    
    return df


def actualizar_historico(df_nuevo: pd.DataFrame, config: Config):
    """Añade los nuevos registros a los archivos históricos (CSV y Excel)."""
    if os.path.exists(config.archivo_hist_csv):
        try:
            df_hist = pd.read_csv(config.archivo_hist_csv)
            df_hist = pd.concat([df_hist, df_nuevo], ignore_index=True)
        except Exception:
            df_hist = df_nuevo
    else:
        df_hist = df_nuevo
    
    df_hist.to_csv(config.archivo_hist_csv, index=False, encoding="utf-8-sig")
    
    archivo_hist_excel = config.archivo_hist_csv.replace(".csv", ".xlsx")
    if os.path.exists(archivo_hist_excel):
        try:
            df_hist_excel = pd.read_excel(archivo_hist_excel)
            df_hist_excel = pd.concat([df_hist_excel, df_nuevo], ignore_index=True)
        except Exception:
            df_hist_excel = df_nuevo
    else:
        df_hist_excel = df_nuevo
    
    try:
        df_hist_excel.to_excel(archivo_hist_excel, index=False)
    except Exception as e:
        LOGGER.warning(f"No se pudo guardar Excel histórico: {e}")


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

async def main():
    config = CONFIG
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    carpeta_capturas = Path(config.carpeta_capturas_base) / timestamp_str
    carpeta_capturas.mkdir(parents=True, exist_ok=True)

    if not os.path.exists(config.archivo_entrada):
        LOGGER.error(f"No se encontró '{config.archivo_entrada}'")
        return

    try:
        df_base = pd.read_csv(config.archivo_entrada, encoding="latin-1")
    except Exception as e:
        LOGGER.error(f"Error leyendo CSV base: {e}")
        return

    estaciones_base = [station_base_from_row(row) for _, row in df_base.iterrows()]
    total = len(estaciones_base)
    fecha_proceso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    LOGGER.info(f"Iniciando extracción para {total} estaciones (concurrencia: {config.max_concurrent_stations})")

    semaphore = asyncio.Semaphore(config.max_concurrent_stations)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=config.headless)
        
        contexts = []
        pages = []
        for _ in range(config.max_concurrent_stations):
            context = await browser.new_context(
                viewport={"width": config.viewport_width, "height": config.viewport_height},
                device_scale_factor=config.device_scale_factor
            )
            page = await context.new_page()
            contexts.append(context)
            pages.append(page)

        async def worker(page, base, idx):
            return await procesar_estacion(page, base, semaphore, config, carpeta_capturas, idx, total, fecha_proceso)

        tasks = [
            worker(pages[i % config.max_concurrent_stations], base, i + 1)
            for i, base in enumerate(estaciones_base)
        ]
        
        resultados = await asyncio.gather(*tasks, return_exceptions=True)
        
        registros_finales = []
        for i, r in enumerate(resultados):
            if isinstance(r, Exception):
                LOGGER.error(f"Excepción en estación {i+1}: {r}")
                base = estaciones_base[i]
                registro = StationRecord(**asdict(base), Fecha_Captura=fecha_proceso, Estado=f"Excepción: {r}")
                registros_finales.append(registro)
            else:
                registros_finales.append(r)

        for context in contexts:
            await context.close()
        await browser.close()

    df_diario = guardar_diario_csv(registros_finales, config)
    actualizar_historico(df_diario, config)

    exitosos = sum(1 for r in registros_finales if r.Estado == "Éxito")
    LOGGER.info(f"Finalizado: {exitosos}/{total} exitosos")
    LOGGER.info(f"Diario: {config.archivo_diario_csv} | Histórico: {config.archivo_hist_csv}")


if __name__ == "__main__":
    asyncio.run(main())
