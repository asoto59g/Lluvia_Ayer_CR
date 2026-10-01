with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add pipeline v2 function after detectar_layout_texto / get_psm_configs
# Find the end of get_psm_configs function
marker = "return configs_map.get(layout, configs_map['auto'])"
idx = content.find(marker)
if idx == -1:
    print("Marker not found")
    exit(1)

# Find end of that function (next blank line or def)
idx_end = content.find('\n\n', idx)
if idx_end == -1:
    idx_end = idx + len(marker)

pipeline_v2 = '''

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
'''

content = content[:idx_end] + pipeline_v2 + content[idx_end:]

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Phase 2.4: Pipeline v2 (Otsu) added")