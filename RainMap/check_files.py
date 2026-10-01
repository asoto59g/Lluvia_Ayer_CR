# check_files.py
from pathlib import Path

base = Path(r"C:\Users\AlejandroSotoBarquer\OneDrive - ABC Geomática Agricola SRL\Documentos\ABC_Gis_Activos\01_Clientes\2026\Lluvia_Ayer_CR\RainMap\capturas_lluvia\20260929_224834")

print("Directorio existe:", base.exists())
print("\nArchivos *ROI_lluvia.png encontrados:")
for f in base.glob("*ROI_lluvia.png"):
    print(f"  {f.name}")

print("\nArchivos *full*.png (primeros 10):")
for f in list(base.glob("*full*.png"))[:10]:
    print(f"  {f.name}")