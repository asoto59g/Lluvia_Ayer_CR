with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add cache functions after log_estacion_procesada
idx = content.find('def log_estacion_procesada')
if idx == -1:
    print('log_estacion_procesada not found')
    exit(1)

# Find end of that function
end_idx = content.find('\n\ndef ', idx+1)
if end_idx == -1:
    end_idx = content.find('\n\nasync def ', idx+1)
if end_idx == -1:
    end_idx = content.find('\n\nclass ', idx+1)
if end_idx == -1:
    end_idx = idx + 2000

cache_code = '''

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


'''

content = content[:end_idx] + cache_code + content[end_idx:]

# Add config field for cache
old_cache_config = '''    # Logging JSONL (Fase 6.3)
    log_jsonl_enabled: bool = True
    log_jsonl_path: str = "logs_scraper.jsonl"'''

new_cache_config = '''    # Logging JSONL (Fase 6.3)
    log_jsonl_enabled: bool = True
    log_jsonl_path: str = "logs_scraper.jsonl"

    # Cache capturas (Fase 6.4)
    cache_enabled: bool = True'''

if old_cache_config in content:
    content = content.replace(old_cache_config, new_cache_config)
else:
    print('Old cache config not found')

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Phase 6.4: Cache de capturas added")