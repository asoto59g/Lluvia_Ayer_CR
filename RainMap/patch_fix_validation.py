with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix _es_lluvia_valida to handle comma
old_es_valida = '''def _es_lluvia_valida(valor: str) -> bool:
    """Valida que el valor extraído sea una lluvia plausible (0-999 mm)."""
    try:
        v = float(valor.replace(',', '.'))
        return 0 <= v <= 999
    except ValueError:
        return False'''

new_es_valida = '''def _es_lluvia_valida(valor: str) -> bool:
    """Valida que el valor extraído sea una lluvia plausible (0-999 mm)."""
    try:
        v = float(valor.replace(',', '.'))
        return 0 <= v <= 999
    except ValueError:
        return False'''

# The function is already correct, the issue is the test expectation
# Let's fix validar_lluvia to reject negative values early
old_validar = '''def validar_lluvia(valor: str, ocr_texto: str, dom_texto: str) -> int:
    """
    Puntuación de calidad 0-100 para valor de lluvia extraído.
    Criterios:
    - 25 pts: valor presente y numérico
    - 20 pts: rango válido CR (0-999 mm)
    - 20 pts: formato decimal limpio (sin artefactos OCR)
    - 15 pts: consistencia OCR vs DOM (dígitos clave compartidos)
    - 10 pts: unidad 'mm' presente cerca del valor
    - 10 pts: contexto palabras clave (ayer, hoy, 7am, lluvia)
    """
    score = 0
    
    if not valor:
        return 0
    
    # 25 pts: valor presente y numérico
    try:
        v = float(valor.replace(',', '.'))
        score += 25
    except ValueError:
        return 0
    
    # 20 pts: rango válido CR (0-999 mm diario)
    if 0 <= v <= 999:
        score += 20
    elif v > 999:
        # Probablemente no es lluvia (año, ID, etc.)
        return 0
    
    # 20 pts: formato decimal limpio
    # Penalizar si el valor original tiene caracteres raros
    if re.match(r'^[0-9]+[\\.,]?[0-9]*$', valor.strip()):
        score += 20
    elif re.match(r'^[0-9]+[\\.,][0-9]+$', valor.strip()):
        score += 15  # decimal OK
    else:
        score += 5   # formato raro
    
    # 15 pts: consistencia OCR vs DOM - dígitos clave compartidos
    def extraer_digitos_clave(texto):
        return set(re.findall(r'[0-9]{2,3}', texto))
    
    ocr_digits = extraer_digitos_clave(ocr_texto)
    dom_digits = extraer_digitos_clave(dom_texto)
    valor_digits = set(re.findall(r'[0-9]{1,3}', valor))
    
    if ocr_digits and dom_digits:
        overlap = len(ocr_digits & dom_digits)
        score += min(15, overlap * 5)
    elif ocr_digits and valor_digits:
        # Al menos coincide con lo que sacó el OCR
        overlap = len(ocr_digits & valor_digits)
        score += min(10, overlap * 5)
    
    # 10 pts: unidad 'mm' presente cerca del valor en OCR
    if re.search(r'\\b' + re.escape(valor.replace('.', '[\\.,]')) + r'\\s*mm', ocr_texto, re.IGNORECASE):
        score += 10
    elif 'mm' in ocr_texto.lower():
        score += 5
    
    # 10 pts: contexto palabras clave
    keywords = ['ayer', 'hoy', '7am', '7 am', 'lluvia', 'precip', 'desd']
    texto_completo = (ocr_texto + ' ' + dom_texto).lower()
    keyword_count = sum(1 for kw in keywords if kw in texto_completo)
    score += min(10, keyword_count * 2)
    
    return min(100, score)'''

new_validar = '''def validar_lluvia(valor: str, ocr_texto: str, dom_texto: str) -> int:
    """
    Puntuación de calidad 0-100 para valor de lluvia extraído.
    Criterios:
    - 25 pts: valor presente y numérico
    - 20 pts: rango válido CR (0-999 mm)
    - 20 pts: formato decimal limpio (sin artefactos OCR)
    - 15 pts: consistencia OCR vs DOM (dígitos clave compartidos)
    - 10 pts: unidad 'mm' presente cerca del valor
    - 10 pts: contexto palabras clave (ayer, hoy, 7am, lluvia)
    """
    score = 0
    
    if not valor:
        return 0
    
    # 25 pts: valor presente y numérico
    try:
        v = float(valor.replace(',', '.'))
        score += 25
    except ValueError:
        return 0
    
    # 20 pts: rango válido CR (0-999 mm diario) - RECHAZAR negativos
    if 0 <= v <= 999:
        score += 20
    else:
        # Negativos o >999 no son lluvia válida
        return 0
    
    # 20 pts: formato decimal limpio
    # Penalizar si el valor original tiene caracteres raros
    if re.match(r'^[0-9]+[\\.,]?[0-9]*$', valor.strip()):
        score += 20
    elif re.match(r'^[0-9]+[\\.,][0-9]+$', valor.strip()):
        score += 15  # decimal OK
    else:
        score += 5   # formato raro
    
    # 15 pts: consistencia OCR vs DOM - dígitos clave compartidos
    def extraer_digitos_clave(texto):
        return set(re.findall(r'[0-9]{2,3}', texto))
    
    ocr_digits = extraer_digitos_clave(ocr_texto)
    dom_digits = extraer_digitos_clave(dom_texto)
    valor_digits = set(re.findall(r'[0-9]{1,3}', valor))
    
    if ocr_digits and dom_digits:
        overlap = len(ocr_digits & dom_digits)
        score += min(15, overlap * 5)
    elif ocr_digits and valor_digits:
        # Al menos coincide con lo que sacó el OCR
        overlap = len(ocr_digits & valor_digits)
        score += min(10, overlap * 5)
    
    # 10 pts: unidad 'mm' presente cerca del valor en OCR
    if re.search(r'\\b' + re.escape(valor.replace('.', '[\\.,]')) + r'\\s*mm', ocr_texto, re.IGNORECASE):
        score += 10
    elif 'mm' in ocr_texto.lower():
        score += 5
    
    # 10 pts: contexto palabras clave
    keywords = ['ayer', 'hoy', '7am', '7 am', 'lluvia', 'precip', 'desd']
    texto_completo = (ocr_texto + ' ' + dom_texto).lower()
    keyword_count = sum(1 for kw in keywords if kw in texto_completo)
    score += min(10, keyword_count * 2)
    
    return min(100, score)'''

if old_validar in content:
    content = content.replace(old_validar, new_validar)
    with open('scraper_v2.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed validar_lluvia to reject negatives")
else:
    print("Old validar not found")
    idx = content.find('def validar_lluvia')
    print(repr(content[idx:idx+100]))