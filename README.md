<img width="1365" height="601" alt="preview" src="https://github.com/user-attachments/assets/f15c5c3d-c530-46fa-bf17-39bc9cb876cb" />


# Lluvia Ayer CR

Link para generar mapas de lluvia diaria: https://lluviaayercr-bamei6jypmye7uhfsrlpzq.streamlit.app/

Datos desde 26set2026

Este repositorio contiene dos scripts principales que permiten **obtener, procesar y visualizar** los datos de precipitación diaria de 138 estaciones meteorológicas de Costa Rica.

## Scripts

| Archivo | Función | Uso principal |
|---------|---------|---------------|
| `scraper_v3.py` | **Scraper** que visita la página web de cada estación, extrae la cantidad de lluvia (mm) de la jornada anterior (7 am → 7 am) y guarda los resultados en dos CSV:
- `lluviadiaria.csv` (datos del día actual) 
- `histlluviadiaria.csv` (histórico acumulado) | ```powershell
python scraper_v3.py
``` |
| `app.py` | **Generador de mapa** que carga el histórico (o el diario) y construye polígonos de Thiessen (Voronoi) para cada estación, coloreándolos según la cantidad de lluvia. Produce una visualización estática embebida como *data‑uri* que puede mostrarse en Streamlit o abrirse directamente en el navegador. | ```powershell
python app.py --fecha 2026-09-27   # muestra la fecha especificada
python app.py                     # usa la fecha más reciente disponible
``` |

## Dependencias

El archivo `requirements.txt` lista las librerías necesarias (pandas, numpy, geopandas, shapely, matplotlib, playwright, pytesseract y requests). Instálalas con:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium  # necesario para el scraper
```

## Flujo de trabajo recomendado

1. **Ejecutar el scraper** (idealmente a través de un cron/GitHub Action) para generar `lluviadiaria.csv` y actualizar el histórico.
2. **Ejecutar `app.py`** con la fecha deseada para producir el mapa de precipitación.
3. (Opcional) **Desplegar con Streamlit** para una UI interactiva que permita seleccionar la fecha mediante un *selectbox*.

## Notas técnicas
- El scraper usa **Playwright** (headless Chromium) y OCR con **Tesseract**. Se implementó una estrategia de *fallback* que captura la página completa cuando las regiones de interés (ROI) específicas fallan.
- `app.py` ahora normaliza automáticamente las fechas del CSV a formato ISO (`YYYY‑MM‑DD`) y maneja diferentes codificaciones (`utf‑8‑sig` y `latin1`).
- Se añadió un mecanismo de registro (`logging`) para facilitar la depuración.

---

## Contribuciones
Los pull requests son bienvenidos. Por favor, mantén el mismo estilo de código y actualiza el *README* si añades funcionalidades.

---

## Licencia
Este proyecto está licenciado bajo la licencia MIT (ver `LICENSE` a continuación).
