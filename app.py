# ----------------------------------------------------
    # PLANTILLA INTERACTIVA HTML (LEAFLET)
    # ----------------------------------------------------
    html_template = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Mapa de Lluvia Thiessen - Costa Rica</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<style>
html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
}
#map {
    width: 100%;
    height: 800px;
}

/* =========================================================
   BARRA DE DESPLAZAMIENTO MÁS ANCHA PARA MÓVILES Y POPUPS
   ========================================================= */
::-webkit-scrollbar {
    width: 14px;
    height: 14px;
}
::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 6px;
}
::-webkit-scrollbar-thumb {
    background: #888;
    border-radius: 6px;
    border: 2px solid #f1f1f1;
}
::-webkit-scrollbar-thumb:hover {
    background: #555;
}

/* Permitir scroll cómodo dentro de las ventanas emergentes (Popups) */
.leaflet-popup-content {
    max-height: 280px;
    overflow-y: auto;
    padding-right: 5px;
}

.map-title-box {
    background: rgba(255, 255, 255, 0.9);
    padding: 10px 14px;
    border-radius: 6px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    font-family: Arial, sans-serif;
    line-height: 1.35;
}
/* ... resto de tus estilos habituales ... */
</style>