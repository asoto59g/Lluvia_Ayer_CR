import re

with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_func = '''def extraer_valor_lluvia(texto: str) -> Optional[str]:
    \"\"\"
    Extrae cantidad numérica en mm de lluvia desde texto OCR.

    Estrategia:
    1. Busca patrón explícito: 'De 7 am de ayer a 7 am de hoy: X mm'
    2. Busca número seguido de 'mm' cerca de palabras clave
    3. Busca número después de 'hoy:' (común en OCR)
    4. Fallback: primer decimal razonable
    \"\"\"
    if not texto:
        return None

    t = ' '.join(texto.split())  # normalizar espacios

    # 1. PATRÓN EXPLÍCITO: etiqueta completa + valor
    patrones_explicitos = [
        r'[Dd]e\\s+7\\s*[aA]\\.?[mM]\\.?\\s+de\\s+ayer\\s+a\\s+7\\s*[aA]\\.?[mM]\\.?\\s+de\\s+hoy[:;]?\\s*([0-9]+[\\.,][0-9]+|\\b[0-9]+\\b)',
        r'[Dd]e\\s+7\\s*a\\.?\\s*m\\.?\\s+de\\s+ayer\\s+a\\s+7\\s*a\\.?\\s*m\\.?\\s+de\\s+hoy[:;]?\\s*([0-9]+[\\.,][0-9]+|\\b[0-9]+\\b)',
        r'7\\s*[aA]\\.?[mM]\\.?\\s+ayer\\s+7\\s*[aA]\\.?[mM]\\.?\\s+hoy[:;]?\\s*([0-9]+[\\.,][0-9]+|\\b[0-9]+\\b)',
    ]
    for pat in patrones_explicitos:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            val = m.group(1).replace(',', '.').strip()
            if _es_lluvia_valida(val):
                return val

    # 2. BUSCAR 'mm' CERCA DE PALABRAS CLAVE
    m = re.search(r'([0-9]+[\\.,][0-9]+|\\b[0-9]+\\b)\\s*mm', t, re.IGNORECASE)
    if m:
        val = m.group(1).replace(',', '.').strip()
        if _es_lluvia_valida(val):
            return val

    # 3. BUSCAR NÚMERO DESPUÉS DE 'hoy:' O 'hoy ;'
    m = re.search(r'hoy[:;]\\s*([0-9]+[\\.,][0-9]+|\\b[0-9]+\\b)', t, re.IGNORECASE)
    if m:
        val = m.group(1).replace(',', '.').strip()
        if _es_lluvia_valida(val):
            return val

    # 4. FALLBACK: primer decimal razonable
    m = re.search(r'([0-9]+[\\.,][0-9]+)', t)
    if m:
        val = m.group(1).replace(',', '.').strip()
        if _es_lluvia_valida(val):
            return val

    return None


def _es_lluvia_valida(valor: str) -> bool:
    \"\"\"Valida que el valor extraído sea una lluvia plausible (0-999 mm).\"\"\"
    try:
        v = float(valor)
        return 0 <= v <= 999
    except ValueError:
        return False'''

# Find and replace the function
pattern = r'def extraer_valor_lluvia\(texto: str\) -> Optional\[str\]:.*?return None'
content = re.sub(pattern, new_func, content, flags=re.DOTALL)

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated')