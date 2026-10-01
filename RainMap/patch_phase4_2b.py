with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the DOM fallback section in parse_all
# The pattern has literal backslashes in the regex, not escaped
import re

# Find the DOM fallback section
pattern = re.compile(r'Fallback DOM.*?best_pipeline = \"dom_regex\"', re.DOTALL)
match = pattern.search(content)
if match:
    print('Found at:', match.start())
    print('Content:', repr(content[match.start():match.end()]))
else:
    print('Not found with regex')
    # Try simpler search
    idx = content.find('Fallback DOM')
    if idx != -1:
        print('Found at idx:', idx)
        print(content[idx:idx+500])
