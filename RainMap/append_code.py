with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    existing = f.read()

new_content = existing + '''

# ============================================================
# PROCESAMIENTO DE ESTACIÓN INDIVIDUAL
# ============================================================

async def procesar_estacion(
    page,
    base: StationBase,
    semaphore: asyncio.Semaphore,
    config: Config,
    carpeta_capturas: Path,
    idx: int,
    total: int,
    fecha_proceso: str
) -> StationRecord:
    """Procesa una sola estación con control de concurrencia."""
    async with semaphore:
        registro = StationRecord(
            **asdict(base),
            Fecha_Captura=fecha_proceso,
            Estado="Pendiente"
        )

        if not base.URL or not base.URL.startswith("http"):
            registro.Estado = "URL no válida"
            LOGGER.warning(f"[{idx}/{total}] URL inválida: {base.URL}")
            return registro

        LOGGER.info(f"[{idx}/{total}] Procesando: {base.URL}")

        try:
            for intento in range(config.max_retries_goto + 1):
                try:
                    await page.goto(base.URL, wait_until="domcontentloaded", timeout=config.goto_timeout_ms)
                    break
                except Exception as e:
                    if intento == config.max_retries_goto:
                        raise
                    LOGGER.warning(f"  Reintento {intento + 1}/{config.max_retries_goto} para {base.URL}: {e}")
                    await asyncio.sleep(2)

            await page.wait_for_timeout(config.wait_after_load_ms)

            await page.evaluate(f"document.body.style.zoom = '{config.zoom_level}'")
            await page.wait_for_timeout(config.wait_after_zoom_ms)

            nombre_img_full = f"estacion_{idx}_full_{config.zoom_level.replace('.', 'pct')}.png"
            ruta_img_full = carpeta_capturas / nombre_img_full
            await page.screenshot(path=str(ruta_img_full), full_page=False)
            registro.Ruta_Captura_Imagen = str(ruta_img_full)

            clip_lluvia = config.roi_lluvia
            ruta_roi_lluvia = carpeta_capturas / f"estacion_{idx}_ROI_lluvia.png"
            await page.screenshot(path=str(ruta_roi_lluvia), clip=clip_lluvia)
            registro.Ruta_ROI_Lluvia = str(ruta_roi_lluvia)

            clip_lluvia_op = config.roi_lluvia_op
            ruta_roi_lluvia_op = carpeta_capturas / f"estacion_{idx}_ROI_lluvia_op.png"
            await page.screenshot(path=str(ruta_roi_lluvia_op), clip=clip_lluvia_op)
            registro.Ruta_ROI_Lluvia_Op = str(ruta_roi_lluvia_op)

            ocr_lluvia_txt = ""
            ocr_lluvia_op_txt = ""
            if HAS_OCR:
                ocr_lluvia_txt = preprocesar_imagen_ocr(str(ruta_roi_lluvia), config)
                ocr_lluvia_op_txt = preprocesar_imagen_ocr(str(ruta_roi_lluvia_op), config)
                registro.OCR_ROI_Lluvia_Texto = " ".join(ocr_lluvia_txt.split())
                registro.OCR_ROI_Lluvia_Op_Texto = " ".join(ocr_lluvia_op_txt.split())

            texto_dom = await extraer_texto_dom(page)
            texto_total = f"{texto_dom} {ocr_lluvia_txt} {ocr_lluvia_op_txt}"

            parsed = DataParser.parse_all(texto_total, ocr_lluvia_txt, ocr_lluvia_op_txt)
            for key, value in parsed.items():
                setattr(registro, key, value)

            registro.Estado = "Éxito"

        except Exception as e:
            registro.Estado = f"Error: {type(e).__name__}: {e}"
            LOGGER.error(f"  Error procesando {base.URL}: {e}")

        return registro


# ============================================================
# GUARDADO DE DATOS
# ============================================================

def guardar_diario_csv(registros: List[StationRecord], config: Config) -> pd.DataFrame:
    """Guarda los registros del día actual en CSV y Excel diario."""
    df = pd.DataFrame([record_to_dict(r) for r in registros])
    
    for intento in range(config.max_retries_csv_write):
        try:
            df.to_csv(config.archivo_diario_csv, index=False, encoding="utf-8-sig")
            break
        except PermissionError:
            if intento == config.max_retries_csv_write - 1:
                raise
            time.sleep(1)
    
    try:
        archivo_excel = config.archivo_diario_csv.replace(".csv", ".xlsx")
        df.to_excel(archivo_excel, index=False)
    except Exception as e:
        LOGGER.warning(f"No se pudo guardar Excel diario: {e}")
    
    return df


def actualizar_historico(df_nuevo: pd.DataFrame, config: Config):
    """Añade los nuevos registros a los archivos históricos (CSV y Excel)."""
    if os.path.exists(config.archivo_hist_csv):
        try:
            df_hist = pd.read_csv(config.archivo_hist_csv)
            df_hist = pd.concat([df_hist, df_nuevo], ignore_index=True)
        except Exception:
            df_hist = df_nuevo
    else:
        df_hist = df_nuevo
    
    df_hist.to_csv(config.archivo_hist_csv, index=False, encoding="utf-8-sig")
    
    archivo_hist_excel = config.archivo_hist_csv.replace(".csv", ".xlsx")
    if os.path.exists(archivo_hist_excel):
        try:
            df_hist_excel = pd.read_excel(archivo_hist_excel)
            df_hist_excel = pd.concat([df_hist_excel, df_nuevo], ignore_index=True)
        except Exception:
            df_hist_excel = df_nuevo
    else:
        df_hist_excel = df_nuevo
    
    try:
        df_hist_excel.to_excel(archivo_hist_excel, index=False)
    except Exception as e:
        LOGGER.warning(f"No se pudo guardar Excel histórico: {e}")


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

async def main():
    config = CONFIG
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    carpeta_capturas = Path(config.carpeta_capturas_base) / timestamp_str
    carpeta_capturas.mkdir(parents=True, exist_ok=True)

    if not os.path.exists(config.archivo_entrada):
        LOGGER.error(f"No se encontró '{config.archivo_entrada}'")
        return

    try:
        df_base = pd.read_csv(config.archivo_entrada, sep=";")
    except Exception as e:
        LOGGER.error(f"Error leyendo CSV base: {e}")
        return

    estaciones_base = [station_base_from_row(row) for _, row in df_base.iterrows()]
    total = len(estaciones_base)
    fecha_proceso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    LOGGER.info(f"Iniciando extracción para {total} estaciones (concurrencia: {config.max_concurrent_stations})")

    semaphore = asyncio.Semaphore(config.max_concurrent_stations)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=config.headless)
        
        contexts = []
        pages = []
        for _ in range(config.max_concurrent_stations):
            context = await browser.new_context(
                viewport={"width": config.viewport_width, "height": config.viewport_height},
                device_scale_factor=config.device_scale_factor
            )
            page = await context.new_page()
            contexts.append(context)
            pages.append(page)

        async def worker(page, base, idx):
            return await procesar_estacion(page, base, semaphore, config, carpeta_capturas, idx, total, fecha_proceso)

        tasks = [
            worker(pages[i % config.max_concurrent_stations], base, i + 1)
            for i, base in enumerate(estaciones_base)
        ]
        
        resultados = await asyncio.gather(*tasks, return_exceptions=True)
        
        registros_finales = []
        for i, r in enumerate(resultados):
            if isinstance(r, Exception):
                LOGGER.error(f"Excepción en estación {i+1}: {r}")
                base = estaciones_base[i]
                registro = StationRecord(**asdict(base), Fecha_Captura=fecha_proceso, Estado=f"Excepción: {r}")
                registros_finales.append(registro)
            else:
                registros_finales.append(r)

        for context in contexts:
            await context.close()
        await browser.close()

    df_diario = guardar_diario_csv(registros_finales, config)
    actualizar_historico(df_diario, config)

    exitosos = sum(1 for r in registros_finales if r.Estado == "Éxito")
    LOGGER.info(f"Finalizado: {exitosos}/{total} exitosos")
    LOGGER.info(f"Diario: {config.archivo_diario_csv} | Histórico: {config.archivo_hist_csv}")


if __name__ == "__main__":
    asyncio.run(main())
'''

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print('Done')