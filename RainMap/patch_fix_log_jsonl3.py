with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix lines 111-115: need try: before with, and correct indentation
# Line 111 is empty, line 112 has 'with' with 8 spaces, line 113 has f.write with 12 spaces
# Should be:
#     try:
#         with open(...):
#             f.write(...)
#     except ...

lines[111] = '    try:\n'
lines[112] = '        with open(config.log_jsonl_path, \'a\', encoding=\'utf-8\') as f:\n'
lines[113] = '            f.write(json.dumps(log_entry, ensure_ascii=False) + \'\\n\')\n'
# lines[114] and 115 are already correct (except and LOGGER)

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed indentation")