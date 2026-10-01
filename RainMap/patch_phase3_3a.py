with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add new fields to StationScraped dataclass
old_scraped = '''@dataclass
class StationScraped:
    """Campos extraídos en tiempo real"""
    Fecha_Captura: str
    Lluvia_Ayer_7am_a_7am_mm: str = ""
    Origen_Lluvia_ROI: str = ""
    Lluvia_Desde_7am_mm: str = ""
    Precip_Ultima_Hora_mm: str = ""
    Temperatura_Actual_C: str = ""
    Sensacion_Termica_C: str = ""
    OCR_ROI_Lluvia_Texto: str = ""
    OCR_ROI_Lluvia_Op_Texto: str = ""
    Ruta_Captura_Imagen: str = ""
    Ruta_ROI_Lluvia: str = ""
    Ruta_ROI_Lluvia_Op: str = ""
    Estado: str = "Pendiente"'''

new_scraped = '''@dataclass
class StationScraped:
    """Campos extraídos en tiempo real"""
    Fecha_Captura: str
    Lluvia_Ayer_7am_a_7am_mm: str = ""
    Origen_Lluvia_ROI: str = ""
    Lluvia_Desde_7am_mm: str = ""
    Precip_Ultima_Hora_mm: str = ""
    Temperatura_Actual_C: str = ""
    Sensacion_Termica_C: str = ""
    OCR_ROI_Lluvia_Texto: str = ""
    OCR_ROI_Lluvia_Op_Texto: str = ""
    Ruta_Captura_Imagen: str = ""
    Ruta_ROI_Lluvia: str = ""
    Ruta_ROI_Lluvia_Op: str = ""
    Estado: str = "Pendiente"
    # Nuevos campos OCR avanzado (Fase 3)
    Lluvia_Score: int = 0
    Lluvia_Pipeline: str = ""'''

if old_scraped in content:
    content = content.replace(old_scraped, new_scraped)
    with open('scraper_v2.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Phase 3.3a: StationScraped updated with Lluvia_Score, Lluvia_Pipeline")
else:
    print("Old StationScraped not found")
    idx = content.find('class StationScraped')
    if idx != -1:
        print(content[idx:idx+600])
    else:
        print("StationScraped not found")