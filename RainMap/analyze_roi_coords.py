# analyze_roi_coords.py
# Ejecútalo en tu máquina: python analyze_roi_coords.py
# Te imprime CSV listo para copiar

import cv2
import numpy as np
import pytesseract
import os
from pathlib import Path

# ── RUTAS QUE ME PASASTE ──
IMAGE_PATHS = [
    r"C:\Users\AlejandroSotoBarquer\OneDrive - ABC Geomática Agricola SRL\Documentos\ABC_Gis_Activos\01_Clientes\2026\Lluvia_Ayer_CR\RainMap\capturas_lluvia\20260929_224834\estacion_8_ROI_lluvia.png",
    r"C:\Users\AlejandroSotoBarquer\OneDrive - ABC Geomática Agricola SRL\Documentos\ABC_Gis_Activos\01_Clientes\2026\Lluvia_Ayer_CR\RainMap\capturas_lluvia\20260929_224834\estacion_22_ROI_lluvia.png",
    r"C:\Users\AlejandroSotoBarquer\OneDrive - ABC Geomática Agricola SRL\Documentos\ABC_Gis_Activos\01_Clientes\2026\Lluvia_Ayer_CR\RainMap\capturas_lluvia\20260929_224834\estacion_30_ROI_lluvia.png",
    r"C:\Users\AlejandroSotoBarquer\OneDrive - ABC Geomática Agricola SRL\Documentos\ABC_Gis_Activos\01_Clientes\2026\Lluvia_Ayer_CR\RainMap\capturas_lluvia\20260929_224834\estacion_41_ROI_lluvia.png",
    r"C:\Users\AlejandroSotoBarquer\OneDrive - ABC Geomática Agricola SRL\Documentos\ABC_Gis_Activos\01_Clientes\2026\Lluvia_Ayer_CR\RainMap\capturas_lluvia\20260929_224834\estacion_53_ROI_lluvia.png",
]

def detect_number_region(img_path):
    """Detecta el bounding box del número grande de lluvia."""
    img = cv2.imread(img_path)
    if img is None:
        return None
    
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 1. Umbral adaptativo para aislar texto oscuro
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 10
    )
    
    # 2. Conectar componentes horizontales (números + decimal)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
    connected = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    # 3. Contornos → filtrar por área y aspect ratio típicos de número grande
    contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    best = None
    best_score = 0
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        aspect = cw / ch if ch > 0 else 0
        
        # Heurística: número de lluvia = área media, aspect ratio 2-6, no muy pequeño
        if 200 < area < w * h * 0.3 and 1.5 < aspect < 8:
            # Score: priorizar centro vertical y tamaño razonable
            center_y_score = 1 - abs((y + ch/2) - h/2) / (h/2)
            score = area * center_y_score
            if score > best_score:
                best_score = score
                best = (x, y, cw, ch)
    
    # Fallback: OCR directo en toda la imagen para ver qué lee
    raw = pytesseract.image_to_string(gray, config="--psm 6 -c tessedit_char_whitelist=0123456789.,").strip()
    
    return {
        "path": img_path,
        "img_w": w, "img_h": h,
        "bbox": best,          # (x, y, w, h) relativo a este ROI
        "ocr_full": raw
    }

print("station_id,x,y,w,h,img_w,img_h,ocr_hint")
for p in IMAGE_PATHS:
    station = Path(p).stem.split("_")[1]  # "8", "22", ...
    res = detect_number_region(p)
    if res and res["bbox"]:
        x, y, bw, bh = res["bbox"]
        print(f"{station},{x},{y},{bw},{bh},{res['img_w']},{res['img_h']},{res['ocr_full']}")
    else:
        print(f"{station},NOT_FOUND,,,," + (res["ocr_full"] if res else "LOAD_ERROR"))