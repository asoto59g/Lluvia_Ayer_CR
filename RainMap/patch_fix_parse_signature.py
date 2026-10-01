with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the parse_all function signature and add the new parameters
old_sig = 'def parse_all(texto_total: str, ocr_lluvia: str, ocr_lluvia_op: str, \n                   ocr_results_lluvia: list = None, ocr_results_lluvia_op: list = None) -> Dict[str, Any]:'

new_sig = 'def parse_all(texto_total: str, ocr_lluvia: str, ocr_lluvia_op: str, \n                   ocr_results_lluvia: list = None, ocr_results_lluvia_op: list = None, \n                   dom_lluvia_val: str = None, dom_lluvia_score: int = None) -> Dict[str, Any]:'

if old_sig in content:
    content = content.replace(old_sig, new_sig)
    with open('scraper_v2.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("parse_all signature updated")
else:
    print("Old signature not found, searching...")
    idx = content.find('def parse_all')
    sig_end = content.find('):', idx)
    print('Current:', repr(content[idx:sig_end+2]))