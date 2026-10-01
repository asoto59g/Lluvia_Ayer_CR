with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the broken regex
old = r"json_matches = re.findall(r'\\{[^{}]*[\\\"\\'](?:rain|precip|lluvia)[\\\"\\']\\s*:\\s*([0-9\\.,]+)', script.string, re.IGNORECASE)"
new = r"json_matches = re.findall(r'\\{[^{}]*[\"'](?:rain|precip|lluvia)[\"']\\s*:\\s*([0-9\\.,]+)', script.string, re.IGNORECASE)"

if old in content:
    content = content.replace(old, new)
    print("Fixed with old pattern")
else:
    # Find the actual broken line
    import re
    matches = [(m.start(), m.group()) for m in re.finditer(r'json_matches = re.findall', content)]
    for pos, match in matches:
        print(f'Found at {pos}: {content[pos:pos+150]}')
    
    # Try to find and fix the actual problematic line
    idx = content.find('json_matches = re.findall')
    if idx != -1:
        line_end = content.find('\n', idx)
        broken_line = content[idx:line_end]
        print(f'Broken line: {repr(broken_line)}')
        
        fixed_line = "json_matches = re.findall(r'\\{[^{}]*[\"\'](?:rain|precip|lluvia)[\"\']\\s*:\\s*([0-9\\.,]+)', script.string, re.IGNORECASE)"
        content = content[:idx] + fixed_line + content[line_end:]
        print("Fixed by direct replacement")

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done")