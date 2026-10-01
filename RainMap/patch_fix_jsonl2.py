with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and fix the broken line
for i, line in enumerate(lines):
    if 'json.dumps(log_entry' in line:
        print(f'Line {i}: {repr(line)}')
        # The issue is the newline in the string literal
        lines[i] = line.replace("'+ '\n')", "'+ '\\\\n')")
        print(f'Fixed: {repr(lines[i])}')
        break

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed")