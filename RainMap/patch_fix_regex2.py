with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the whole extraer_lluvia_dom function and replace it
start_idx = content.find('async def extraer_lluvia_dom')
if start_idx == -1:
    print('Function not found')
    exit(1)

# Find the end of the function (next async def or class or double blank line after return)
end_idx = content.find('\n\nasync def', start_idx)
if end_idx == -1:
    end_idx = content.find('\n\nclass ', start_idx)
if end_idx == -1:
    end_idx = content.find('\n\ndef ', start_idx)
if end_idx == -1:
    end_idx = len(content)

print(f'Function from {start_idx} to {end_idx}')
print(content[start_idx:start_idx+100])
print('---')
print(content[end_idx-100:end_idx])
