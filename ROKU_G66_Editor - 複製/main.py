import sys
from PyQt6.QtWidgets import QApplication
from ui_main_window import MainWindow

def main():
    """
    ROKU-ROKU G66 Editor Entry Point.
    """
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
