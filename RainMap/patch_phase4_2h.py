with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the parse_all call and add the DOM params
idx = content.find('DataParser.parse_all(')
idx2 = content.find('DataParser.parse_all(', idx + 1)
if idx2 == -1:
    idx2 = idx

# Find the end of the call
call_end = content.find(')', idx2)
# Need to find the matching closing paren - count parens
paren_count = 0
for i in range(idx2, len(content)):
    if content[i] == '(':
        paren_count += 1
    elif content[i] == ')':
        paren_count -= 1
        if paren_count == 0:
            call_end = i
            break

print(f'Call from {idx2} to {call_end}')
print(content[idx2:call_end+1])

# Replace the call to add dom_lluvia_val and dom_lluvia_score
old_call = content[idx2:call_end+1]
new_call = old_call.replace(
    'ocr_results_lluvia_op=ocr_results_lluvia_op',
    'ocr_results_lluvia_op=ocr_results_lluvia_op,\n                dom_lluvia_val=dom_lluvia_val,\n                dom_lluvia_score=dom_lluvia_score'
)

content = content[:idx2] + new_call + content[call_end+1:]

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("parse_all call updated with DOM params")