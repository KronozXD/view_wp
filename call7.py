import sys
import sqlite3
import pandas as pd
import datetime
import math
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import QFileDialog
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

DATABASE_PATH = 'msgstore.db'
MY_NUMBER = 'mi_numero@c.us'  # Ajustar con su número propio

class PandasTableModel(QtCore.QAbstractTableModel):
    def __init__(self, df=pd.DataFrame(), parent=None):
        super().__init__(parent)
        self._df = df

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._df)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self._df.columns)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == QtCore.Qt.DisplayRole:
            val = self._df.iloc[index.row(), index.column()]
            return str(val)
        return None

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role != QtCore.Qt.DisplayRole:
            return None
        if orientation == QtCore.Qt.Horizontal:
            return self._df.columns[section]
        else:
            return str(section)


class CallDetailDialog(QtWidgets.QDialog):
    def __init__(self, df_detail, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detalle de Llamadas con el Contacto")
        self.resize(600, 400)

        self.df_detail = df_detail.copy()

        layout = QtWidgets.QVBoxLayout(self)
        
        self.table_view = QtWidgets.QTableView()
        model = PandasTableModel(self.df_detail)
        self.table_view.setModel(model)
        layout.addWidget(self.table_view)

        buttons_layout = QtWidgets.QHBoxLayout()

        self.export_button = QtWidgets.QPushButton("Exportar a CSV")
        self.export_button.clicked.connect(self.export_to_csv)
        buttons_layout.addWidget(self.export_button)

        self.close_button = QtWidgets.QPushButton("Cerrar")
        self.close_button.clicked.connect(self.close)
        buttons_layout.addWidget(self.close_button)

        layout.addLayout(buttons_layout)

    def export_to_csv(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "Guardar CSV", "", "CSV Files (*.csv)", options=options)
        if file_name:
            self.df_detail.to_csv(file_name, index=False)
            QtWidgets.QMessageBox.information(self, "Exportar CSV", f"Archivo guardado en {file_name}")


class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = fig.add_subplot(111)
        super().__init__(fig)
        self.setParent(parent)
        FigureCanvas.setSizePolicy(self,
                                   QtWidgets.QSizePolicy.Expanding,
                                   QtWidgets.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)


class CallsAnalyzer(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gráfico Estrella: Mi línea al centro (Top N contactos con detalle, búsqueda y arrastre)")
        self.setGeometry(100, 100, 1000, 700)

        self.df_calls = self.load_calls()
        if self.df_calls is None or self.df_calls.empty:
            QtWidgets.QMessageBox.critical(self, "Error", "No se pudo cargar la tabla de llamadas. Verifique la BD.")
            sys.exit(1)

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)

        # Barra de búsqueda
        search_layout = QtWidgets.QHBoxLayout()
        lbl_search = QtWidgets.QLabel("Buscar contacto:")
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Escriba parte del número/contacto...")
        self.search_input.textChanged.connect(self.update_plot)
        search_layout.addWidget(lbl_search)
        search_layout.addWidget(self.search_input)

        # Controles top_n
        controls_layout = QtWidgets.QHBoxLayout()
        lbl_top = QtWidgets.QLabel("Top N contactos a mostrar:")
        self.spin_top = QtWidgets.QSpinBox()
        self.spin_top.setRange(1, 1000)
        self.spin_top.setValue(10)  # Por defecto, top 10
        self.spin_top.valueChanged.connect(self.update_plot)
        controls_layout.addWidget(lbl_top)
        controls_layout.addWidget(self.spin_top)

        main_layout.addLayout(search_layout)
        main_layout.addLayout(controls_layout)

        self.canvas = MplCanvas(self, width=5, height=4)
        main_layout.addWidget(self.canvas)

        # Diccionario/Lista para mapear objetos asociados a cada contacto
        self.contact_objects = []
        self.line_data_map = {}
        self.last_picked_line = None
        self.dragged_contact = None
        self.dragging = False

        # Eventos de interacción
        self.canvas.mpl_connect('pick_event', self.pick_event_callback)
        self.canvas.mpl_connect('button_press_event', self.on_plot_click)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.canvas.mpl_connect('button_release_event', self.on_release)

        self.update_plot()

    def load_calls(self):
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            query = """
            SELECT
                call_log._id,
                call_log.jid_row_id,
                call_log.from_me,
                call_log.call_id,
                call_log.timestamp,
                call_log.duration,
                call_log.video_call,
                call_log.call_result,
                call_log.call_type,
                jid.raw_string AS caller_jid
            FROM call_log
            LEFT JOIN jid ON call_log.jid_row_id = jid._id
            """
            df_calls = pd.read_sql_query(query, conn)
            conn.close()
            df_calls['timestamp'] = pd.to_numeric(df_calls['timestamp'], errors='coerce')
            return df_calls
        except Exception as e:
            print("Error:", e)
            return pd.DataFrame()

    def update_plot(self):
        search_text = self.search_input.text().strip().lower()
        top_n = self.spin_top.value()
        self.plot_star_diagram(MY_NUMBER, top_n, search_text)

    def convert_timestamp_to_datetime(self, ts):
        if pd.notnull(ts) and ts > 0:
            try:
                return datetime.datetime.fromtimestamp(ts/1000)
            except:
                return None
        return None

    def plot_star_diagram(self, my_number, top_n, search_text):
        self.canvas.ax.clear()
        self.line_data_map.clear()
        self.last_picked_line = None
        self.dragged_contact = None
        self.contact_objects = []

        df_agrup = self.df_calls.groupby('caller_jid').size().reset_index(name='total_llamadas')
        df_agrup = df_agrup[df_agrup['caller_jid'] != my_number]

        # Filtro por search_text
        if search_text:
            df_agrup = df_agrup[df_agrup['caller_jid'].str.contains(search_text, case=False, na=False)]

        if df_agrup.empty:
            self.canvas.ax.text(0.5,0.5,"No se han encontrado contactos con ese criterio.", 
                                ha='center', va='center')
            self.canvas.draw()
            return

        # Ordenar por total_llamadas y tomar top N
        df_agrup = df_agrup.sort_values('total_llamadas', ascending=False).head(top_n)

        num_contacts = len(df_agrup)
        radius = 5 + num_contacts * 0.2
        angle_step = 2*math.pi / num_contacts
        center_x, center_y = 0,0

        # Centro (mi línea)
        self.canvas.ax.plot(center_x, center_y, 'o', color='black')
        self.canvas.ax.text(center_x, center_y, my_number, ha='center', va='center', fontsize=10, fontweight='bold')

        i = 0
        for _, row in df_agrup.iterrows():
            contact_jid = row['caller_jid']
            total_calls = row['total_llamadas']
            angle = i * angle_step
            oc_x = center_x + radius*math.cos(angle)
            oc_y = center_y + radius*math.sin(angle)

            # Crear la línea con picker=False para la línea, porque arrastramos el contacto (texto)
            # La detección del arrastre será sobre el texto, no la línea.
            line = self.canvas.ax.plot([center_x, oc_x],[center_y, oc_y], color='blue', linestyle='-')[0]

            # Texto del contacto (con picker=True para arrastrar)
            contact_text = self.canvas.ax.text(oc_x, oc_y, contact_jid, ha='center', va='center', fontsize=9, color='blue', picker=True)
            mid_x = (center_x+oc_x)/2
            mid_y = (center_y+oc_y)/2
            calls_text = self.canvas.ax.text(mid_x, mid_y, str(total_calls), ha='center', va='center', fontsize=9, color='red')

            # Preparar detalle de las llamadas para este contacto
            df_detail = self.get_detail_df_for_contact(contact_jid)
            self.line_data_map[line] = df_detail

            obj = {
                'contact_jid': contact_jid,
                'line': line,
                'contact_text': contact_text,
                'calls_text': calls_text,
                'center_x': center_x,
                'center_y': center_y,
                'oc_x': oc_x,
                'oc_y': oc_y,
                'mid_x': mid_x,
                'mid_y': mid_y,
                'total_calls': total_calls,
                'df_detail': df_detail
            }
            self.contact_objects.append(obj)
            i += 1

        self.canvas.ax.set_xlim(-radius-2, radius+2)
        self.canvas.ax.set_ylim(-radius-2, radius+2)
        self.canvas.ax.set_aspect('equal')
        self.canvas.ax.axis('off')
        self.canvas.draw()

    def get_detail_df_for_contact(self, contact_jid):
        # Filtrar llamadas con este contacto
        df_contact = self.df_calls[self.df_calls['caller_jid'] == contact_jid].copy()
        if df_contact.empty:
            return pd.DataFrame()

        df_contact['datetime'] = df_contact['timestamp'].apply(self.convert_timestamp_to_datetime)
        df_contact['fecha'] = df_contact['datetime'].dt.date
        df_contact['hora'] = df_contact['datetime'].dt.time

        # Lógica nueva:
        # from_me=1 => Saliente
        # from_me=0 => Entrante
        # call_result=5 => Contestada
        # call_result en [0,1,2,3,4] => No contestada (Perdida)

        def tipo_llamada(row):
            if row['from_me'] == 1:
                if row['call_result'] == 5:
                    return "Saliente Contestada"
                else:
                    return "Saliente No Contestada"
            else:
                if row['call_result'] == 5:
                    return "Entrante Contestada"
                else:
                    return "Entrante Perdida"

        df_contact['tipo_llamada'] = df_contact.apply(tipo_llamada, axis=1)

        df_detail = df_contact[['fecha','hora','tipo_llamada','duration']]
        return df_detail

    def pick_event_callback(self, event):
        # Si se pickea un texto de contacto
        artist = event.artist
        for obj in self.contact_objects:
            if obj['contact_text'] == artist:
                # Iniciar arrastre
                self.dragging = True
                self.dragged_contact = obj
                mouse_x, mouse_y = event.mouseevent.xdata, event.mouseevent.ydata
                self.drag_start_pos = (obj['oc_x'], obj['oc_y'])
                self.drag_offset = (mouse_x, mouse_y)
                break

    def on_plot_click(self, event):
        # Doble clic para mostrar detalle (en la línea seleccionada previamente)
        # Aquí no tenemos selección previa en línea, pero podemos mostrar detalle
        # según el contacto arrastrado. Mejoramos la lógica:
        # No hay línea pickable directamente. Podemos buscar el contacto más cercano,
        # pero el usuario solicitó doble clic sobre la flecha del contacto?
        # Anteriormente el detalle se mostraba al hacer doble clic tras pick en la línea.
        #
        # Ahora la selección se hace en pick_event sobre el texto.
        # El usuario no mencionó cambio en la forma de doble clic. Asumiremos
        # doble clic sobre el texto del contacto no mostrará el detalle, 
        # sino que el detalle sigue mostrándose al hacer doble clic si tenemos
        # una línea seleccionada. Pero no hemos guardado last_picked_line.
        #
        # Para simplificar: ahora que movemos contactos, no hemos pickeado líneas. 
        # Ajustaremos la lógica para que al hacer doble clic sobre el TEXTO (pick_event ya lo detecta),
        # se muestre el detalle del contacto. 
        # Así: pick_event (clic simple) - solo arrastre. 
        # Doble clic (on_plot_click con event.dblclick=True), si tenemos dragged_contact?
        # 
        # Mejor: si el usuario hace doble clic sin arrastrar, que muestre detalle del contacto pickeado por último.
        # Guardemos last_picked_line no sirve porque ya no pickeamos la línea. 
        # Pickeamos el texto. Guardaremos last_picked_contact en pick_event para doble clic.

        if event.dblclick and self.dragged_contact is not None:
            # Mostrar detalle del contacto actual
            df_detail = self.dragged_contact['df_detail']
            if df_detail is not None and not df_detail.empty:
                dlg = CallDetailDialog(df_detail)
                dlg.exec_()

    def on_motion(self, event):
        if self.dragging and self.dragged_contact is not None and event.inaxes == self.canvas.ax:
            dx = event.xdata - self.drag_offset[0]
            dy = event.ydata - self.drag_offset[1]
            x, y = self.drag_start_pos
            new_x, new_y = (x+dx, y+dy)
            # Actualizar posiciones
            self.dragged_contact['oc_x'] = new_x
            self.dragged_contact['oc_y'] = new_y

            # Recalcular mid point
            cx, cy = self.dragged_contact['center_x'], self.dragged_contact['center_y']
            mid_x = (cx + new_x)/2
            mid_y = (cy + new_y)/2
            self.dragged_contact['mid_x'] = mid_x
            self.dragged_contact['mid_y'] = mid_y

            # Actualizar posiciones gráficas
            self.dragged_contact['contact_text'].set_position((new_x, new_y))
            self.dragged_contact['calls_text'].set_position((mid_x, mid_y))

            # Actualizar línea
            self.dragged_contact['line'].set_data([cx, new_x],[cy, new_y])

            self.canvas.draw()

    def on_release(self, event):
        if self.dragging:
            self.dragging = False
            self.dragged_contact = None


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = CallsAnalyzer()
    window.show()
    sys.exit(app.exec_())
