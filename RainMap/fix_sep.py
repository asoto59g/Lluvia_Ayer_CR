with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('pd.read_csv(config.archivo_entrada, sep=";")', 'pd.read_csv(config.archivo_entrada)')

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed separator')