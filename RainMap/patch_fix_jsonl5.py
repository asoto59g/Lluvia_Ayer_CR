with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix lines 113-114
lines[113] = "            f.write(json.dumps(log_entry, ensure_ascii=False) + '\\\\n')\n"
del lines[114]

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed")