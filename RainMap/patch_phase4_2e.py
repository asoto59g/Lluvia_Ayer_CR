with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the call to DataParser.parse_all in procesar_estacion
idx = content.find('DataParser.parse_all(')
# Find the second occurrence (in procesar_estacion)
idx2 = content.find('DataParser.parse_all(', idx + 1)
if idx2 == -1:
    idx2 = idx

print(f'Found at {idx2}')
print(content[idx2:idx2+300])
