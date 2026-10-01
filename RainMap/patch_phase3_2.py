with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the DataParser.parse_all method and replace it
old_parse = '''    @staticmethod
    def parse_all(texto_total: str, ocr_lluvia: str, ocr_lluvia_op: str) -> Dict[str, str]:
        resultado = {}
        
        # Lluvia de ayer 7am-7am (prioridad: ROI estándar -> ROI opcional -> DOM)
        lluvia_val = extraer_valor_lluvia(ocr_lluvia)
        if lluvia_val:
            resultado["Lluvia_Ayer_7am_a_7am_mm"] = lluvia_val
            resultado["Origen_Lluvia_ROI"] = "ROI_Lluvia_Estandar"
        else:
            lluvia_op_val = extraer_valor_lluvia(ocr_lluvia_op)
            if lluvia_op_val:
                resultado["Lluvia_Ayer_7am_a_7am_mm"] = lluvia_op_val
                resultado["Origen_Lluvia_ROI"] = "ROI_Lluvia_Opcional"
            else:
                m = re.search(
                    r'De\\s+7\\s*a\\.?m\\.?\\s+de\\s+ayer\\s+a\\s+7\\s*a\\.?m\\.?\\s+de\\s+hoy:?\\s*([0-9\\.,]+)\\s*mm',
                    texto_total, re.IGNORECASE
                )
                if m:
                    resultado["Lluvia_Ayer_7am_a_7am_mm"] = m.group(1).replace(',', '.').strip()
                    resultado["Origen_Lluvia_ROI"] = "DOM_HTML"
        
        # Lluvia desde 7am hoy
        m = re.search(r'Desde\\s+las?\\s+7\\s*a\\.?m\\.?:?\\s*([0-9\\.,]+)\\s*mm', texto_total, re.IGNORECASE)
        if m:
            resultado["Lluvia_Desde_7am_mm"] = m.group(1).replace(',', '.').strip()
        
        # Temperatura actual
        m = re.search(r'Temperatura\\s+Actual:?\\s*([0-9\\.,]+)\\s*°?C', texto_total, re.IGNORECASE)
        if m:
            resultado["Temperatura_Actual_C"] = m.group(1).replace(',', '.').strip()
        
        # Sensación térmica
        m = re.search(r'Sensaci[oó]n\\s+t[eé]rmica(?:\\s+Actual)?:?\\s*([0-9\\.,]+)\\s*°?C', texto_total, re.IGNORECASE)
        if m:
            resultado["Sensacion_Termica_C"] = m.group(1).replace(',', '.').strip()
        
        return resultado'''

new_parse = '''    @staticmethod
    def parse_all(texto_total: str, ocr_lluvia: str, ocr_lluvia_op: str, 
                   ocr_results_lluvia: list = None, ocr_results_lluvia_op: list = None) -> Dict[str, Any]:
        """
        Extrae campos meteorológicos desde texto combinado (DOM + OCR).
        Ahora usa multi-pipeline OCR con scoring para selección robusta.
        Retorna dict con valores + metadatos (score, pipeline_usado).
        """
        from scraper_v2 import validar_lluvia, extraer_valor_lluvia
        
        resultado = {}
        
        # ===== LLUVIA AYER 7AM-7AM: Multi-pipeline + Scoring =====
        best_lluvia = None
        best_score = -1
        best_origin = ""
        best_pipeline = ""
        
        # Candidatos: cada pipeline del ROI estándar
        if ocr_results_lluvia:
            for ocr_res in ocr_results_lluvia:
                val = extraer_valor_lluvia(ocr_res.texto)
                if val:
                    score = validar_lluvia(val, ocr_res.texto, texto_total)
                    if score > best_score:
                        best_score = score
                        best_lluvia = val
                        best_origin = "ROI_Lluvia_Estandar"
                        best_pipeline = ocr_res.pipeline
        
        # Candidatos: cada pipeline del ROI opcional
        if ocr_results_lluvia_op:
            for ocr_res in ocr_results_lluvia_op:
                val = extraer_valor_lluvia(ocr_res.texto)
                if val:
                    score = validar_lluvia(val, ocr_res.texto, texto_total)
                    if score > best_score:
                        best_score = score
                        best_lluvia = val
                        best_origin = "ROI_Lluvia_Opcional"
                        best_pipeline = ocr_res.pipeline
        
        # Fallback DOM (patrón explícito en texto total)
        m = re.search(
            r'De\\s+7\\s*a\\.?m\\.?\\s+de\\s+ayer\\s+a\\s+7\\s*a\\.?m\\.?\\s+de\\s+hoy:?\\s*([0-9\\.,]+)\\s*mm',
            texto_total, re.IGNORECASE
        )
        if m:
            val = m.group(1).replace(',', '.').strip()
            score = validar_lluvia(val, '', texto_total)
            if score > best_score:
                best_score = score
                best_lluvia = val
                best_origin = "DOM_HTML"
                best_pipeline = "dom_regex"
        
        # Fallback legacy: single OCR strings (compatibilidad)
        if best_lluvia is None:
            for ocr_text, origin in [(ocr_lluvia, "ROI_Lluvia_Estandar"), (ocr_lluvia_op, "ROI_Lluvia_Opcional")]:
                val = extraer_valor_lluvia(ocr_text)
                if val:
                    score = validar_lluvia(val, ocr_text, texto_total)
                    if score > best_score:
                        best_score = score
                        best_lluvia = val
                        best_origin = origin
                        best_pipeline = "legacy"
        
        if best_lluvia:
            resultado["Lluvia_Ayer_7am_a_7am_mm"] = best_lluvia
            resultado["Origen_Lluvia_ROI"] = best_origin
            resultado["Lluvia_Score"] = best_score
            resultado["Lluvia_Pipeline"] = best_pipeline
        
        # ===== LLUVIA DESDE 7AM HOY (sin cambios, solo regex) =====
        m = re.search(r'Desde\\s+las?\\s+7\\s*a\\.?m\\.?:?\\s*([0-9\\.,]+)\\s*mm', texto_total, re.IGNORECASE)
        if m:
            resultado["Lluvia_Desde_7am_mm"] = m.group(1).replace(',', '.').strip()
        
        # ===== TEMPERATURA ACTUAL =====
        m = re.search(r'Temperatura\\s+Actual:?\\s*([0-9\\.,]+)\\s*°?C', texto_total, re.IGNORECASE)
        if m:
            resultado["Temperatura_Actual_C"] = m.group(1).replace(',', '.').strip()
        
        # ===== SENSIACIÓN TÉRMICA =====
        m = re.search(r'Sensaci[oó]n\\s+t[eé]rmica(?:\\s+Actual)?:?\\s*([0-9\\.,]+)\\s*°?C', texto_total, re.IGNORECASE)
        if m:
            resultado["Sensacion_Termica_C"] = m.group(1).replace(',', '.').strip()
        
        return resultado'''

if old_parse in content:
    content = content.replace(old_parse, new_parse)
    with open('scraper_v2.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Phase 3.2: DataParser.parse_all updated with multi-pipeline scoring")
else:
    print("Old parse_all not found, searching...")
    idx = content.find('def parse_all')
    if idx != -1:
        print(content[idx:idx+500])
    else:
        print("parse_all not found at all")