import sys
import json
import sqlite3
import datetime
from PyQt5.QtCore import Qt, pyqtSlot, QObject, QDateTime
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                             QListWidget, QListWidgetItem, QLineEdit, QPushButton, 
                             QTableWidget, QTableWidgetItem, QLabel, QDialog, QFormLayout,
                             QDateTimeEdit, QFrame, QSizePolicy, QSpacerItem)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel

def format_timestamp(ts):
    """Convierte timestamp (en milisegundos) a cadena con fecha y hora."""
    if ts and isinstance(ts, int):
        dt = datetime.datetime.fromtimestamp(ts / 1000.0)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    return str(ts)

def timestamp_to_datetime(ts):
    """Convierte timestamp (milisegundos) a un objeto datetime."""
    if ts and isinstance(ts, int):
        return datetime.datetime.fromtimestamp(ts / 1000.0)
    return None

map_html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mapa</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  html, body {height:100%; margin:0; padding:0;}
  #map {width:100%; height:100%;}
</style>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
</head>
<body>
<div id="map"></div>
<script>
// Iconos personalizados
var defaultIcon = L.icon({
    iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
    iconSize: [25,41],
    iconAnchor: [12,41],
    popupAnchor: [1,-34],
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    shadowSize: [41,41]
});

var redIcon = L.icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
    iconSize: [25,41],
    iconAnchor: [12,41],
    popupAnchor: [1,-34],
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    shadowSize: [41,41]
});

var markersDict = {};
var channel = null;

var map = L.map('map').setView([20,0], 2);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom:19,
  attribution: '© OpenStreetMap contributors'
}).addTo(map);

function addMarker(id, lat, lon, number, timestamp, live, place) {
  var chosenIcon = defaultIcon;
  var isFinal = false;
  if (live == 'final') {
    chosenIcon = redIcon;
    isFinal = true;
  }
  var marker = L.marker([lat, lon], {icon: chosenIcon}).addTo(map);
  marker.bindTooltip(number + " - " + place + " (" + timestamp + ")");
  marker.on('dblclick', function(e) {
    var data = {id: id};
    if (channel && channel.objects && channel.objects.bridge) {
      channel.objects.bridge.onMarkerDoubleClicked(JSON.stringify(data));
    }
  });
  markersDict[id] = {
    marker: marker,
    originalIcon: chosenIcon,
    final: isFinal
  };
}

function highlightMarker(id, lat, lon) {
  if (markersDict[id]) {
    var mObj = markersDict[id];
    var marker = mObj.marker;
    map.setView([lat, lon], 15); // centra el mapa en la ubicación
    marker.setIcon(redIcon);
    if (!mObj.final) {
      // Si no es final, restaurar el icono tras 2 segundos
      setTimeout(function() {
        marker.setIcon(mObj.originalIcon);
      }, 2000);
    }
  }
}

// Inicializar QWebChannel
new QWebChannel(qt.webChannelTransport, function(ch) {
    channel = ch;
});
</script>
</body>
</html>
"""

############################################################
# Cargar datos desde msgstore.db
############################################################

conn = sqlite3.connect('msgstore.db')
c = conn.cursor()

c.execute("""
SELECT ml.message_row_id,
       j.raw_string AS number,
       ml.latitude,
       ml.longitude,
       ml.place_name,
       ml.place_address,
       ml.url,
       ml.live_location_share_duration,
       ml.live_location_final_latitude,
       ml.live_location_final_longitude,
       ml.live_location_final_timestamp,
       m.timestamp
FROM message_location ml
JOIN message m ON ml.message_row_id = m._id
JOIN chat cc ON m.chat_row_id = cc._id
JOIN jid j ON cc.jid_row_id = j._id;
""")

rows = c.fetchall()
conn.close()

data = []
data_by_id = {}
timestamps = []

for row in rows:
    message_id = row[0]
    ts_val = row[11]
    record = {
        "id": message_id,
        "number": row[1],
        "latitude": row[2],
        "longitude": row[3],
        "place_name": row[4] if row[4] else "",
        "place_address": row[5] if row[5] else "",
        "url": row[6] if row[6] else "",
        "live_duration": row[7] if row[7] else 0,
        "final_lat": row[8],
        "final_lon": row[9],
        "final_ts": row[10],
        "timestamp": ts_val
    }
    data.append(record)
    data_by_id[message_id] = record
    if ts_val is not None:
        timestamps.append(ts_val)

all_numbers = sorted(set([d["number"] for d in data]))

# Conteo por número
number_counts = {}
for d in data:
    number_counts[d["number"]] = number_counts.get(d["number"], 0) + 1

# Ordenar por número de puntos compartidos (desc)
sorted_number_counts = sorted(number_counts.items(), key=lambda x: x[1], reverse=True)

# Determinar el rango de fechas global
if timestamps:
    min_ts = min(timestamps)
    max_ts = max(timestamps)
else:
    # Si no hay datos, usar ahora
    now_ts = int(datetime.datetime.now().timestamp() * 1000)
    min_ts, max_ts = now_ts, now_ts

min_dt = timestamp_to_datetime(min_ts)
max_dt = timestamp_to_datetime(max_ts)

############################################################
# Clase Bridge para comunicación entre JS y Python
############################################################

class Bridge(QObject):
    def __init__(self, data_dict, parent=None):
        super().__init__(parent)
        self.data_dict = data_dict
        self.detail_callback = None

    def set_detail_callback(self, callback):
        self.detail_callback = callback

    @pyqtSlot(str)
    def onMarkerDoubleClicked(self, json_str):
        info = json.loads(json_str)
        marker_id = info.get("id")
        if marker_id in self.data_dict:
            record = self.data_dict[marker_id]
            if self.detail_callback:
                self.detail_callback(record)

############################################################
# Ventana de Detalle
############################################################

class DetailDialog(QDialog):
    def __init__(self, parent=None, info=None, main_window=None):
        super().__init__(parent)
        self.setWindowTitle("Detalle de Ubicación")
        self.main_window = main_window
        layout = QFormLayout()
        
        if info is None:
            info = {}
        number = info.get("number", "")
        timestamp = info.get("timestamp", 0)
        place = info.get("place_name", "")
        lat = info.get("latitude", "")
        lon = info.get("longitude", "")
        live_duration = info.get("live_duration", 0)
        final_lat = info.get("final_lat", None)
        final_lon = info.get("final_lon", None)
        final_ts = info.get("final_ts", None)

        # Formatear timestamp a fecha/hora
        timestamp_str = format_timestamp(timestamp)

        layout.addRow("Número:", QLabel(str(number)))
        layout.addRow("Fecha/Hora:", QLabel(timestamp_str))
        layout.addRow("Lugar:", QLabel(place))
        layout.addRow("Coordenadas:", QLabel(f"{lat}, {lon}"))
        
        if live_duration and live_duration > 0:
            layout.addRow("Ubicación en tiempo real:", QLabel("Sí"))
            layout.addRow("Duración (seg):", QLabel(str(live_duration)))
            if final_lat and final_lon:
                layout.addRow("Punto final:", QLabel(f"{final_lat}, {final_lon}"))
                # Agregar botón para marcar ubicación final en el mapa
                mark_button = QPushButton("Marcar ubicación final")
                mark_button.clicked.connect(lambda: self.mark_final_location(final_lat, final_lon))
                layout.addRow(mark_button)
            if final_ts is not None:
                layout.addRow("Tiempo final:", QLabel(str(final_ts)))
        else:
            layout.addRow("Ubicación en tiempo real:", QLabel("No"))

        self.setLayout(layout)

    def mark_final_location(self, lat, lon):
        if self.main_window:
            self.main_window.place_final_marker(lat, lon)

############################################################
# Ventana Principal
############################################################

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Visualización de Ubicaciones - Estilo WhatsApp")
        self.setStyleSheet("""
            QWidget {
                background-color: #ECE5DD;
                font-family: Arial;
            }
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #128C7E;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton {
                background-color: #25D366;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 5px;
            }
            QListWidget {
                background-color: #DCF8C6;
            }
            QTableWidget {
                background-color: #DCF8C6;
            }
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #128C7E;
                border-radius: 5px;
            }
        """)

        main_layout = QHBoxLayout(self)
        splitter = QSplitter(self)
        splitter.setOrientation(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Panel izquierdo (contactos)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        self.filter_line = QLineEdit()
        self.filter_line.setPlaceholderText("Filtrar Número...")
        self.filter_line.textChanged.connect(self.filter_numbers)
        
        self.number_list = QListWidget()
        self.load_number_list()

        self.number_list.itemChanged.connect(self.update_map_markers)

        self.select_all_btn = QPushButton("Seleccionar Todos")
        self.select_all_btn.clicked.connect(self.select_all_numbers)

        self.clear_sel_btn = QPushButton("Limpiar Selección")
        self.clear_sel_btn.clicked.connect(self.clear_selection)

        self.count_table = QTableWidget()
        self.count_table.setColumnCount(2)
        self.count_table.setHorizontalHeaderLabels(["Número", "Total Ubicaciones"])
        self.count_table.setRowCount(len(sorted_number_counts))
        for i, (num, cnt) in enumerate(sorted_number_counts):
            self.count_table.setItem(i, 0, QTableWidgetItem(num))
            self.count_table.setItem(i, 1, QTableWidgetItem(str(cnt)))
        self.count_table.resizeColumnsToContents()

        left_layout.addWidget(QLabel("<b>Contactos (que compartieron ubicación)</b>"))
        left_layout.addWidget(self.filter_line)
        left_layout.addWidget(self.number_list)
        left_layout.addWidget(self.select_all_btn)
        left_layout.addWidget(self.clear_sel_btn)
        left_layout.addWidget(QLabel("<b>Resumen por contacto</b>"))
        left_layout.addWidget(self.count_table)
        left_layout.addStretch()

        # Panel derecho (mapa + filtros de fechas + cuadro posiciones)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Filtro de fechas
        date_filter_layout = QHBoxLayout()
        date_filter_layout.addWidget(QLabel("Inicio:"))
        self.start_date = QDateTimeEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDateTime(min_dt if min_dt else QDateTime.currentDateTime())
        date_filter_layout.addWidget(self.start_date)

        date_filter_layout.addWidget(QLabel("Fin:"))
        self.end_date = QDateTimeEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDateTime(max_dt if max_dt else QDateTime.currentDateTime())
        date_filter_layout.addWidget(self.end_date)

        self.apply_date_filter_btn = QPushButton("Aplicar Filtro de Fecha")
        self.apply_date_filter_btn.clicked.connect(self.update_map_markers)
        date_filter_layout.addWidget(self.apply_date_filter_btn)

        right_layout.addLayout(date_filter_layout)

        # Mapa
        self.webview = QWebEngineView()
        # Aseguramos que el mapa se expanda:
        self.webview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.channel = QWebChannel(self.webview.page())
        self.bridge = Bridge(data_by_id)
        self.bridge.set_detail_callback(self.show_marker_detail)
        self.channel.registerObject('bridge', self.bridge)
        self.webview.page().setWebChannel(self.channel)

        def on_load_finished(ok):
            if ok:
                self.update_map_markers()
        
        self.webview.loadFinished.connect(on_load_finished)
        self.webview.setHtml(map_html)

        # Layout para el mapa
        map_layout = QVBoxLayout()
        map_layout.setContentsMargins(0,0,0,0)
        map_layout.addWidget(self.webview, 1)  # El "1" da prioridad de estiramiento

        # Cuadro sobrepuesto con posiciones
        self.positions_frame = QFrame()
        self.positions_frame.setVisible(True)
        positions_layout = QVBoxLayout(self.positions_frame)
        self.positions_title_layout = QHBoxLayout()
        self.positions_title_layout.addWidget(QLabel("<b>Posiciones Filtradas</b>"))

        # Botones minimizar/maximizar
        self.minimize_btn = QPushButton("Minimizar")
        self.minimize_btn.clicked.connect(self.minimize_positions)
        self.positions_title_layout.addWidget(self.minimize_btn)

        self.maximize_btn = QPushButton("Maximizar")
        self.maximize_btn.clicked.connect(self.maximize_positions)
        self.positions_title_layout.addWidget(self.maximize_btn)

        positions_layout.addLayout(self.positions_title_layout)

        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(4)
        self.positions_table.setHorizontalHeaderLabels(["Fecha/Hora", "Coordenadas", "Lugar", "Ir"])
        positions_layout.addWidget(self.positions_table)

        # Contenedor del mapa y la tabla de posiciones
        self.map_container = QWidget()
        self.map_container_layout = QVBoxLayout(self.map_container)
        self.map_container_layout.setContentsMargins(0,0,0,0)

        # Agregamos el frame de posiciones sin stretch
        self.map_container_layout.addWidget(self.positions_frame, 0)
        # Agregamos el layout del mapa con stretch = 1 para que el mapa ocupe el espacio restante
        self.map_container_layout.addLayout(map_layout, 1)

        right_layout.addWidget(self.map_container)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        
        splitter.setStretchFactor(1, 2)

        self.last_marker_info = None
        self.is_minimized = False

    def load_number_list(self):
        self.number_list.clear()
        for num in all_numbers:
            item = QListWidgetItem(num)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            # Desmarcado por defecto
            item.setCheckState(Qt.Unchecked)
            self.number_list.addItem(item)

    def filter_numbers(self, text):
        self.number_list.clear()
        filtered = [n for n in all_numbers if text.lower() in n.lower()]
        for num in filtered:
            item = QListWidgetItem(num)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Unchecked) 
            self.number_list.addItem(item)
        self.update_map_markers()

    def select_all_numbers(self):
        for i in range(self.number_list.count()):
            item = self.number_list.item(i)
            item.setCheckState(Qt.Checked)
        self.update_map_markers()

    def clear_selection(self):
        for i in range(self.number_list.count()):
            item = self.number_list.item(i)
            item.setCheckState(Qt.Unchecked)
        self.update_map_markers()

    def minimize_positions(self):
        # Oculta la tabla, dejando visibles el título y los botones.
        self.positions_table.setVisible(False)
        self.is_minimized = True

    def maximize_positions(self):
        # Muestra la tabla nuevamente.
        self.positions_table.setVisible(True)
        self.is_minimized = False

    def show_marker_detail(self, record):
        dlg = DetailDialog(info=record, main_window=self)
        dlg.exec_()

    def update_map_markers(self):
        if self.webview is None:
            return

        # Contactos chequeados
        checked_numbers = []
        for i in range(self.number_list.count()):
            item = self.number_list.item(i)
            if item.checkState() == Qt.Checked:
                checked_numbers.append(item.text())

        # Filtrar por fechas
        start_dt = self.start_date.dateTime().toPyDateTime()
        end_dt = self.end_date.dateTime().toPyDateTime()

        # Filtrar datos
        filtered_data = []
        for d_item in data:
            if d_item["number"] in checked_numbers:
                dt = timestamp_to_datetime(d_item["timestamp"])
                if dt and start_dt <= dt <= end_dt:
                    filtered_data.append(d_item)

        # Limpiar marcadores en el mapa
        js_clear = """
            Object.values(markersDict).forEach(function(mObj) {
                map.removeLayer(mObj.marker);
            });
            markersDict = {};
        """
        self.webview.page().runJavaScript(js_clear)

        # Agregar marcadores filtrados
        for d_item in filtered_data:
            number = d_item["number"]
            lat = d_item["latitude"]
            lon = d_item["longitude"]
            place = d_item["place_name"]
            ts = format_timestamp(d_item["timestamp"])
            if d_item["live_duration"] > 0 and d_item["final_lat"] is not None and d_item["final_lon"] is not None:
                live = 'final'
            elif d_item["live_duration"] > 0:
                live = 'true'
            else:
                live = 'false'
            id_val = d_item["id"]
            js_add_marker = f"addMarker({id_val}, {lat}, {lon}, '{number}', '{ts}', '{live}', '{place}');"
            self.webview.page().runJavaScript(js_add_marker)

        # Actualizar la tabla de posiciones filtradas
        self.update_positions_table(filtered_data)

    def update_positions_table(self, filtered_data):
        self.positions_table.clearContents()
        self.positions_table.setRowCount(len(filtered_data))
        for i, d_item in enumerate(filtered_data):
            ts_str = format_timestamp(d_item["timestamp"])
            lat = d_item["latitude"]
            lon = d_item["longitude"]
            coords_str = f"{lat}, {lon}"
            place = d_item["place_name"] if d_item["place_name"] else "Sin nombre"

            self.positions_table.setItem(i, 0, QTableWidgetItem(ts_str))
            self.positions_table.setItem(i, 1, QTableWidgetItem(coords_str))
            self.positions_table.setItem(i, 2, QTableWidgetItem(place))

            btn = QPushButton("Ir")
            btn.clicked.connect(lambda _, idx=i: self.go_to_marker(filtered_data[idx]))
            self.positions_table.setCellWidget(i, 3, btn)

        self.positions_table.resizeColumnsToContents()

    def go_to_marker(self, record):
        # Llama a la función JS highlightMarker para centrar y resaltar el marcador
        id_val = record["id"]
        lat = record["latitude"]
        lon = record["longitude"]
        js_code = f"highlightMarker({id_val}, {lat}, {lon});"
        self.webview.page().runJavaScript(js_code)

    def place_final_marker(self, lat, lon):
        # Añade un marcador adicional en la ubicación final en el mapa (marcador final en rojo)
        number = "Final"
        ts_str = "Ubicación Final"
        live = "final"
        final_label = "Posición Final"
        id_val = 999999  # ID ficticio
        js_add_marker = f"addMarker({id_val}, {lat}, {lon}, '{number}', '{ts_str}', '{live}', '{final_label}');"
        self.webview.page().runJavaScript(js_add_marker)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec_())
