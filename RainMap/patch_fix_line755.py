with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 755 (index 754)
# The problem is the regex string escaping
# Original broken: r'\{[^{}]*["\'](?:rain|precip|lluvia)["\']\s*:\s*([0-9\.,]+)'
# Should be: r'\{[^{}]*["\'](?:rain|precip|lluvia)["\']\s*:\s*([0-9\.,]+)'
# But in Python source we need proper escaping

fixed_line = 'json_matches = re.findall(r\'\\{[^{}]*[\\"\'](?:rain|precip|lluvia)[\\"\']\\s*:\\s*([0-9\\.,]+)\', script.string, re.IGNORECASE)\n'

lines[754] = fixed_line

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Line 755 fixed")
print("New line:", repr(lines[754]))