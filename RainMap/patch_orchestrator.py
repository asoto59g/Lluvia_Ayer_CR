with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add orchestrator after the last pipeline function (v4)
marker = 'return " ".join(dict.fromkeys(textos))'
# Find the LAST occurrence (v4)
idx = content.rfind(marker)
if idx == -1:
    print("Marker not found")
    exit(1)

idx_end = content.find('\n\n', idx)
if idx_end == -1:
    idx_end = idx + len(marker)

orchestrator = '''

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
    if "v3" in config.ocr_pipelines and config.ocr_enable_sauvola:
        try:
            from scipy.ndimage import uniform_filter
            # v3 implementation would go here
            pass
        except ImportError:
            pass
    
    return results
'''

content = content[:idx_end] + orchestrator + content[idx_end:]

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Orchestrator added")