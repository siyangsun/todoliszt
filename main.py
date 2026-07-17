import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from app.main_window import APP_NAME, MainWindow

ICON_PATH = Path(__file__).parent / "assets" / "icon.png"


def main():
    if sys.platform == "win32":
        # Give the process its own taskbar identity so Windows shows our
        # icon instead of grouping under the generic Python one
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_NAME)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(QIcon(str(ICON_PATH)))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
