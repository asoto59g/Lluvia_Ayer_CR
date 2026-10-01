with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the current parse_all function - we need to update the DOM fallback section
old_dom_fallback = '''        # Fallback DOM (patr\xf3n expl\xedcito en texto total)
        m = re.search(
            r'De\\s+7\\s+a\\.?m\\.?\\s+de\\s+ayer\\s+a\\s+7\\s+a\\.?m\\.?\\s+de\\s+hoy:?\\s*([0-9\\.,]+)\\s*mm',
            texto_total, re.IGNORECASE
        )
        if m:
            val = m.group(1).replace(',', '.').strip()
            score = validar_lluvia(val, '', texto_total)
            if score > best_score:
                best_score = score
                best_lluvia = val
                best_origin = "DOM_HTML"
                best_pipeline = "dom_regex"'''

new_dom_fallback = '''        # Fallback DOM: extraer_lluvia_dom (DOM estructurado) - ASYNC, se llama desde procesar_estacion
        # Se pasa el resultado via par\xe1metro opcional dom_lluvia_val / dom_lluvia_score
        if dom_lluvia_val is not None and dom_lluvia_val:
            val = dom_lluvia_val
            score = dom_lluvia_score if dom_lluvia_score is not None else validar_lluvia(val, '', texto_total)
            if score > best_score:
                best_score = score
                best_lluvia = val
                best_origin = "DOM_Estructurado"
                best_pipeline = "dom_fallback"'''

if old_dom_fallback in content:
    content = content.replace(old_dom_fallback, new_dom_fallback)
    with open('scraper_v2.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Phase 4.2: parse_all updated to accept DOM fallback params")
else:
    print("Old DOM fallback not found, searching...")
    idx = content.find('Fallback DOM')
    if idx != -1:
        print(content[idx:idx+400])
    else:
        print("Pattern not found")