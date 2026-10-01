with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and fix the indentation error around line 756
for i, line in enumerate(lines):
    if 'for m in json_matches:' in line:
        print(f'Found at line {i}: {repr(line)}')
        # Remove this line and the next few lines until we're back to normal indentation
        j = i
        while j < len(lines) and (lines[j].startswith(' ') or lines[j].startswith('\t')):
            j += 1
        # Remove from i to j-1
        del lines[i:j]
        break

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed indentation")