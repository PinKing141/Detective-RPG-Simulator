"""Qt launcher for the Detective's Notebook HTML page.

Opens the notebook in a frameless-friendly QMainWindow with a QWebEngineView so
the CSS 3D page-flip animations render with hardware acceleration.

Run:
    pip install PySide6
    python notebook/notebook_qt.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QIcon, QPalette, QColor
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings


HERE = Path(__file__).resolve().parent
NOTEBOOK_HTML = HERE / "notebook.html"


class NotebookWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Detective's Notebook")
        self.resize(1280, 860)

        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#0b0604"))
        self.setPalette(palette)

        self.view = QWebEngineView(self)
        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.ShowScrollBars, False)

        self.view.setUrl(QUrl.fromLocalFile(str(NOTEBOOK_HTML)))
        self.setCentralWidget(self.view)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        else:
            super().keyPressEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Detective's Notebook")
    if not NOTEBOOK_HTML.exists():
        raise FileNotFoundError(f"Missing HTML: {NOTEBOOK_HTML}")
    win = NotebookWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
