with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add numpy import if not present
if 'import numpy as np' not in content:
    content = content.replace('import pandas as pd', 'import pandas as pd\nimport numpy as np')

# Find location after imports and before CONFIG - add the layout detection functions
# We'll add them after the CONFIG class definition
insert_marker = 'CONFIG = Config()'

layout_functions = '''

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
'''

idx = content.find(insert_marker)
if idx != -1:
    idx_end = idx + len(insert_marker)
    content = content[:idx_end] + layout_functions + content[idx_end:]
    with open('scraper_v2.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Phase 2.1: Layout detection functions added")
else:
    print("Marker not found")