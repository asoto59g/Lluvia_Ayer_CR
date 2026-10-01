# analyze_roi_fixed.py
import cv2
import numpy as np
import pytesseract
from pathlib import Path

BASE = Path(r"C:\Users\AlejandroSotoBarquer\OneDrive - ABC Geomática Agricola SRL\Documentos\ABC_Gis_Activos\01_Clientes\2026\Lluvia_Ayer_CR\RainMap\capturas_lluvia\20260929_224834")

TARGETS = [
    "8", "22", "30", "41", "53",
    "24", "31", "38", "46", "48",
    "59", "67", "70", "71", "74",
    "79", "80", "88", "99", "101",
    "102", "106", "111", "112", "115",
    "116", "124", "126", "127", "129",
    "132", "133", "135", "140"
]

def imread_unicode(path: Path):
    """Lee imagen con ruta Unicode en Windows."""
    data = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)

def detect_number_region(img_path: Path):
    img = imread_unicode(img_path)
    if img is None:
        return None
    
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Umbral adaptativo inverso
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 10
    )
    
    # Cerrar horizontalmente
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
    connected = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    # Contornos
    contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    best = None
    best_score = 0
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        aspect = cw / ch if ch > 0 else 0
        
        if 200 < area < w * h * 0.4 and 1.2 < aspect < 10:
            center_y_score = 1 - abs((y + ch/2) - h/2) / (h/2)
            score = area * center_y_score
            if score > best_score:
                best_score = score
                best = (x, y, cw, ch)
    
    # OCR referencia
    raw = pytesseract.image_to_string(
        gray, config="--psm 6 -c tessedit_char_whitelist=0123456789.,"
    ).strip()
    
    return {"bbox": best, "img_w": w, "img_h": h, "ocr_full": raw}

print("station_id,x,y,w,h,img_w,img_h,ocr_hint")
for sid in TARGETS:
    img_path = BASE / f"estacion_{sid}_ROI_lluvia.png"
    res = detect_number_region(img_path)
    if res and res["bbox"]:
        x, y, bw, bh = res["bbox"]
        print(f"{sid},{x},{y},{bw},{bh},{res['img_w']},{res['img_h']},{res['ocr_full']}")
    else:
        print(f"{sid},NOT_FOUND,,,," + (res["ocr_full"] if res else "LOAD_ERROR"))