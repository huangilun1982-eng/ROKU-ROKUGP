import sys
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
from ui_main_window import MainWindow

def global_exception_handler(exc_type, exc_value, exc_tb):
    """全域例外攔截：防止程式無聲關閉，改為顯示錯誤對話框"""
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print(error_msg)  # 輸出到終端供除錯
    QMessageBox.critical(None, "程式錯誤", f"發生未預期的錯誤:\n\n{error_msg[:500]}")

def main():
    """
    ROKU-ROKU G66 Editor Entry Point.
    """
    sys.excepthook = global_exception_handler
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
