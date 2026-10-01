with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the log_jsonl function - missing with open
old = '''def log_jsonl(evento: str, data: dict, config: Config = CONFIG):
    """Escribe una l\u96d1ea JSONL al archivo de log estructurado."""
    if not config.log_jsonl_enabled:
        return
    
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'evento': evento,
        **data
    }
    
    try:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\\n')
    except Exception as e:
        LOGGER.debug(f'[JSONL] Error escribiendo log: {e}')'''

new = '''def log_jsonl(evento: str, data: dict, config: Config = CONFIG):
    """Escribe una l\u96d1ea JSONL al archivo de log estructurado."""
    if not config.log_jsonl_enabled:
        return
    
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'evento': evento,
        **data
    }
    
    try:
        with open(config.log_jsonl_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\\n')
    except Exception as e:
        LOGGER.debug(f'[JSONL] Error escribiendo log: {e}')'''

if old in content:
    content = content.replace(old, new)
    with open('scraper_v2.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed log_jsonl function")
else:
    print("Old function not found")
    # Find the actual content
    idx = content.find('def log_jsonl')
    print(repr(content[idx:idx+500]))