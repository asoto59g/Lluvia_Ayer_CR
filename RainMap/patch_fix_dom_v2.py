with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the end of extraer_lluvia_dom function (should be before procesar_estacion)
# We need to add the missing closing lines
for i, line in enumerate(lines):
    if 'async def procesar_estacion' in line:
        # Insert the missing closing of extraer_lluvia_dom before this line
        missing = [
            '        # Estrategia 5: Regex específico en texto visible\n',
            '        texto_completo = ""\n',
            '        for frame in page.frames:\n',
            '            try:\n',
            '                frame_content = await frame.content()\n',
            '                soup = BeautifulSoup(frame_content, \'html.parser\')\n',
            '                texto_completo += " " + \' \'.join(soup.get_text(separator=\' \').split())\n',
            '            except Exception:\n',
            '                pass\n',
            '\n',
            '        m = re.search(r\'De\\\\s+7\\\\s*a\\\\.?m\\\\.?\\\\s+de\\\\s+ayer\\\\s+a\\\\s+7\\\\s*a\\\\.?m\\\\.?\\\\s+de\\\\s+hoy:?\\\\s*([0-9\\\\.,]+)\\\\s*mm\', texto_completo, re.IGNORECASE)\n',
            '        if m:\n',
            '            return m.group(1).replace(",", ".").strip(), 70\n',
            '\n',
            '        m = re.search(r\'([0-9]+[\\\\.,][0-9]+|\\\\b[0-9]+\\\\b)\\\\s*mm\', texto_completo, re.IGNORECASE)\n',
            '        if m:\n',
            '            val = m.group(1).replace(",", ".").strip()\n',
            '            try:\n',
            '                if 0 <= float(val) <= 999:\n',
            '                    return val, 50\n',
            '            except ValueError:\n',
            '                pass\n',
            '        \n',
            '    except Exception as e:\n',
            '        LOGGER.debug(f"  [DOM Fallback] Error: {e}")\n',
            '    return "", 0\n',
            '\n',
            '\n'
        ]
        lines = lines[:i] + missing + lines[i:]
        break

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed DOM function ending")