with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix the broken try-except structure
# Lines 17-28 are messed up
# Should be:
# try:
#     import pytesseract
#     from PIL import Image, ImageEnhance
#     HAS_OCR = True
# except ImportError:
#     HAS_OCR = False
#     print(...)
# try:
#     from scipy.ndimage import uniform_filter
#     HAS_SCIPY = True
# except ImportError:
#     HAS_SCIPY = False

# Rebuild the import section
new_imports = [
    'try:\n',
    '    import pytesseract\n',
    '    from PIL import Image, ImageEnhance\n',
    '    HAS_OCR = True\n',
    'except ImportError:\n',
    '    HAS_OCR = False\n',
    '    print("Aviso: pytesseract/PIL no est醤 instalados. Para usar OCR ejecuta: pip install pytesseract pillow")\n',
    '\n',
    'try:\n',
    '    from scipy.ndimage import uniform_filter\n',
    '    HAS_SCIPY = True\n',
    'except ImportError:\n',
    '    HAS_SCIPY = False\n',
    '\n'
]

# Replace lines 17-28 (0-indexed: 16-27)
lines = lines[:16] + new_imports + lines[28:]

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Imports fixed")