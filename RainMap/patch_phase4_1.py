with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add the DOM fallback function after extraer_texto_dom
marker = 'return " ".join(textos)'
# Find the LAST occurrence (in extraer_texto_dom)
idx = content.rfind(marker)
if idx == -1:
    print("Marker not found")
    exit(1)

idx_end = content.find('\n\n', idx)
if idx_end == -1:
    idx_end = idx + len(marker)

dom_fallback = '''

async def extraer_lluvia_dom(page) -> tuple[str, int]:
    """
    Busca valor de lluvia en el DOM estructurado.
    Retorna (valor_str, score) o ("", 0).
    Estrategias:
    1. Tablas HTML con palabras clave
    2. JSON embebido en scripts
    3. Meta tags geo/coord/weather
    4. Elementos con data-* attributes
    5. Texto visible con regex específico
    """
    try:
        # Estrategia 1: Tablas HTML
        for frame in page.frames:
            try:
                content = await frame.content()
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                
                # Buscar en tablas
                for table in soup.find_all('table'):
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        cell_texts = [c.get_text(strip=True).lower() for c in cells]
                        
                        # Buscar fila con 'lluvia' o 'precip' o '7am'
                        for i, cell in enumerate(cell_texts):
                            if any(kw in cell for kw in ['lluvia', 'precip', '7am', '7 am', 'ayer']):
                                # El valor suele estar en la siguiente celda
                                for j in range(i+1, len(cell_texts)):
                                    val = extraer_valor_lluvia(cell_texts[j])
                                    if val:
                                        return val, 75  # Score base para DOM estructurado
                                # O en la misma celda después de dos puntos
                                val = extraer_valor_lluvia(cells[i].get_text())
                                if val:
                                    return val, 70
            except Exception:
                pass
        
        # Estrategia 2: JSON en scripts
        for frame in page.frames:
            try:
                content = await frame.content()
                import json
                import re
                soup = BeautifulSoup(content, 'html.parser')
                for script in soup.find_all('script'):
                    if script.string:
                        # Buscar patrones tipo {"rain": 12.5, ...} o "precipitation": 12.5
                        json_matches = re.findall(r'\{[^{}]*[\"\'](?:rain|precip|lluvia)[\"\']\s*:\s*([0-9\.,]+)', script.string, re.IGNORECASE)
                        for m in json_matches:
                            val = m.replace(',', '.').strip()
                            try:
                                if 0 <= float(val) <= 999:
                                    return val, 80
                            except ValueError:
                                pass
            except Exception:
                pass
        
        # Estrategia 3: Meta tags
        for frame in page.frames:
            try:
                content = await frame.content()
                soup = BeautifulSoup(content, 'html.parser')
                for meta in soup.find_all('meta'):
                    name = meta.get('name', '') or meta.get('property', '')
                    content_val = meta.get('content', '')
                    if any(kw in name.lower() for kw in ['weather', 'rain', 'precip', 'geo']):
                        val = extraer_valor_lluvia(content_val)
                        if val:
                            return val, 65
            except Exception:
                pass
        
        # Estrategia 4: data-* attributes
        for frame in page.frames:
            try:
                content = await frame.content()
                soup = BeautifulSoup(content, 'html.parser')
                for elem in soup.find_all(attrs={'data-rain': True}):
                    val = extraer_valor_lluvia(elem.get('data-rain', ''))
                    if val:
                        return val, 70
                for elem in soup.find_all(attrs={'data-precipitation': True}):
                    val = extraer_valor_lluvia(elem.get('data-precipitation', ''))
                    if val:
                        return val, 70
                for elem in soup.find_all(attrs={'data-value': True}):
                    if 'rain' in elem.get('data-value', '').lower() or 'precip' in elem.get('data-value', '').lower():
                        val = extraer_valor_lluvia(elem.get('data-value', ''))
                        if val:
                            return val, 65
            except Exception:
                pass
        
        # Estrategia 5: Regex específico en texto visible (fallback genérico)
        texto_completo = ""
        for frame in page.frames:
            try:
                content = await frame.content()
                soup = BeautifulSoup(content, 'html.parser')
                texto_completo += " " + ' '.join(soup.get_text(separator=' ').split())
            except Exception:
                pass
        
        # Patrón explícito IMN: "De 7 am de ayer a 7 am de hoy: X mm"
        m = re.search(r'De\\s+7\\s*a\\.?m\\.?\\s+de\\s+ayer\\s+a\\s+7\\s*a\\.?m\\.?\\s+de\\s+hoy:?\\s*([0-9\\.,]+)\\s*mm', texto_completo, re.IGNORECASE)
        if m:
            return m.group(1).replace(',', '.').strip(), 70
        
        # Patrón genérico: X mm con contexto lluvia
        m = re.search(r'([0-9]+[\\.,][0-9]+|\\b[0-9]+\\b)\\s*mm', texto_completo, re.IGNORECASE)
        if m:
            val = m.group(1).replace(',', '.').strip()
            try:
                if 0 <= float(val) <= 999:
                    return val, 50
            except ValueError:
                pass
        
    except Exception as e:
        LOGGER.debug(f"  [DOM Fallback] Error: {e}")
    
    return "", 0

# Need to import extraer_valor_lluvia at module level for this function
# It's already defined, but we need to make sure it's accessible'''

content = content[:idx_end] + dom_fallback + content[idx_end:]

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Phase 4.1: extraer_lluvia_dom added")