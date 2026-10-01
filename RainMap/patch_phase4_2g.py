with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the texto_total line and the parse_all call
text_total_idx = content.find('texto_total = f"{texto_dom} {ocr_lluvia_txt} {ocr_lluvia_op_txt}"')
if text_total_idx == -1:
    print('texto_total line not found')
    exit(1)

# Find the end of that line
text_total_end = content.find('\n', text_total_idx)

# Insert DOM extraction after texto_total definition
insert_at = text_total_end + 1

dom_code = '''            # ===== DOM Fallback: extraer_lluvia_dom (async) =====
            dom_lluvia_val = ""
            dom_lluvia_score = 0
            if hasattr(page, 'frames'):  # page is available
                try:
                    dom_lluvia_val, dom_lluvia_score = await extraer_lluvia_dom(page)
                    if dom_lluvia_val:
                        LOGGER.info(f"  [DOM Fallback] Lluvia encontrada: {dom_lluvia_val} mm (score: {dom_lluvia_score})")
                except Exception as e:
                    LOGGER.debug(f"  [DOM Fallback] Error: {e}")
            
'''

content = content[:insert_at] + dom_code + content[insert_at:]

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("DOM extraction added before parse_all")