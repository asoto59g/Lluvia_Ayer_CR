with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove the problematic JSON strategy lines (754-762)
# Replace with a simpler version
lines[753] = '                    # Estrategia 2: JSON en scripts (simplified)\n'
lines[754] = '                    pass\n'
# Remove the following lines until the for loop
# Find the line with 'for m in json_matches:'
for i in range(755, min(770, len(lines))):
    if 'for m in json_matches:' in lines[i]:
        # Remove lines 755 to i-1
        del lines[755:i]
        break

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("JSON strategy removed/simplified")