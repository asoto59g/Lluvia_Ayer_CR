with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add adaptive threshold check in procesar_estacion after OCR and before parse_all
# Find where parse_all is called
idx = content.find('dom_lluvia_val=dom_lluvia_val')
if idx == -1:
    print('DOM params not found')
    exit(1)

# Find the parse_all call start
call_start = content.rfind('DataParser.parse_all(', 0, idx)
if call_start == -1:
    print('parse_all call not found')
    exit(1)

# Find the line before the call
line_start = content.rfind('\n', 0, call_start) + 1

# Insert adaptive threshold logic before parse_all
adaptive_code = '''            # ===== Umbral adaptativo: si todos los OCR scores bajos, forzar DOM =====
            max_ocr_score = 0
            if ocr_results_lluvia:
                for r in ocr_results_lluvia:
                    val = extraer_valor_lluvia(r.texto)
                    if val:
                        s = validar_lluvia(val, r.texto, texto_total)
                        max_ocr_score = max(max_ocr_score, s)
            if ocr_results_lluvia_op:
                for r in ocr_results_lluvia_op:
                    val = extraer_valor_lluvia(r.texto)
                    if val:
                        s = validar_lluvia(val, r.texto, texto_total)
                        max_ocr_score = max(max_ocr_score, s)
            
            force_dom = max_ocr_score < config.ocr_min_score_threshold
            if force_dom and hasattr(page, 'frames'):
                LOGGER.info(f"  [Adaptativo] Max OCR score ({max_ocr_score}) < umbral ({config.ocr_min_score_threshold}), forzando DOM fallback")
                try:
                    dom_lluvia_val, dom_lluvia_score = await extraer_lluvia_dom(page)
                except Exception as e:
                    LOGGER.debug(f"  [DOM Fallback] Error: {e}")
            
'''

content = content[:line_start] + adaptive_code + content[line_start:]

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Phase 6.2b: Adaptive threshold logic added")