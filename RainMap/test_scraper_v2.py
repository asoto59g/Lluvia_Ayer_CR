#!/usr/bin/env python3
"""
Tests unitarios para scraper_v2.py
Ejecuta: python -m pytest test_scraper_v2.py -v
"""
import pytest
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from scraper_v2 import (
    validar_lluvia,
    _es_lluvia_valida,
    detectar_layout_texto,
    get_psm_configs,
    extraer_valor_lluvia,
    DataParser,
    OCRResult,
    StationBase,
    StationScraped,
    StationRecord,
    CONFIG,
)


class TestValidarLluvia:
    """Tests para validar_lluvia()"""

    def test_valor_valido_con_mm(self):
        score = validar_lluvia("12.5", "Lluvia: 12.5 mm ayer", "DOM: 12.5 mm")
        assert score >= 70
        assert score <= 100

    def test_valor_cero(self):
        score = validar_lluvia("0", "0 mm", "0 mm")
        assert score >= 50

    def test_valor_año_rechazado(self):
        score = validar_lluvia("2024", "Año 2024", "2024")
        assert score == 0

    def test_valor_negativo_rechazado(self):
        score = validar_lluvia("-5", "-5 mm", "-5 mm")
        assert score == 0

    def test_valor_muy_alto_rechazado(self):
        score = validar_lluvia("1500", "1500 mm", "1500 mm")
        assert score == 0

    def test_valor_vacio(self):
        score = validar_lluvia("", "texto", "texto")
        assert score == 0

    def test_valor_no_numerico(self):
        score = validar_lluvia("abc", "abc", "abc")
        assert score == 0


class TestEsLluviaValida:
    """Tests para _es_lluvia_valida()"""

    def test_validos(self):
        assert _es_lluvia_valida("12.5") is True
        assert _es_lluvia_valida("0") is True
        assert _es_lluvia_valida("999") is True
        assert _es_lluvia_valida("12,5") is True

    def test_invalidos(self):
        assert _es_lluvia_valida("2024") is False
        assert _es_lluvia_valida("-1") is False
        assert _es_lluvia_valida("1000") is False
        assert _es_lluvia_valida("abc") is False


class TestDetectarLayout:
    """Tests para detectar_layout_texto()"""

    def test_existe_funcion(self):
        assert callable(detectar_layout_texto)

    def test_con_imagen_real(self):
        # Usa una captura real si existe
        if os.path.exists("Caplluvia.png"):
            layout = detectar_layout_texto("Caplluvia.png")
            assert layout in ["single_line", "sparse", "block", "auto"]


class TestGetPsmConfigs:
    """Tests para get_psm_configs()"""

    def test_todos_layouts(self):
        for layout in ["single_line", "sparse", "block", "auto"]:
            configs = get_psm_configs(layout)
            assert isinstance(configs, list)
            assert len(configs) >= 2
            for c in configs:
                assert c.startswith("--psm")

    def test_layout_desconocido(self):
        configs = get_psm_configs("unknown")
        assert configs == get_psm_configs("auto")


class TestExtraerValorLluvia:
    """Tests para extraer_valor_lluvia()"""

    def test_patron_estandar(self):
        val = extraer_valor_lluvia("De 7 am de ayer a 7 am de hoy: 12.5 mm")
        assert val == "12.5"

    def test_patron_decimal_coma(self):
        val = extraer_valor_lluvia("Lluvia: 12,5 mm")
        assert val == "12.5"  # Se normaliza a punto

    def test_patron_entero(self):
        val = extraer_valor_lluvia("5 mm")
        assert val == "5"

    def test_sin_coincidencia(self):
        val = extraer_valor_lluvia("Temperatura 28 C")
        assert val is None  # Retorna None si no hay match


class TestDataParser:
    """Tests para DataParser.parse_all()"""

    def test_parse_lluvia_desde_ocr_results(self):
        ocr_results = [
            OCRResult(pipeline="v1", layout="auto", psm_used=6, texto="12.5 mm lluvia ayer"),
            OCRResult(pipeline="v2", layout="auto", psm_used=7, texto="12.5 mm"),
        ]
        result = DataParser.parse_all(
            texto_total="Temperatura: 28 C",
            ocr_lluvia="",
            ocr_lluvia_op="",
            ocr_results_lluvia=ocr_results,
            ocr_results_lluvia_op=[]
        )
        assert result.get("Lluvia_Ayer_7am_a_7am_mm") == "12.5"
        assert result.get("Lluvia_Score") > 0
        assert result.get("Lluvia_Pipeline") in ["v1", "v2"]

    def test_parse_dom_fallback(self):
        result = DataParser.parse_all(
            texto_total="De 7 am de ayer a 7 am de hoy: 15.2 mm",
            ocr_lluvia="",
            ocr_lluvia_op="",
            ocr_results_lluvia=[],
            ocr_results_lluvia_op=[],
            dom_lluvia_val="15.2",
            dom_lluvia_score=75
        )
        assert result.get("Lluvia_Ayer_7am_a_7am_mm") == "15.2"
        assert result.get("Origen_Lluvia_ROI") == "DOM_Estructurado"
        assert result.get("Lluvia_Pipeline") == "dom_fallback"

    def test_parse_temperatura(self):
        result = DataParser.parse_all(
            texto_total="Temperatura Actual: 28.5 C",
            ocr_lluvia="",
            ocr_lluvia_op="",
            ocr_results_lluvia=[],
            ocr_results_lluvia_op=[]
        )
        assert result.get("Temperatura_Actual_C") == "28.5"

    def test_parse_sensacion_termica(self):
        result = DataParser.parse_all(
            texto_total="Sensación Térmica Actual: 30.2 °C",
            ocr_lluvia="",
            ocr_lluvia_op="",
            ocr_results_lluvia=[],
            ocr_results_lluvia_op=[]
        )
        assert result.get("Sensacion_Termica_C") == "30.2"


class TestStationRecord:
    """Tests para dataclasses"""

    def test_station_record_campos_nuevos(self):
        base = StationBase(
            Indice="1",
            URL="http://test",
            Nombre_Estacion="Test",
            Latitud_DMS="10N",
            Longitud_DMS="84W",
            Altitud_msnm="100",
            Region="Test",
            Latitud_Decimal="10",
            Longitud_Decimal="-84"
        )
        scraped = StationScraped(
            Fecha_Captura="2024-01-01",
            Lluvia_Score=85,
            Lluvia_Pipeline="v4"
        )
        record = StationRecord(**base.__dict__, **scraped.__dict__)
        assert hasattr(record, "Lluvia_Score")
        assert hasattr(record, "Lluvia_Pipeline")
        assert record.Lluvia_Score == 85
        assert record.Lluvia_Pipeline == "v4"


class TestConfig:
    """Tests para Config"""

    def test_campos_ocr_avanzado(self):
        assert hasattr(CONFIG, "ocr_enable_multi_pipeline")
        assert hasattr(CONFIG, "ocr_enable_layout_detection")
        assert hasattr(CONFIG, "ocr_enable_sauvola")
        assert hasattr(CONFIG, "ocr_min_score_threshold")
        assert hasattr(CONFIG, "ocr_pipelines")

    def test_campos_logging(self):
        assert hasattr(CONFIG, "log_jsonl_enabled")
        assert hasattr(CONFIG, "log_jsonl_path")

    def test_campos_cache(self):
        assert hasattr(CONFIG, "cache_enabled")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])