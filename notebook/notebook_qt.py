"""Qt launcher for the Detective's Notebook HTML page.

Generates a real game case via noir.cli.run_game._start_case (same path the
TUI uses) and injects the JSON payload into the page so the notebook spreads
mirror what the terminal UI would show for that seed.

Run:
    pip install PySide6
    python notebook/notebook_qt.py --seed 101
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "notebook"))

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings

from case_dump import build_case_payload  # noqa: E402


HERE = Path(__file__).resolve().parent
NOTEBOOK_HTML = HERE / "notebook.html"


class NotebookWindow(QMainWindow):
    def __init__(self, payload: dict) -> None:
        super().__init__()
        self.setWindowTitle("Detective's Notebook")
        self.resize(1280, 860)

        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#0b0604"))
        self.setPalette(palette)

        self.payload = payload
        self.view = QWebEngineView(self)
        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.ShowScrollBars, False)

        self.view.loadFinished.connect(self._on_loaded)
        self.view.setUrl(QUrl.fromLocalFile(str(NOTEBOOK_HTML)))
        self.setCentralWidget(self.view)

    def _on_loaded(self, ok: bool) -> None:
        if not ok:
            return
        payload_json = json.dumps(self.payload, default=str)
        js = (
            f"window.__CASE__ = {payload_json}; "
            "if (window.__hydrate) window.__hydrate(window.__CASE__);"
        )
        self.view.page().runJavaScript(js)

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
    p = argparse.ArgumentParser(description="Detective's Notebook (Qt window).")
    p.add_argument("--seed", type=int, default=101)
    p.add_argument("--case-index", type=int, default=1)
    args = p.parse_args()

    payload = build_case_payload(seed=args.seed, case_index=args.case_index)

    app = QApplication(sys.argv)
    app.setApplicationName("Detective's Notebook")
    if not NOTEBOOK_HTML.exists():
        raise FileNotFoundError(f"Missing HTML: {NOTEBOOK_HTML}")
    win = NotebookWindow(payload)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
