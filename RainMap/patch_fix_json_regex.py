with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

idx = content.find('json_matches = re.findall')
print('Before fix:', repr(content[idx:idx+120]))

# The issue is with the quote escaping. Let's use a simpler approach - just replace that one line
fixed_line = 'json_matches = re.findall(r\'\\{[^{}]*["\'](?:rain|precip|lluvia)["\']\\s*:\\s*([0-9\\.,]+)\', script.string, re.IGNORECASE)'

line_start = content.rfind('\n', 0, idx) + 1
line_end = content.find('\n', idx)
if line_end == -1:
    line_end = len(content)

content = content[:line_start] + fixed_line + content[line_end:]

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed')