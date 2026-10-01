with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 2. Add OCRResult dataclass after StationRecord
old_stationrecord = '''@dataclass
class StationRecord(StationBase, StationScraped):
    """Registro completo = base + scraped"""
    pass'''

new_stationrecord = '''@dataclass
class StationRecord(StationBase, StationScraped):
    """Registro completo = base + scraped"""
    pass


@dataclass
class OCRResult:
    """Resultado de un pipeline OCR individual."""
    pipeline: str           # v1, v2, v3, v4, dom_fallback
    layout: str             # single_line, sparse, block, auto
    psm_used: int           # PSM que dio mejor resultado
    texto: str              # Texto crudo OCR
    score: int = 0          # Score de validación 0-100
    lat_dms: str = ""       # Para coords (v6)
    lon_dms: str = ""       # Para coords (v6)
    lluvia_mm: str = ""     # Para lluvia (v2)'''

content = content.replace(old_stationrecord, new_stationrecord)

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Step 2: OCRResult dataclass added")