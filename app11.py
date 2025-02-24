import sys
import sqlite3
import pandas as pd
import os
import datetime
from PyQt5 import QtWidgets, QtGui, QtCore

CHATS_BATCH_SIZE = 500
MESSAGES_BATCH_SIZE = 500
BASE_MEDIA_PATH = r'F:\Nuevacarpeta\media'  # Ajustar ruta
DATABASE_PATH = 'msgstore.db'

MAX_IMAGE_WIDTH = 300

class ChatsModel(QtCore.QAbstractListModel):
    def __init__(self, chats_df, parent=None):
        super().__init__(parent)
        self.chats_df = chats_df

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.chats_df)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == QtCore.Qt.DisplayRole:
            return self.chats_df.iloc[index.row()]['chat_display_name']
        if role == QtCore.Qt.UserRole:
            return self.chats_df.iloc[index.row()]['chat_jid']
        return None

    def update_chats(self, new_df):
        self.beginResetModel()
        self.chats_df = new_df
        self.endResetModel()

class MessagesModel(QtCore.QAbstractListModel):
    def __init__(self, messages_df, parent=None):
        super().__init__(parent)
        self.messages_df = messages_df
        self.loaded_count = 0
        self.messages_batch_size = MESSAGES_BATCH_SIZE

    def rowCount(self, parent=QtCore.QModelIndex()):
        return self.loaded_count

    def canFetchMore(self, parent=QtCore.QModelIndex()):
        return self.loaded_count < len(self.messages_df)

    def fetchMore(self, parent=QtCore.QModelIndex()):
        remainder = len(self.messages_df) - self.loaded_count
        items_to_fetch = min(self.messages_batch_size, remainder)
        if items_to_fetch > 0:
            self.beginInsertRows(QtCore.QModelIndex(), self.loaded_count, self.loaded_count + items_to_fetch - 1)
            self.loaded_count += items_to_fetch
            self.endInsertRows()

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        if index.row() >= self.loaded_count:
            return None
        msg = self.messages_df.iloc[index.row()]
        if role == QtCore.Qt.UserRole:
            return msg.to_dict()
        if role == QtCore.Qt.DisplayRole:
            return msg['text_data']
        return None

    def update_messages(self, new_df):
        self.beginResetModel()
        self.messages_df = new_df
        self.loaded_count = 0
        self.endResetModel()

class MessageDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, base_media_path, parent=None):
        super().__init__(parent)
        self.base_media_path = base_media_path
        self.image_cache = {}

    def paint(self, painter, option, index):
        painter.save()
        msg = index.data(QtCore.Qt.UserRole)
        if not msg:
            painter.restore()
            return

        from_me = msg.get('from_me', 0)
        background_color = QtGui.QColor('#dcf8c6' if from_me == 1 else '#ffffff')

        rect = option.rect
        margin = 5
        painter.setPen(QtGui.QColor('#dcdcdc'))
        painter.setBrush(background_color)
        painter.drawRoundedRect(rect.adjusted(margin, margin, -margin, -margin), 10, 10)

        message_type = msg.get('message_type', 0)
        text_data = msg.get('text_data', '')
        media_caption = msg.get('media_caption', '')
        file_path = msg.get('file_path', '')
        timestamp = msg.get('display_timestamp', '')

        latitude = msg.get('latitude', None)
        longitude = msg.get('longitude', None)
        place_name = msg.get('place_name', '')
        place_address = msg.get('place_address', '')
        url = msg.get('url', '')

        display_text = self.get_display_text(message_type, text_data, media_caption, latitude, longitude, place_name, place_address, url)

        painter.setPen(QtGui.QColor('#303030'))
        font = option.font
        font.setPointSize(12)
        painter.setFont(font)

        content_rect = rect.adjusted(margin+10, margin+10, -margin-10, -margin-10)
        x = content_rect.x()
        y = content_rect.y()

        fm = painter.fontMetrics()
        text_width = content_rect.width()

        if message_type == 1 and file_path:
            pix = self.load_image(index.row(), file_path)
            if pix:
                painter.drawPixmap(x, y, pix)
                y += pix.height() + 5
                y = self.draw_green_button(painter, x, y, "Ver Imagen", fm)

        if message_type == 2:
            y = self.draw_green_button(painter, x, y, "Reproducir (Audio)", fm)
        elif message_type == 3:
            y = self.draw_green_button(painter, x, y, "Reproducir (Video)", fm)

        if message_type == 5:
            y = self.draw_green_button(painter, x, y, "Ver Ubicación", fm)

        text_bound = fm.boundingRect(0,0,text_width,100000, QtCore.Qt.TextWordWrap, display_text)
        text_rect = QtCore.QRect(x, y, text_width, text_bound.height())
        painter.drawText(text_rect, QtCore.Qt.TextWordWrap, display_text)
        y += text_bound.height()

        if timestamp:
            time_font = QtGui.QFont(option.font)
            time_font.setPointSize(8)
            painter.setFont(time_font)
            painter.setPen(QtGui.QColor('gray'))
            time_fm = QtGui.QFontMetrics(time_font)
            time_height = time_fm.height() + 5
            time_y = y + 5
            time_rect = QtCore.QRect(x, time_y, text_width, time_height)
            painter.drawText(time_rect, QtCore.Qt.AlignRight, timestamp)
            y += time_height

        painter.restore()

    def sizeHint(self, option, index):
        msg = index.data(QtCore.Qt.UserRole)
        if not msg:
            return super().sizeHint(option, index)

        rect_width = option.rect.width() - 40
        message_type = msg.get('message_type', 0)
        text_data = msg.get('text_data', '')
        media_caption = msg.get('media_caption', '')
        file_path = msg.get('file_path', '')
        timestamp = msg.get('display_timestamp', '')

        latitude = msg.get('latitude', None)
        longitude = msg.get('longitude', None)
        place_name = msg.get('place_name', '')
        place_address = msg.get('place_address', '')
        url = msg.get('url', '')

        display_text = self.get_display_text(message_type, text_data, media_caption, latitude, longitude, place_name, place_address, url)

        base_font = option.font
        base_font.setPointSize(12)
        fm = QtGui.QFontMetrics(base_font)

        image_height = 0
        button_height_for_image = 0
        if message_type == 1 and file_path:
            pix = self.load_image(index.row(), file_path)
            if pix:
                image_height = pix.height() + 5
                button_height_for_image = self.button_height("Ver Imagen", fm)

        media_extra = 0
        if message_type == 2:
            media_text = "Reproducir (Audio)"
            media_extra += self.button_height(media_text, fm)
        elif message_type == 3:
            media_text = "Reproducir (Video)"
            media_extra += self.button_height(media_text, fm)

        loc_extra = 0
        if message_type == 5:
            loc_extra += self.button_height("Ver Ubicación", fm)

        text_bound = fm.boundingRect(0,0,rect_width,100000, QtCore.Qt.TextWordWrap, display_text)
        text_height = text_bound.height()

        time_height = 0
        if timestamp:
            time_font = QtGui.QFont(option.font)
            time_font.setPointSize(8)
            time_fm = QtGui.QFontMetrics(time_font)
            time_height = time_fm.height() + 5

        total_height = image_height + button_height_for_image + media_extra + loc_extra + text_height + time_height + 30
        return QtCore.QSize(option.rect.width(), total_height)

    def get_display_text(self, message_type, text_data, media_caption, latitude, longitude, place_name, place_address, url):
        media_types = {
            0: 'Texto',
            1: 'Imagen',
            2: 'Audio',
            3: 'Video',
            4: 'Contacto',
            5: 'Ubicación',
            9: 'Documento',
            13: 'Llamada',
        }
        if message_type != 0 and message_type not in (2,3,5):
            media_type = media_types.get(message_type, 'Desconocido')
            media_desc = f"[{media_type}]"
            if media_caption:
                media_desc += f" {media_caption}"
            display_text = (media_desc + "\n" + text_data).strip()
        elif message_type == 5:
            media_type = media_types.get(message_type, 'Ubicación')
            media_desc = f"[{media_type}]"
            loc_info = []
            if place_name:  # Mostrar place_name solo si no está vacío
                loc_info.append(f"Nombre: {place_name}")
            if place_address:
                loc_info.append(f"Dirección: {place_address}")
            if latitude is not None and longitude is not None:
                loc_info.append(f"Lat: {latitude}, Lon: {longitude}")
            if url:
                loc_info.append(f"URL (original): {url}")
            loc_text = "\n".join(loc_info)
            display_text = (media_desc + "\n" + loc_text + "\n" + text_data).strip()
        else:
            display_text = text_data if text_data else "[Mensaje vacío]"
        return display_text

    def load_image(self, row, file_path):
        if row in self.image_cache:
            return self.image_cache[row]

        full_path = self.adjust_media_path(file_path)
        if os.path.exists(full_path):
            pix = QtGui.QPixmap(full_path)
            if not pix.isNull():
                pix = pix.scaledToWidth(MAX_IMAGE_WIDTH, QtCore.Qt.SmoothTransformation)
                self.image_cache[row] = pix
                return pix
        self.image_cache[row] = None
        return None

    def adjust_media_path(self, path):
        if path.startswith('Media/'):
            path = path[len('Media/'):]
        adjusted_path = os.path.join(self.base_media_path, *path.split('/'))
        return adjusted_path

    def draw_green_button(self, painter, x, y, text, fm):
        button_font = QtGui.QFont(painter.font())
        button_font.setBold(True)
        painter.setFont(button_font)

        text_width = fm.width(text)
        button_width = text_width + 20
        button_height = fm.height() + 10
        rect = QtCore.QRect(x, y, button_width, button_height)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor("#128C7E"))
        painter.drawRoundedRect(rect, 5, 5)
        painter.setPen(QtGui.QColor("#ffffff"))
        painter.drawText(rect, QtCore.Qt.AlignCenter, text)
        painter.setFont(QtGui.QFont(painter.font()))
        return y + button_height + 5

    def button_height(self, text, fm):
        return fm.height() + 10 + 5

class WhatsAppViewer(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Visualizador de WhatsApp (Rango Fecha 01/01/2020 y Ubicaciones)")
        self.setGeometry(100, 100, 1000, 600)
        self.base_media_path = BASE_MEDIA_PATH

        self.all_conversations = pd.DataFrame()
        self.filtered_chats = pd.DataFrame()
        self.messages_df = pd.DataFrame()
        self.selected_chat_jid = None
        self.scroll_loading_messages = False

        self.load_data()
        self.create_widgets()

    def load_data(self):
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            query = """
            SELECT
                message._id,
                message.key_id,
                message.chat_row_id,
                message.from_me,
                message.sender_jid_row_id,
                message.status,
                message.timestamp,
                message.message_type,
                message.text_data,
                jid.raw_string AS sender_jid,
                chat.subject AS chat_name,
                chat_jid.raw_string AS chat_jid,
                message_media.file_path,
                message_media.media_name,
                message_media.file_size AS media_size,
                message_media.media_caption,
                message_media.media_duration,
                message_media.mime_type AS media_mime_type,
                message_media.width,
                message_media.height,
                message_location.latitude,
                message_location.longitude,
                message_location.place_name,
                message_location.place_address,
                message_location.url,
                message_location.live_location_share_duration,
                message_location.live_location_sequence_number,
                message_location.live_location_final_latitude,
                message_location.live_location_final_longitude,
                message_location.live_location_final_timestamp,
                message_location.map_download_status
            FROM message
            LEFT JOIN jid ON message.sender_jid_row_id = jid._id
            LEFT JOIN chat ON message.chat_row_id = chat._id
            LEFT JOIN jid AS chat_jid ON chat.jid_row_id = chat_jid._id
            LEFT JOIN message_media ON message._id = message_media.message_row_id
            LEFT JOIN message_location ON message._id = message_location.message_row_id
            """
            df_messages = pd.read_sql_query(query, conn)
            conn.close()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error al leer los mensajes", str(e))
            sys.exit(1)

        df_messages['timestamp'] = pd.to_numeric(df_messages['timestamp'], errors='coerce')
        df_messages['timestamp_raw'] = df_messages['timestamp']
        df_messages['display_timestamp'] = df_messages['timestamp_raw'].apply(self.convert_timestamp)

        df_messages['from_me'] = df_messages['from_me'].fillna(0).astype(int)
        df_messages['text_data'] = df_messages['text_data'].fillna('')
        df_messages['sender_jid'] = df_messages['sender_jid'].fillna('Desconocido')
        df_messages['chat_name'] = df_messages['chat_name'].fillna('')
        df_messages['chat_jid'] = df_messages['chat_jid'].fillna('')
        df_messages['message_type'] = df_messages['message_type'].fillna(0).astype(int)
        df_messages['media_name'] = df_messages['media_name'].fillna('')
        df_messages['media_caption'] = df_messages['media_caption'].fillna('')
        df_messages['file_path'] = df_messages['file_path'].fillna('')
        df_messages['media_mime_type'] = df_messages['media_mime_type'].fillna('')
        df_messages['media_duration'] = df_messages['media_duration'].fillna(0).astype(int)
        df_messages['media_size'] = df_messages.get('media_size', 0).fillna(0).astype(int)

        location_cols = [
            'latitude','longitude','place_name','place_address','url',
            'live_location_share_duration','live_location_sequence_number',
            'live_location_final_latitude','live_location_final_longitude',
            'live_location_final_timestamp','map_download_status'
        ]
        for col in location_cols:
            if col in df_messages.columns:
                df_messages[col] = df_messages[col].fillna('')

        df_messages['latitude'] = pd.to_numeric(df_messages['latitude'], errors='coerce')
        df_messages['longitude'] = pd.to_numeric(df_messages['longitude'], errors='coerce')

        df_messages['chat_display_name'] = df_messages.apply(
            lambda row: row['chat_name'] if row['chat_name'] else row['chat_jid'], axis=1
        )

        conversaciones = df_messages.sort_values('timestamp_raw', ascending=False).drop_duplicates('chat_jid')
        conversaciones = conversaciones.sort_values(by='timestamp_raw', ascending=False).reset_index(drop=True)
        conversaciones = conversaciones[['chat_jid', 'chat_display_name', 'text_data', 'display_timestamp', 'timestamp_raw']]

        self.all_conversations = conversaciones
        self.filtered_chats = self.all_conversations
        self.df_messages = df_messages

    def convert_timestamp(self, ts):
        if pd.notnull(ts) and ts > 0:
            try:
                return datetime.datetime.fromtimestamp(ts / 1000).strftime('%d/%m/%Y %H:%M:%S')
            except Exception:
                return None
        else:
            return None

    def create_widgets(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #ECE5DD;
            }
            QListView {
                background-color: #FFFFFF;
                font-size: 14px;
            }
            QLineEdit {
                font-size: 14px;
            }
            QPushButton {
                font-size: 14px;
            }
        """)

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QHBoxLayout(central_widget)

        # Panel izquierdo: Chats
        left_layout = QtWidgets.QVBoxLayout()
        chat_header = QtWidgets.QLabel("Chats")
        chat_header.setStyleSheet("background-color: #075E54; color: #FFFFFF; font-size: 16px; padding: 10px;")
        left_layout.addWidget(chat_header)

        chat_search_layout = QtWidgets.QHBoxLayout()
        chat_search_label = QtWidgets.QLabel("Buscar:")
        chat_search_label.setStyleSheet("font-weight: bold; color: #075E54;")
        self.chat_search_input = QtWidgets.QLineEdit()
        self.chat_search_input.setPlaceholderText("Buscar chats...")
        self.chat_search_input.textChanged.connect(self.filter_chats)
        chat_search_layout.addWidget(chat_search_label)
        chat_search_layout.addWidget(self.chat_search_input)
        left_layout.addLayout(chat_search_layout)

        self.chat_list_view = QtWidgets.QListView()
        self.chat_model = ChatsModel(self.filtered_chats)
        self.chat_list_view.setModel(self.chat_model)
        self.chat_list_view.clicked.connect(self.select_chat)
        left_layout.addWidget(self.chat_list_view)

        # Panel derecho: Mensajes
        right_layout = QtWidgets.QVBoxLayout()

        self.message_header = QtWidgets.QLabel("Seleccione un chat")
        self.message_header.setStyleSheet("background-color: #075E54; color: #FFFFFF; font-size: 16px; padding: 10px;")
        right_layout.addWidget(self.message_header)

        message_search_layout = QtWidgets.QHBoxLayout()
        message_search_label = QtWidgets.QLabel("Buscar:")
        message_search_label.setStyleSheet("font-weight: bold; color: #075E54;")

        self.message_search_input = QtWidgets.QLineEdit()
        self.message_search_input.setPlaceholderText("Texto a buscar en mensajes...")
        self.message_search_input.textChanged.connect(self.filter_messages)

        self.type_filter = QtWidgets.QComboBox()
        self.type_filter.addItem("Todos")
        self.type_filter.addItem("Solo Imágenes")
        self.type_filter.addItem("Solo Videos")
        self.type_filter.addItem("Solo Audio")
        self.type_filter.addItem("Solo Ubicaciones")

        self.type_filter.currentIndexChanged.connect(self.filter_messages)

        # Fecha inicial en 01/01/2020
        self.date_from = QtWidgets.QDateEdit(QtCore.QDate(2020,1,1))
        self.date_from.setCalendarPopup(True)
        self.date_to = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_from.dateChanged.connect(self.filter_messages)
        self.date_to.dateChanged.connect(self.filter_messages)

        date_label = QtWidgets.QLabel("Rango Fechas:")
        date_label.setStyleSheet("font-weight: bold; color: #075E54;")

        clear_filters_button = QtWidgets.QPushButton("Limpiar Filtros")
        clear_filters_button.setStyleSheet("background-color: #128C7E; color: #FFFFFF; font-weight: bold; border-radius: 5px; padding: 5px;")
        clear_filters_button.clicked.connect(self.clear_filters)

        message_search_layout.addWidget(message_search_label)
        message_search_layout.addWidget(self.message_search_input)
        message_search_layout.addWidget(self.type_filter)
        message_search_layout.addWidget(date_label)
        message_search_layout.addWidget(self.date_from)
        message_search_layout.addWidget(self.date_to)
        message_search_layout.addWidget(clear_filters_button)
        right_layout.addLayout(message_search_layout)

        self.messages_view = QtWidgets.QListView()
        self.messages_view.setWordWrap(True)
        self.messages_view.setItemDelegate(MessageDelegate(self.base_media_path))
        self.messages_view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.messages_view.verticalScrollBar().valueChanged.connect(self.check_scroll_position_messages)
        self.messages_view.doubleClicked.connect(self.handle_message_double_click)
        right_layout.addWidget(self.messages_view)

        main_layout.addLayout(left_layout, 1)
        main_layout.addLayout(right_layout, 3)

        self.load_chats()

    def load_chats(self):
        self.chat_model.update_chats(self.filtered_chats)

    def filter_chats(self):
        filtro = self.chat_search_input.text().lower()
        if filtro:
            filtered = self.all_conversations[self.all_conversations['chat_display_name'].str.contains(filtro, case=False, na=False)]
        else:
            filtered = self.all_conversations
        self.filtered_chats = filtered
        self.load_chats()

    def select_chat(self, index):
        self.messages_view.setModel(None)

        chat_jid = index.data(QtCore.Qt.UserRole)
        chat_name = index.data(QtCore.Qt.DisplayRole)
        self.selected_chat_jid = chat_jid
        self.message_header.setText(chat_name)

        self.filtered_data = self.get_messages_for_chat(chat_jid)

        self.messages_model = MessagesModel(self.filtered_data)
        self.messages_view.setModel(self.messages_model)
        self.messages_model.fetchMore(QtCore.QModelIndex())

        self.clear_filters()

    def get_messages_for_chat(self, chat_jid):
        chat_messages = self.df_messages[self.df_messages['chat_jid'] == chat_jid]
        chat_messages = chat_messages.sort_values(by='timestamp_raw', ascending=True).reset_index(drop=True)
        return chat_messages

    def check_scroll_position_messages(self):
        if self.messages_view.model() and self.messages_view.model().canFetchMore(QtCore.QModelIndex()):
            scrollbar = self.messages_view.verticalScrollBar()
            if scrollbar.value() + scrollbar.pageStep() >= scrollbar.maximum() - 50:
                self.messages_view.model().fetchMore(QtCore.QModelIndex())

    def filter_messages(self):
        if not self.selected_chat_jid or not hasattr(self, 'messages_model'):
            return

        datos_a_filtrar = self.df_messages[self.df_messages['chat_jid'] == self.selected_chat_jid]

        filtro_texto = self.message_search_input.text().lower()
        if filtro_texto:
            datos_a_filtrar = datos_a_filtrar[
                datos_a_filtrar['text_data'].str.contains(filtro_texto, case=False, na=False) |
                datos_a_filtrar['media_caption'].str.contains(filtro_texto, case=False, na=False)
            ]

        tipo = self.type_filter.currentText()
        if tipo == "Solo Imágenes":
            datos_a_filtrar = datos_a_filtrar[datos_a_filtrar['message_type'] == 1]
        elif tipo == "Solo Videos":
            datos_a_filtrar = datos_a_filtrar[datos_a_filtrar['message_type'] == 3]
        elif tipo == "Solo Audio":
            datos_a_filtrar = datos_a_filtrar[datos_a_filtrar['message_type'] == 2]
        elif tipo == "Solo Ubicaciones":
            datos_a_filtrar = datos_a_filtrar[datos_a_filtrar['message_type'] == 5]

        from_date = self.date_from.date()
        to_date = self.date_to.date()
        from_ts = int(datetime.datetime(from_date.year(), from_date.month(), from_date.day(),0,0).timestamp()*1000)
        to_ts = int(datetime.datetime(to_date.year(), to_date.month(), to_date.day(),23,59,59).timestamp()*1000)

        datos_a_filtrar = datos_a_filtrar[(datos_a_filtrar['timestamp_raw'] >= from_ts) & (datos_a_filtrar['timestamp_raw'] <= to_ts)]

        datos_a_filtrar = datos_a_filtrar.sort_values(by='timestamp_raw', ascending=True).reset_index(drop=True)
        self.filtered_data = datos_a_filtrar
        self.messages_model.update_messages(self.filtered_data)
        self.messages_model.fetchMore(QtCore.QModelIndex())

    def clear_filters(self):
        self.message_search_input.clear()
        self.type_filter.setCurrentIndex(0)
        # Fecha inicial en 01/01/2020
        self.date_from.setDate(QtCore.QDate(2020,1,1))
        self.date_to.setDate(QtCore.QDate.currentDate())
        self.filter_messages()

    def handle_message_double_click(self, index):
        msg = index.data(QtCore.Qt.UserRole)
        if not msg:
            return
        message_type = msg.get('message_type', 0)
        file_path = msg.get('file_path', '')
        latitude = msg.get('latitude', None)
        longitude = msg.get('longitude', None)

        if message_type == 5 and latitude is not None and longitude is not None:
            osm_url = f"https://www.openstreetmap.org/?mlat={latitude}&mlon={longitude}#map=15/{latitude}/{longitude}"
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(osm_url))
        elif message_type in (1, 2, 3) and file_path:
            adjusted_path = self.adjust_media_path(file_path)
            if os.path.exists(adjusted_path):
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(adjusted_path))

    def adjust_media_path(self, path):
        if path.startswith('Media/'):
            path = path[len('Media/'):]
        adjusted_path = os.path.join(self.base_media_path, *path.split('/'))
        return adjusted_path

    @property
    def df_messages(self):
        return getattr(self, '_df_messages', None)

    @df_messages.setter
    def df_messages(self, value):
        setattr(self, '_df_messages', value)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    viewer = WhatsAppViewer()
    viewer.show()
    sys.exit(app.exec_())
