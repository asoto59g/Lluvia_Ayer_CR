with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the OCR config section
old = '''    ocr_lang: str = "spa"
    ocr_psm_primary: int = 6
    ocr_psm_fallback: int = 11
    ocr_upscale_factor: float = 2.5
    ocr_contrast_factor: float = 2.0
    
    def __post_init__(self):'''

new = '''    ocr_lang: str = "spa"
    ocr_psm_primary: int = 6
    ocr_psm_fallback: int = 11
    ocr_upscale_factor: float = 2.5
    ocr_contrast_factor: float = 2.0

    # OCR Avanzado (Fase 1)
    ocr_enable_multi_pipeline: bool = True
    ocr_enable_layout_detection: bool = True
    ocr_enable_sauvola: bool = False
    ocr_min_score_threshold: int = 50
    ocr_pipelines: List[str] = field(default_factory=lambda: ["v1", "v2", "v4"])

    def __post_init__(self):'''

if old in content:
    content = content.replace(old, new)
    with open('scraper_v2.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed")
else:
    print("Pattern not found, checking...")
    idx = content.find('ocr_contrast_factor')
    print(repr(content[idx:idx+200]))