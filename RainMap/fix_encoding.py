with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('pd.read_csv(config.archivo_entrada)', 'pd.read_csv(config.archivo_entrada, encoding="latin-1")')

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed encoding')