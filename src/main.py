import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt
from gui import ShScriptHubApp, APP_STYLESHEET
from utils import get_resource_path


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    try:
        app.setAttribute(Qt.AA_UseStyleSheetPalette)
    except AttributeError:
        pass
    icon_path = get_resource_path("assets/icon.ico")
    if os.path.exists(icon_path):
        try:
            app.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            print(f"Warning: Could not set icon: {e}")
    window = ShScriptHubApp()
    window.resize(900, 520)
    window.setMinimumSize(520, 360)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
