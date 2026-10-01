with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix _es_lluvia_valida - it's already correct but the test expects comma to work
# Actually the function does replace comma with dot, so it should work
# Let me check the actual function
idx = content.find('def _es_lluvia_valida')
print('Current _es_lluvia_valida:')
print(content[idx:idx+200])
