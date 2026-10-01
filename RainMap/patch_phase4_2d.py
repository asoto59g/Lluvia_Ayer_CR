with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace using position
idx = content.find('Fallback DOM (patr')
if idx == -1:
    print('Not found')
    exit(1)

# Find the end of the section
end_idx = content.find('best_pipeline = "dom_regex"', idx)
if end_idx == -1:
    print('End not found')
    exit(1)
end_idx += len('best_pipeline = "dom_regex"')

print(f'Replacing from {idx} to {end_idx}')
print('Old content:')
print(content[idx:end_idx])

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

content = content[:idx] + new + content[end_idx:]

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Phase 4.2: parse_all updated to accept DOM fallback params")