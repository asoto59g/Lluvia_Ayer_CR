with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the DOM fallback section precisely
old = '''        # Fallback DOM (patr髇 expl韈ito en texto total)
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

new = '''        # Fallback DOM: extraer_lluvia_dom (DOM estructurado)
        # Se pasa el resultado via par髇metros opcionales dom_lluvia_val / dom_lluvia_score
        if dom_lluvia_val is not None and dom_lluvia_val:
            val = dom_lluvia_val
            score = dom_lluvia_score if dom_lluvia_score is not None else validar_lluvia(val, '', texto_total)
            if score > best_score:
                best_score = score
                best_lluvia = val
                best_origin = "DOM_Estructurado"
                best_pipeline = "dom_fallback"'''

if old in content:
    content = content.replace(old, new)
    with open('scraper_v2.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Phase 4.2: parse_all updated to accept DOM fallback params")
else:
    print("Exact match not found")