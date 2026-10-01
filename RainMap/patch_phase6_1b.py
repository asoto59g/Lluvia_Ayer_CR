with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add v3 (Sauvola) pipeline after v4 and before run_all_pipelines
# Find the end of v4 function
marker = 'return " ".join(dict.fromkeys(textos))'
idx = content.rfind(marker)  # Last occurrence (in v4)
if idx == -1:
    print("Marker not found")
    exit(1)

idx_end = content.find('\n\n', idx)
if idx_end == -1:
    idx_end = idx + len(marker)

pipeline_v3 = '''

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
'''

content = content[:idx_end] + pipeline_v3 + content[idx_end:]

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Phase 6.1b: Pipeline v3 (Sauvola) added")