with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the log_jsonl function and fix it
in_function = False
brace_count = 0
for i, line in enumerate(lines):
    if 'def log_jsonl' in line:
        in_function = True
    if in_function:
        if 'try:' in line:
            # Next line should be the with open
            # Find the f.write line and fix the whole block
            pass
        if 'f.write(json.dumps' in line:
            # Fix this line and the surrounding block
            # Replace from try: to except
            lines[i-1] = '        with open(config.log_jsonl_path, \'a\', encoding=\'utf-8\') as f:\n'
            lines[i] = '            f.write(json.dumps(log_entry, ensure_ascii=False) + \'\\n\')\n'
            print(f'Fixed lines {i-1} and {i}')
            print(f'  {repr(lines[i-1])}')
            print(f'  {repr(lines[i])}')
            break

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed")