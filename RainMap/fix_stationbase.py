with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''@dataclass
class StationBase:
    """Campos base desde Estaciones.csv"""
    Indice: str
    URL: str
    Nombre_Estacion: str
    Latitud_DMS: str
    Longitud_DMS: str
    Altitud_msnm: str
    Region: str
    Latitud_Decimal: str
    Longitud_Decimal: str'''

new = '''@dataclass
class StationBase:
    """Campos base desde Estaciones.csv"""
    Indice: str = ""
    URL: str = ""
    Nombre_Estacion: str = ""
    Latitud_DMS: str = ""
    Longitud_DMS: str = ""
    Altitud_msnm: str = ""
    Region: str = ""
    Latitud_Decimal: str = ""
    Longitud_Decimal: str = ""'''

content = content.replace(old, new)

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed StationBase')