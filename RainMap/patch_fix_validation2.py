with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the range check to reject negatives
old_range = '''    # 20 pts: rango válido CR (0-999 mm diario)
    if 0 <= v <= 999:
        score += 20
    elif v > 999:
        # Probablemente no es lluvia (año, ID, etc.)
        return 0'''

new_range = '''    # 20 pts: rango válido CR (0-999 mm diario) - RECHAZAR negativos y >999
    if 0 <= v <= 999:
        score += 20
    else:
        # Negativos o >999 no son lluvia válida
        return 0'''

if old_range in content:
    content = content.replace(old_range, new_range)
    with open('scraper_v2.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed range check")
else:
    print("Old range check not found")