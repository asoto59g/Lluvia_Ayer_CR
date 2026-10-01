with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the OCR processing section in procesar_estacion
old_ocr_section = '''            ocr_lluvia_txt = ""
            ocr_lluvia_op_txt = ""
            if HAS_OCR:
                ocr_lluvia_txt = preprocesar_imagen_ocr(str(ruta_roi_lluvia), config)
                ocr_lluvia_op_txt = preprocesar_imagen_ocr(str(ruta_roi_lluvia_op), config)
                registro.OCR_ROI_Lluvia_Texto = " ".join(ocr_lluvia_txt.split())
                registro.OCR_ROI_Lluvia_Op_Texto = " ".join(ocr_lluvia_op_txt.split())

            texto_dom = await extraer_texto_dom(page)
            texto_total = f"{texto_dom} {ocr_lluvia_txt} {ocr_lluvia_op_txt}"

            parsed = DataParser.parse_all(texto_total, ocr_lluvia_txt, ocr_lluvia_op_txt)'''

new_ocr_section = '''            # ===== OCR MULTI-PIPELINE (Fase 2+3) =====
            ocr_results_lluvia = []
            ocr_results_lluvia_op = []
            ocr_lluvia_txt = ""
            ocr_lluvia_op_txt = ""
            
            if HAS_OCR and config.ocr_enable_multi_pipeline:
                # Ejecutar todos los pipelines en ambos ROIs
                ocr_results_lluvia = run_all_pipelines(str(ruta_roi_lluvia), config)
                ocr_results_lluvia_op = run_all_pipelines(str(ruta_roi_lluvia_op), config)
                
                # Combinar texto de todos los pipelines para guardar
                ocr_lluvia_txt = " ".join([r.texto for r in ocr_results_lluvia if r.texto])
                ocr_lluvia_op_txt = " ".join([r.texto for r in ocr_results_lluvia_op if r.texto])
                
                registro.OCR_ROI_Lluvia_Texto = " ".join(ocr_lluvia_txt.split())
                registro.OCR_ROI_Lluvia_Op_Texto = " ".join(ocr_lluvia_op_txt.split())
            elif HAS_OCR:
                # Fallback legacy: solo v1
                ocr_lluvia_txt = preprocesar_imagen_ocr_v1(str(ruta_roi_lluvia), config)
                ocr_lluvia_op_txt = preprocesar_imagen_ocr_v1(str(ruta_roi_lluvia_op), config)
                registro.OCR_ROI_Lluvia_Texto = " ".join(ocr_lluvia_txt.split())
                registro.OCR_ROI_Lluvia_Op_Texto = " ".join(ocr_lluvia_op_txt.split())

            texto_dom = await extraer_texto_dom(page)
            texto_total = f"{texto_dom} {ocr_lluvia_txt} {ocr_lluvia_op_txt}"

            # Pasar resultados OCR al parser para scoring
            parsed = DataParser.parse_all(
                texto_total, ocr_lluvia_txt, ocr_lluvia_op_txt,
                ocr_results_lluvia=ocr_results_lluvia,
                ocr_results_lluvia_op=ocr_results_lluvia_op
            )'''

if old_ocr_section in content:
    content = content.replace(old_ocr_section, new_ocr_section)
    with open('scraper_v2.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Phase 3.3b: procesar_estacion updated with multi-pipeline OCR")
else:
    print("Old OCR section not found, searching...")
    idx = content.find('ocr_lluvia_txt = ""')
    if idx != -1:
        print(content[idx:idx+500])
    else:
        print("Pattern not found")