with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add scipy import check at the top with other imports
if 'HAS_SCIPY = False' not in content:
    # Find where HAS_OCR is defined
    idx = content.find('HAS_OCR = ')
    if idx != -1:
        end_idx = content.find('\n', idx)
        scipy_check = '''
try:
    from scipy.ndimage import uniform_filter
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
'''
        content = content[:end_idx+1] + scipy_check + content[end_idx+1:]
        print("Added HAS_SCIPY check")
    else:
        print("HAS_OCR not found")

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Phase 6.1a: SciPy check added")