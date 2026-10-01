with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the v3 placeholder in run_all_pipelines with actual implementation
old_v3 = '''    # Pipeline v3 (Sauvola) - opcional, requiere scipy
    if "v3" in config.ocr_pipelines and config.ocr_enable_sauvola:
        try:
            from scipy.ndimage import uniform_filter
            # v3 implementation would go here
            pass
        except ImportError:
            pass'''

new_v3 = '''    # Pipeline v3 (Sauvola) - opcional, requiere scipy
    if "v3" in config.ocr_pipelines and config.ocr_enable_sauvola and HAS_SCIPY:
        texto = preprocesar_imagen_ocr_v3_sauvola(ruta_img, config)
        results.append(OCRResult(
            pipeline="v3",
            layout="auto",
            psm_used=6,  # default
            texto=texto
        ))'''

if old_v3 in content:
    content = content.replace(old_v3, new_v3)
    with open('scraper_v2.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Phase 6.2: v3 integrated in run_all_pipelines")
else:
    print("Old v3 block not found, searching...")
    idx = content.find('Pipeline v3 (Sauvola)')
    if idx != -1:
        print(content[idx:idx+300])
    else:
        print("Not found")