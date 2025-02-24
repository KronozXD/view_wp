import sys
import os
import subprocess

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QFrame, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QRect, QPropertyAnimation, QEasingCurve, QTimer, QSize
from PySide6.QtGui import QIcon, QPixmap, QColor

# --- Colores tecnológicos ---
NEON_GREEN = "#39FF14"        # Verde neón
BACKGROUND_BLACK = "#121212"  # Fondo oscuro
BUTTON_HOVER = "#1F1F1F"      # Gris oscuro para hover en los botones

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Título y dimensiones de la ventana principal
        self.setWindowTitle("Interfaz Principal - Estilo Tecnológico")
        self.setGeometry(200, 100, 1000, 700)

        # Contenedor principal
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)

        # Barra lateral (menú)
        self.side_menu = self.create_side_menu()
        main_layout.addWidget(self.side_menu, 0)

        # Zona central con imagen y botones
        self.main_frame = QFrame()
        self.main_layout = QVBoxLayout(self.main_frame)

        # Imagen / Logo principal (ajusta la ruta según tu proyecto)
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap("icons/logo_neon.png")
        # Escalado de ejemplo para el logo principal (opcional)
        pixmap = pixmap.scaled(250, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.logo_label.setPixmap(pixmap)
        self.main_layout.addWidget(self.logo_label)

        # Botones para abrir otros scripts
        # Ajusta las rutas de íconos y scripts a tu estructura
        self.btn_modulo1 = self.create_button(
            "Ver Mensajes", 
            "icons/icon_modulo1.png", 
            lambda: self.open_script("app11.py")
        )
        self.btn_modulo2 = self.create_button(
            "Extracto de Llamadas", 
            "icons/icon_modulo2.png", 
            lambda: self.open_script("call7.py")
        )
        self.btn_modulo3 = self.create_button(
            "Geolocalización", 
            "icons/icon_modulo3.png", 
            lambda: self.open_script("loc4.py")
        )

        self.main_layout.addWidget(self.btn_modulo1)
        self.main_layout.addWidget(self.btn_modulo2)
        self.main_layout.addWidget(self.btn_modulo3)
        self.main_layout.addStretch()

        # Agregamos el frame central al layout principal
        main_layout.addWidget(self.main_frame, 1)
        self.setCentralWidget(central_widget)

        # Botón flotante con animaciones (verde neón)
        self.floating_button = self.create_floating_button()
        self.init_periodic_animation()

        # Aplicar estilos generales
        self.apply_style()

    def create_side_menu(self):
        """
        Crea un menú lateral básico.
        """
        frame = QFrame()
        frame.setFixedWidth(200)
        layout = QVBoxLayout(frame)

        # Título del menú
        label_menu = QLabel("MENÚ")
        label_menu.setAlignment(Qt.AlignCenter)
        label_menu.setStyleSheet(f"color: {NEON_GREEN}; font-size: 20px; font-weight: bold;")
        layout.addWidget(label_menu)

        layout.addStretch()

        # Texto de contacto en la parte inferior izquierda
        self.contact_label = QLabel("Derechos: Kevin Massi ver. 1.0")
        self.contact_label.setStyleSheet(f"color: {NEON_GREEN}; font-size: 12px;")
        layout.addWidget(self.contact_label, alignment=Qt.AlignLeft)

        return frame

    def create_button(self, text, icon_path, callback):
        """
        Crea un botón con un ícono (máx. 500x500 px), texto y una función (callback).
        """
        button = QPushButton(text)
        
        # Escalar el icono a un máximo de 500x500 (KeepAspectRatio)
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon = QIcon(pixmap)
            button.setIcon(icon)
            # Ajustar el tamaño que se mostrará en el botón
            button.setIconSize(QSize(64, 64))
        else:
            # Si el ícono no existe o está vacío, no asignamos nada
            print(f"[ADVERTENCIA] No se encontró el ícono: {icon_path}")
        
        button.clicked.connect(callback)
        return button

    def create_floating_button(self):
        """
        Crea un botón flotante con animaciones (fade-in y desplazamiento).
        """
        button = QPushButton()
        button.setIcon(QIcon("icons/logo_neon.png"))  # Ajusta si deseas otro icono
        button.setIconSize(QSize(64, 64))
        button.setStyleSheet("border: none; background: transparent;")
        button.setParent(self)
        button.setGeometry(20, 20, 64, 64)

        # Sombra verde neón
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setOffset(0, 0)
        shadow.setColor(QColor(57, 255, 20, 180))  # Verde neón con algo de transparencia
        button.setGraphicsEffect(shadow)

        # Animación de opacidad (fade-in)
        anim_opacity = QPropertyAnimation(button, b"windowOpacity")
        anim_opacity.setDuration(1500)
        anim_opacity.setStartValue(0.0)
        anim_opacity.setEndValue(1.0)
        anim_opacity.setEasingCurve(QEasingCurve.InOutQuad)
        anim_opacity.start()

        # Animación de posición (slide)
        anim_geometry = QPropertyAnimation(button, b"geometry")
        anim_geometry.setDuration(1500)
        anim_geometry.setStartValue(QRect(-100, 20, 64, 64))
        anim_geometry.setEndValue(QRect(20, 20, 64, 64))
        anim_geometry.setEasingCurve(QEasingCurve.OutBounce)
        anim_geometry.start()

        return button

    def init_periodic_animation(self):
        """
        Animación periódica para el botón flotante (efecto de flotación).
        """
        self.timer = QTimer()
        self.timer.setInterval(4000)
        self.timer.timeout.connect(self.float_button_animation)
        self.timer.start()

    def float_button_animation(self):
        """
        Hace que el botón flotante suba y baje ligeramente.
        """
        current_geom = self.floating_button.geometry()
        up_geom = QRect(
            current_geom.x(), 
            current_geom.y() - 10, 
            current_geom.width(), 
            current_geom.height()
        )

        anim = QPropertyAnimation(self.floating_button, b"geometry")
        anim.setDuration(600)
        anim.setStartValue(current_geom)
        anim.setKeyValueAt(0.5, up_geom)
        anim.setEndValue(current_geom)
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        anim.start()

    def open_script(self, script_name):
        """
        Ejecuta un script externo de Python mediante subprocess.
        """
        python_exec = "python" if os.name == "nt" else "python3"
        script_path = os.path.join(os.getcwd(), script_name)
        if os.path.exists(script_path):
            subprocess.Popen([python_exec, script_path])
        else:
            print(f"[ERROR] No se encontró el script: {script_path}")

    def apply_style(self):
        """
        Aplica el estilo general (negro + verde neón).
        """
        style_sheet = f"""
        QMainWindow {{
            background-color: {BACKGROUND_BLACK};
        }}
        QFrame {{
            background-color: {BACKGROUND_BLACK};
            border-radius: 15px;
        }}
        QLabel {{
            color: {NEON_GREEN};
            font-size: 18px;
        }}
        QPushButton {{
            background-color: {BACKGROUND_BLACK};
            color: {NEON_GREEN};
            font-size: 16px;
            padding: 10px;
            border: 2px solid {NEON_GREEN};
            border-radius: 8px;
        }}
        QPushButton:hover {{
            background-color: {BUTTON_HOVER};
        }}
        """
        self.setStyleSheet(style_sheet)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
