#!/usr/bin/env python3
"""
Sticky Notes simples em PyQt5 - Versão com salvamento otimizado
"""

import os
# Workaround para Wayland
if os.environ.get("XDG_SESSION_TYPE") == "wayland":
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
   
import sys
import json
import signal
import subprocess

from PyQt5.QtWidgets import (
    QApplication, QWidget, QTextEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QMenu, QAction, QColorDialog, QFontDialog, QSystemTrayIcon, QMessageBox, QLabel
)
from PyQt5.QtCore import Qt, QSettings, QSize, QTimer, QUrl
from PyQt5.QtGui import QIcon, QFont, QColor, QCursor, QDesktopServices
import uuid


import simple_sticky_notes.about as about
import simple_sticky_notes.modules.configure as configure 
from simple_sticky_notes.modules.resources import resource_path

from simple_sticky_notes.modules.wabout    import show_about_window
from simple_sticky_notes.desktop import create_desktop_file, create_desktop_directory, create_desktop_menu


# ---------- Path to config file ----------
CONFIG_PATH = os.path.join( os.path.expanduser("~"),
                            ".config", 
                            about.__package__, 
                            "config.json" )

DEFAULT_CONTENT={   
    "indicator_configure": "Configure",
    "indicator_about": "About",
    "indicator_coffee": "Coffee",
    "indicator_new_note": "New note",
    "indicator_show_notes": "Show all",
    "indicator_hide_notes": "Hide all",
    "indicator_exit": "Exit",
    "note_width": 250,
    "note_height": 180,
    "note_pos_col": 100,
    "note_pos_lin": 100,
    "note_bg_color": "#ffff99",
    "note_text_color": "#000000",
    "note_font": "Sans 12",
    "note_btn_drag": "Move the sticky note",
    "note_btn_new": "Add a new sticky note",
    "note_btn_lock": "Lock this sticky note",
    "note_btn_menu": "Open the menu",
    "note_btn_close": "Delete thi sticky note",
    "menu_action_color": "Change background color",
    "menu_action_text": "Change text color",
    "menu_action_font": "Change font",
    "menu_action_lock": "Lock",
    "menu_action_unlock": "Unlock",
    "dialog_action_color": "Choose the background color",
    "dialog_action_text": "Choose the text color",
    "dialog_action_font": "Choose the font",
    "dialog_action_delete": "Delete note",
    "dialog_action_delete_confirm": "Are you sure you want to delete this note?",
}

configure.verify_default_config(CONFIG_PATH,default_content=DEFAULT_CONTENT)

CONFIG=configure.load_config(CONFIG_PATH)

# ------------------------------------------------------------------------------


class StickyNote(QWidget):
    """Janela de nota individual"""
    def __init__(self, noteset, note_data=None):
        super().__init__()
       
        self.resizing = False
        self.resize_hitbox = 40
       
        self.noteset = noteset
        self.uuid = note_data.get('uuid', str(uuid.uuid4())) if note_data else str(uuid.uuid4())
        self.body = note_data.get('body', '') if note_data else ''
        self.properties = note_data.get('properties', {}) if note_data else {}
        self.category = note_data.get('cat', '') if note_data else ''
        
        self.locked = self.properties.get('locked', False)
        self.bg_color = QColor(self.properties.get('bg_color', CONFIG["note_bg_color"]))
        self.text_color = QColor(self.properties.get('text_color', CONFIG["note_text_color"]))
        self.font = QFont(self.properties.get('font', CONFIG["note_font"]))
        
        self.save_timer = None

        self.setWindowFlag(Qt.Tool, True)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setMinimumSize(180, 120)
       
        self.init_ui()
        self.load_state()

    def init_ui(self):
        """Cria a interface da nota"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        # === TOOLBAR ===
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(0)
       
        self.toolbar_widget = QWidget()
        self.toolbar_widget.setMouseTracking(True)
        self.toolbar_widget.setCursor(Qt.ArrowCursor)
        self.toolbar_widget.setLayout(toolbar)

        self.btn_drag = QPushButton()
        self.btn_new = QPushButton()
        self.btn_lock = QPushButton()
        self.btn_menu = QPushButton()
        self.btn_close = QPushButton()

        # Adiciona os botões da esquerda
        for btn, icon_name, tooltip in [
            (self.btn_drag, "move", CONFIG["note_btn_drag"]),
            (self.btn_new,  "add",  CONFIG["note_btn_new"]),
            (self.btn_lock, "lock", CONFIG["note_btn_lock"]),
            (self.btn_menu, "menu", CONFIG["note_btn_menu"])
        ]:
            icon_path = resource_path("icons",f"{icon_name}.svg")
            btn.setFixedSize(28, 28)
            btn.setToolTip(tooltip)
            btn.setIcon(QIcon(icon_path))
            btn.setIconSize(QSize(20, 20))
            btn.setFlat(True)
            btn.setCursor(Qt.ArrowCursor)
            toolbar.addWidget(btn)

        # === EXPANDER (o que você pediu) ===
        toolbar.addStretch()          # <-- Isso empurra o close para a direita

        # Botão de fechar (fica sozinho à direita)
        icon_path = resource_path("icons","close.svg")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setToolTip(CONFIG["note_btn_close"])
        self.btn_close.setIcon(QIcon(icon_path))
        self.btn_close.setIconSize(QSize(20, 20))
        self.btn_close.setFlat(True)
        self.btn_close.setCursor(Qt.ArrowCursor)
        toolbar.addWidget(self.btn_close)
        
        # === ESTILO DO MENU (muito importante para notas claras) ===
        self.menu_style = """
            QMenu {
                background-color: #ffffff;
                border: 1px solid #c0c0c0;
                border-radius: 6px;
                padding: 4px;
                color: #000000;
                font-size: 13px;
            }
            QMenu::item {
                padding: 6px 25px 6px 25px;
                border-radius: 4px;
                color: #000000;
            }
            QMenu::item:selected {
                background-color: #e0e0e0;
                font-weight: bold;
                color: #000000;
            }
            QMenu::item:disabled {
                color: #aaaaaa;
            }
        """

        # Configurações do btn_drag
        self.btn_drag.setCursor(Qt.SizeAllCursor)
        self.btn_drag.mousePressEvent = self.drag_mouse_press

        layout.addWidget(self.toolbar_widget)

        # Área de texto
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(self.body)
        self.text_edit.textChanged.connect(self.on_text_changed)
        self.text_edit.viewport().setCursor(Qt.IBeamCursor)
        layout.addWidget(self.text_edit)
        
        icon_path = resource_path("icons","resizer.svg")
        self.resize_handle = QLabel(self)
        self.resize_handle.setPixmap(QIcon(icon_path).pixmap(20, 20))
        self.resize_handle.resize(20, 20)

        self.btn_new.clicked.connect(self.noteset.new_note)
        self.btn_lock.clicked.connect(self.toggle_lock)
        self.btn_menu.clicked.connect(self.show_menu)
        self.btn_close.clicked.connect(self.delete_note)

        self.setMouseTracking(True)
        self.update_style()
        
        

    def update_style(self):
        r, g, b, _ = self.bg_color.getRgb()
        self.setStyleSheet(f"""
            QWidget {{
                background-color: rgb({r}, {g}, {b});
                border-radius: 8px;
            }}
            QTextEdit {{
                background-color: transparent;
                color: {self.text_color.name()};
                border: none;
                selection-background-color: #666666;
                selection-color: white;
            }}
            QPushButton {{
                background: transparent;
                border: none;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,80);
                border-radius: 4px;
            }}
        """)
        self.text_edit.setFont(self.font)

    def load_state(self):
        pos = self.properties.get('position', [CONFIG["note_pos_col"], CONFIG["note_pos_lin"]])
        size = self.properties.get('size', [CONFIG["note_width"], CONFIG["note_height"] ])
        self.move(pos[0], pos[1])
        self.resize(size[0], size[1])
        self.set_locked_state(self.locked)

    # ====================== SALVAMENTO ======================
    def save_note(self, immediate=False):
        self.properties = {
            'position': [self.pos().x(), self.pos().y()],
            'size': [self.width(), self.height()],
            'locked': self.locked,
            'bg_color': self.bg_color.name(),
            'text_color': self.text_color.name(),
            'font': self.font.toString()
        }

        if immediate:
            self.noteset.save_all()
        else:
            if self.save_timer is None:
                self.save_timer = QTimer()
                self.save_timer.setSingleShot(True)
                self.save_timer.timeout.connect(self.noteset.save_all)
            self.save_timer.start(800)

    def on_text_changed(self):
        self.save_note(immediate=False)

    # ====================== MOVIMENTO ======================
    def moveEvent(self, event):
        """Salva posição quando a janela é movida"""
        super().moveEvent(event)
        self.save_note(immediate=False)   # debounce também no movimento

    # ====================== RESIZE ======================
    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if self.is_in_resize_zone(event.pos()):
            self.resizing = True
            self.resize_start_pos = event.globalPos()
            self.resize_start_size = self.size()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.resizing:
            delta = event.globalPos() - self.resize_start_pos
            self.resize(
                max(self.minimumWidth(), self.resize_start_size.width() + delta.x()),
                max(self.minimumHeight(), self.resize_start_size.height() + delta.y())
            )
            event.accept()
            return

        if self.is_in_resize_zone(event.pos()):
            self.setCursor(Qt.SizeFDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if self.resizing:
            self.resizing = False
            self.save_note(immediate=True)
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_handle.move(
            self.width() - self.resize_handle.width() - 2,
            self.height() - self.resize_handle.height() - 2
        )

    def is_in_resize_zone(self, pos):
        return (pos.x() >= self.width() - self.resize_hitbox and
                pos.y() >= self.height() - self.resize_hitbox)

    # ====================== OUTRAS AÇÕES ======================
    def toggle_lock(self):
        self.set_locked_state(not self.locked)

    def set_locked_state(self, locked):
        self.locked = locked
        self.text_edit.setReadOnly(locked)
        icon_name = "lock" if locked else "unlock"
        icon_path = resource_path("icons", f"{icon_name}.svg")
        self.btn_lock.setIcon(QIcon(icon_path))
        self.save_note(immediate=True)


    def show_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(self.menu_style)   # ← aplica o estilo
        
        action_color = QAction(CONFIG["menu_action_color"], self)
        action_color.triggered.connect(self.change_bg_color)
        menu.addAction(action_color)

        action_text = QAction(CONFIG["menu_action_text"], self)
        action_text.triggered.connect(self.change_text_color)
        menu.addAction(action_text)

        action_font = QAction(CONFIG["menu_action_font"], self)
        action_font.triggered.connect(self.change_font)
        menu.addAction(action_font)

        menu.addSeparator()
        lock_action = QAction(CONFIG["menu_action_lock"] if not self.locked else CONFIG["menu_action_unlock"], self)
        lock_action.triggered.connect(self.toggle_lock)
        menu.addAction(lock_action)

        menu.exec_(QCursor.pos())

    def change_bg_color(self):
        color = QColorDialog.getColor(self.bg_color, self, CONFIG["dialog_action_color"])
        if color.isValid():
            self.bg_color = color
            self.update_style()
            self.save_note(immediate=True)

    def change_text_color(self):
        color = QColorDialog.getColor(self.text_color, self, CONFIG["dialog_action_text"])
        if color.isValid():
            self.text_color = color
            self.update_style()
            self.save_note(immediate=True)

    def change_font(self):
        font, ok = QFontDialog.getFont(self.font, self, CONFIG["dialog_action_font"])
        if ok:
            self.font = font
            self.update_style()
            self.save_note(immediate=True)

    def delete_note(self):
        reply = QMessageBox.question(   self, 
                                        CONFIG["dialog_action_delete"],
                                        CONFIG["dialog_action_delete_confirm"],
                                        QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.noteset.delete_note(self)
            self.close()

    def drag_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            handle = self.windowHandle()
            if handle is not None:
                handle.startSystemMove()
            event.accept()



class NoteSet:
    """Gerencia todas as notas"""
    def __init__(self, app):
        self.app = app
        self.notes = []
        self.settings = QSettings("stickynotes", "qt")

    def load_notes(self):
        data = self.settings.value("notes", [])
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                data = []
        for note_data in data:
            note = StickyNote(self, note_data)
            self.notes.append(note)
            note.show()

    def new_note(self):
        note = StickyNote(self)
        self.notes.append(note)
        note.show()
        self.save_all()

    def delete_note(self, note_widget):
        if note_widget in self.notes:
            self.notes.remove(note_widget)
        self.save_all()

    def save_all(self):
        """Salva todas as notas"""
        data = []
        for note in self.notes:
            if not note.isVisible():
                continue
            note_data = {
                'uuid': note.uuid,
                'body': note.text_edit.toPlainText(),
                'properties': note.properties,
                'cat': note.category
            }
            data.append(note_data)
        self.settings.setValue("notes", json.dumps(data))

    def show_all(self):
        for note in self.notes:
            note.show()

    def hide_all(self):
        for note in self.notes:
            note.hide()


class IndicatorStickyNotes(QApplication):
    """Aplicação principal"""
    def __init__(self, argv):
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)
        self.noteset = NoteSet(self)

       
        ## Icon
        # Get base directory for icons
        self.icon_path = resource_path("icons", "logo.png")
        self.setWindowIcon(QIcon(self.icon_path)) 
        
        
        # Tray Icon
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QIcon(self.icon_path))
        self.tray.setVisible(True)
        self.create_tray_menu()

        # Carregar notas
        self.noteset.load_notes()
        if not self.noteset.notes:
            self.noteset.new_note()

    def _open_file_in_text_editor(self, filepath):
        if os.name == 'nt':  # Windows
            os.startfile(filepath)
        elif os.name == 'posix':  # Linux/macOS
            subprocess.run(['xdg-open', filepath])
            
    def open_configure_editor(self):
        self._open_file_in_text_editor(CONFIG_PATH)

    def open_about(self):
        data={
            "version": about.__version__,
            "package": about.__package__,
            "program_name": about.__program_name__,
            "author": about.__author__,
            "email": about.__email__,
            "description": about.__description__,
            "url_source": about.__url_source__,
            "url_doc": about.__url_doc__,
            "url_funding": about.__url_funding__,
            "url_bugs": about.__url_bugs__
        }
        show_about_window(data,self.icon_path)

    def on_coffee_action_click(self):
        QDesktopServices.openUrl(QUrl("https://ko-fi.com/trucomanx"))

    def create_tray_menu(self):
        menu = QMenu()
        
        # New
        self.new_action = QAction( QIcon(resource_path('icons', 'add.svg')), 
                                    CONFIG["indicator_new_note"], 
                                    self)
        self.new_action.triggered.connect(self.noteset.new_note)
        menu.addAction(self.new_action)
        
        #
        menu.addSeparator()
        
        # Show
        self.show_action = QAction( QIcon(resource_path('icons', 'fullscreen.svg')), 
                                    CONFIG["indicator_show_notes"], 
                                    self)
        self.show_action.triggered.connect(self.noteset.show_all)
        menu.addAction(self.show_action)
        
        
        # Hide
        self.hide_action = QAction( QIcon(resource_path('icons', 'fullscreen-exit.svg')), 
                                    CONFIG["indicator_hide_notes"], 
                                    self)
        self.hide_action.triggered.connect(self.noteset.hide_all)
        menu.addAction(self.hide_action)
        
        #
        menu.addSeparator()
        
        # Configure
        self.configure_action = QAction(QIcon(resource_path('icons', 'applications-system.svg')),
                                        CONFIG["indicator_configure"], 
                                        self)
        self.configure_action.triggered.connect(self.open_configure_editor)
        menu.addAction(self.configure_action)
        
        # About
        self.about_action = QAction(QIcon(resource_path('icons', 'status_help.png')), 
                                    CONFIG["indicator_about"], 
                                    self)
        self.about_action.triggered.connect(self.open_about)
        menu.addAction(self.about_action)
        
        # Coffee
        self.coffee_action = QAction(   QIcon(resource_path('icons', 'emote-love.png')), 
                                        CONFIG["indicator_coffee"], 
                                        self)
        self.coffee_action.triggered.connect(self.on_coffee_action_click)
        menu.addAction(self.coffee_action)
        
        # Exit
        self.quit_action = QAction(CONFIG["indicator_exit"])
        self.quit_action.setIcon(QIcon(resource_path('icons', 'application-exit.png')))
        self.quit_action.triggered.connect(self.quit)
        menu.addAction(self.quit_action)

        self.tray.setContextMenu(menu)

    def quit(self):
        self.noteset.save_all()
        super().quit()

def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
       

    icon_path=resource_path("icons", "logo.png")
    extras="" 
    
    create_desktop_directory()    
    create_desktop_menu()
    create_desktop_file(os.path.join("~",".local","share","applications"), 
                        program_name=about.__program_name__,
                        extras=extras,
                        icon_path=icon_path)
    
    for n in range(len(sys.argv)):
        if sys.argv[n] == "--autostart":
            create_desktop_directory(overwrite = True)
            create_desktop_menu(overwrite = True)
            create_desktop_file(os.path.join("~",".config","autostart"), 
                                overwrite=True, 
                                program_name=about.__program_name__,
                                extras=extras,
                                icon_path=icon_path)
            return
        if sys.argv[n] == "--applications":
            create_desktop_directory(overwrite = True)
            create_desktop_menu(overwrite = True)
            create_desktop_file(os.path.join("~",".local","share","applications"), 
                                overwrite=True, 
                                program_name=about.__program_name__,
                                extras=extras,
                                icon_path=icon_path)
            return
    
    app = IndicatorStickyNotes(sys.argv)
    app.setApplicationName(about.__package__) # xprop WM_CLASS # *.desktop -> StartupWMClass  
    sys.exit(app.exec_())
    
if __name__ == "__main__":

    main()
