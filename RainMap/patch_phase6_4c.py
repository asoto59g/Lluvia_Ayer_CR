with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the entire multi-pipeline OCR block with cache integration
old_block = '''            if HAS_OCR and config.ocr_enable_multi_pipeline:
                # Ejecutar todos los pipelines en ambos ROIs
                ocr_results_lluvia = run_all_pipelines(str(ruta_roi_lluvia), config)
                ocr_results_lluvia_op = run_all_pipelines(str(ruta_roi_lluvia_op), config)
                
                # Combinar texto de todos los pipelines para guardar
                ocr_lluvia_txt = " ".join([r.texto for r in ocr_results_lluvia if r.texto])
                ocr_lluvia_op_txt = " ".join([r.texto for r in ocr_results_lluvia_op if r.texto])
                
                registro.OCR_ROI_Lluvia_Texto = " ".join(ocr_lluvia_txt.split())
                registro.OCR_ROI_Lluvia_Op_Texto = " ".join(ocr_lluvia_op_txt.split())
            elif HAS_OCR:'''

new_block = '''            if HAS_OCR and config.ocr_enable_multi_pipeline:
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
            elif HAS_OCR:'''

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('scraper_v2.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Phase 6.4c: Cache integrated in procesar_estacion")
else:
    print("Old block not found, searching...")
    idx = content.find('if HAS_OCR and config.ocr_enable_multi_pipeline:')
    if idx != -1:
        print(content[idx:idx+500])
    else:
        print("Not found at all")