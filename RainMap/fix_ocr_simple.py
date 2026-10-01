with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the function and replace it
new_function = '''def extraer_valor_lluvia(texto: str) -> Optional[str]:
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
        return False
'''

# Find start and end of the function
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if 'def extraer_valor_lluvia' in line and start_idx is None:
        start_idx = i
    if start_idx is not None and line.strip() == 'return None' and end_idx is None:
        # Check if this is the end of extraer_valor_lluvia (not _es_lluvia_valida)
        # Look ahead to see if next non-empty line is def _es_lluvia_valida or class
        for j in range(i+1, min(i+5, len(lines))):
            if lines[j].strip() and not lines[j].strip().startswith('#'):
                if lines[j].strip().startswith('def ') or lines[j].strip().startswith('class '):
                    end_idx = i
                break

if start_idx is not None and end_idx is not None:
    # Replace
    new_lines = lines[:start_idx] + [new_function + '\n'] + lines[end_idx+1:]
    with open('scraper_v2.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print('Function replaced successfully')
else:
    print('Could not find function boundaries')
    print(f'start_idx={start_idx}, end_idx={end_idx}')