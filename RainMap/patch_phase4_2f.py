with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the call to DataParser.parse_all in procesar_estacion
idx = content.find('DataParser.parse_all(')
idx2 = content.find('DataParser.parse_all(', idx + 1)
if idx2 == -1:
    idx2 = idx

# Find the lines before the call to insert the DOM extraction
call_start = content.rfind('\n', 0, idx2) + 1
# Look for where texto_total is defined
text_total_idx = content.rfind('texto_total =', 0, idx2)
if text_total_idx == -1:
    print('texto_total not found before parse_all')
    exit(1)

# Find the end of that line
text_total_end = content.find('\n', text_total_idx)

print(f'texto_total at {text_total_idx}:{text_total_end}')
print(content[text_total_idx:text_total_end])
print('---')
print(f'parse_all call at {idx2}')
print(content[idx2:idx2+200])
