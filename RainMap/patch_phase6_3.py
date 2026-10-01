with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add JSON logging function after imports / config section
# Find a good place - after CONFIG = Config()
idx = content.find('CONFIG = Config()')
if idx == -1:
    print('CONFIG not found')
    exit(1)

idx_end = content.find('\n\n', idx)
if idx_end == -1:
    idx_end = idx + len('CONFIG = Config()')

json_logging = '''
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


def log_estacion_procesada(registro, config: Config = CONFIG, duracion_ms: int = 0, \n                           ocr_results=None, dom_result=None):
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

'''

content = content[:idx_end] + json_logging + content[idx_end:]

# Add config fields for JSONL
old_log_config = '''    # OCR Avanzado (Fase 1)
    ocr_enable_multi_pipeline: bool = True
    ocr_enable_layout_detection: bool = True
    ocr_enable_sauvola: bool = False
    ocr_min_score_threshold: int = 50
    ocr_pipelines: List[str] = field(default_factory=lambda: ["v1", "v2", "v4"])'''

new_log_config = '''    # OCR Avanzado (Fase 1)
    ocr_enable_multi_pipeline: bool = True
    ocr_enable_layout_detection: bool = True
    ocr_enable_sauvola: bool = False
    ocr_min_score_threshold: int = 50
    ocr_pipelines: List[str] = field(default_factory=lambda: ["v1", "v2", "v4"])

    # Logging JSONL (Fase 6.3)
    log_jsonl_enabled: bool = True
    log_jsonl_path: str = "logs_scraper.jsonl"'''

if old_log_config in content:
    content = content.replace(old_log_config, new_log_config)
else:
    print('Old log config not found')

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Phase 6.3: JSONL logging functions + config added")