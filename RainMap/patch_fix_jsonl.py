with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the JSONL line - the newline escape is broken
old = "f.write(json.dumps(log_entry, ensure_ascii=False) + '\\n')"
new = "f.write(json.dumps(log_entry, ensure_ascii=False) + '\\\\n')"

if old in content:
    content = content.replace(old, new)
    with open('scraper_v2.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed")
else:
    print("Pattern not found")
    idx = content.find('json.dumps')
    print(repr(content[idx:idx+60]))