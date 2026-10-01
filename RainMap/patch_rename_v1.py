with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Rename original function to v1
old = 'def preprocesar_imagen_ocr(ruta_img, config: Config = CONFIG) -> str:'
new = 'def preprocesar_imagen_ocr_v1(ruta_img, config: Config = CONFIG) -> str:'
content = content.replace(old, new)

# Also update the docstring reference
old_doc = '"""\n    Mejora la imagen y ejecuta OCR con Tesseract.\n    """'
new_doc = '"""\n    Pipeline v1 (original): DSF=2.0, resize 2.5x, escala de grises, contraste 2.0x, PSM 6/11.\n    """'
content = content.replace(old_doc, new_doc)

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Renamed original to v1")