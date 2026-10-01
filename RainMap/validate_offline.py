#!/usr/bin/env python3
"""
Script de validación offline para probar pipelines OCR con capturas reales.
Uso: python validate_offline.py [carpeta_capturas]
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from scraper_v2 import (
    run_all_pipelines,
    detectar_layout_texto,
    get_psm_configs,
    extraer_valor_lluvia,
    validar_lluvia,
    DataParser,
    CONFIG,
    OCRResult,
)


def validar_captura(ruta_img, config, nombre=""):
    """Ejecuta todos los pipelines y muestra resultados detallados."""
    print(f"\n{'='*60}")
    print(f"VALIDANDO: {nombre or Path(ruta_img).name}")
    print(f"{'='*60}")
    
    if not os.path.exists(ruta_img):
        print(f"  [ERROR] Archivo no encontrado: {ruta_img}")
        return None
    
    # Layout detection
    layout = detectar_layout_texto(ruta_img)
    psm_configs = get_psm_configs(layout)
    print(f"  Layout detectado: {layout}")
    print(f"  PSM configs: {psm_configs}")
    
    # Run all pipelines
    results = run_all_pipelines(ruta_img, config)
    
    print(f"\n  Resultados OCR ({len(results)} pipelines):")
    for r in results:
        val = extraer_valor_lluvia(r.texto)
        score = validar_lluvia(val, r.texto, "") if val else 0
        texto_preview = r.texto[:80].replace('\n', ' ') + "..." if len(r.texto) > 80 else r.texto.replace('\n', ' ')
        print(f"    [{r.pipeline}] PSM={r.psm_used} Layout={r.layout} Score={score}")
        print(f"        Valor extraído: {val}")
        print(f"        Texto: {texto_preview}")
    
    # Best result
    best = None
    best_score = -1
    for r in results:
        val = extraer_valor_lluvia(r.texto)
        if val:
            score = validar_lluvia(val, r.texto, "")
            if score > best_score:
                best_score = score
                best = (r.pipeline, val, score)
    
    if best:
        print(f"\n  >>> MEJOR: Pipeline={best[0]} Valor={best[1]} Score={best[2]}")
    else:
        print(f"\n  >>> NO SE ENCONTRÓ VALOR DE LLUVIA VÁLIDO")
    
    return {
        'archivo': str(ruta_img),
        'layout': layout,
        'pipelines': [
            {
                'pipeline': r.pipeline,
                'layout': r.layout,
                'psm': r.psm_used,
                'valor': extraer_valor_lluvia(r.texto),
                'score': validar_lluvia(extraer_valor_lluvia(r.texto), r.texto, "") if extraer_valor_lluvia(r.texto) else 0,
                'texto_preview': r.texto[:200]
            }
            for r in results
        ],
        'mejor': {
            'pipeline': best[0],
            'valor': best[1],
            'score': best[2]
        } if best else None
    }


def main():
    # Configurar pipelines a probar
    CONFIG.ocr_enable_sauvola = True
    CONFIG.ocr_pipelines = ['v1', 'v2', 'v3', 'v4']
    CONFIG.ocr_min_score_threshold = 50
    
    # Carpeta de capturas
    if len(sys.argv) > 1:
        carpeta = Path(sys.argv[1])
    else:
        carpeta = Path("capturas_lluvia")
    
    if not carpeta.exists():
        print(f"Carpeta no encontrada: {carpeta}")
        print("Uso: python validate_offline.py [carpeta_capturas]")
        return
    
    # Buscar imágenes
    extensiones = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff')
    imagenes = []
    for ext in extensiones:
        imagenes.extend(carpeta.glob(f'*{ext}'))
        imagenes.extend(carpeta.glob(f'*{ext.upper()}'))
    
    if not imagenes:
        print(f"No se encontraron imágenes en {carpeta}")
        return
    
    print(f"Encontradas {len(imagenes)} imágenes en {carpeta}")
    
    # Validar cada imagen
    resultados = []
    for img in sorted(imagenes):
        try:
            res = validar_captura(img, CONFIG, img.name)
            if res:
                resultados.append(res)
        except Exception as e:
            print(f"  [ERROR] {img.name}: {e}")
    
    # Resumen
    print(f"\n{'='*60}")
    print("RESUMEN")
    print(f"{'='*60}")
    
    for r in resultados:
        if r['mejor']:
            print(f"  {Path(r['archivo']).name:30s} | {r['mejor']['valor']:>6s} mm | {r['mejor']['pipeline']:>2s} | Score: {r['mejor']['score']:>3d}")
        else:
            print(f"  {Path(r['archivo']).name:30s} | {'NO ENCONTRADO':>12s}")
    
    # Guardar JSON
    output_file = Path("validacion_offline_resultados.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(f"\nResultados guardados en: {output_file}")


if __name__ == "__main__":
    main()