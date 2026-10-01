with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find where OCR multi-pipeline runs in procesar_estacion
idx = content.find('if HAS_OCR and config.ocr_enable_multi_pipeline:')
if idx == -1:
    print('OCR multi-pipeline block not found')
    exit(1)

# Find the start of this block (look for the line before)
block_start = content.rfind('\n', 0, idx) + 1

# We need to insert cache check before the OCR block
cache_check = '''            # ===== Cache check =====
            cached_ocr = None
            if config.cache_enabled:
                cached_ocr = cache_obtener(str(ruta_roi_lluvia))
            
            if cached_ocr is not None:
                ocr_results_lluvia = cached_ocr
                ocr_lluvia_txt = " ".join([r.texto for r in ocr_results_lluvia if r.texto])
                registro.OCR_ROI_Lluvia_Texto = " ".join(ocr_lluvia_txt.split())
                LOGGER.info(f"  [Cache] Usando OCR cacheado para ROI estándar")
            else:
                # Ejecutar OCR normal
'''

# Find the end of the OCR block to add cache save
# Look for where ocr_results_lluvia is assigned from run_all_pipelines
ocr_assign_idx = content.find('ocr_results_lluvia = run_all_pipelines', idx)
if ocr_assign_idx == -1:
    print('ocr_results_lluvia assignment not found')
    exit(1)

# Find the end of that assignment line
ocr_assign_end = content.find('\n', ocr_assign_idx)

# We need to wrap the OCR execution in the else block and add cache save after
# This is complex - let's just add cache save after the OCR block
# Find where both ROIs are processed
second_roi_idx = content.find('ocr_results_lluvia_op = run_all_pipelines', idx)
if second_roi_idx == -1:
    print('second ROI not found')
    exit(1)

second_roi_end = content.find('\n', second_roi_idx)
# Find the end of the multi-pipeline if block
if_block_end = content.find('\n            elif HAS_OCR:', second_roi_end)
if if_block_end == -1:
    if_block_end = content.find('\n            # ===== DOM Fallback', second_roi_end)

print(f'Inserting cache save at {if_block_end}')
print(content[if_block_end-100:if_block_end+50])
