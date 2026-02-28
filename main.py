"""
main.py
PopAI - Windows 11 デスクトップ常駐アシスタント
エントリポイント。システムトレイに常駐し、
グローバルホットキー (Ctrl+Alt+Space) でフロートウィンドウを起動する。
"""

import sys
import signal
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QWidget
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter, QBrush
from PyQt6.QtCore import Qt

# トレイ常駐アプリのため Ctrl+C による割り込みを無視する
# (pyautogui が送る Ctrl+C が自プロセスを終了させないようにするため)
signal.signal(signal.SIGINT, signal.SIG_IGN)

from hotkey import HotkeyThread
from float_window import FloatWindow


# ------------------------------------------------------------------ #
# トレイアイコン用のシンプルな画像を動的生成
# ------------------------------------------------------------------ #
def make_tray_icon() -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(QColor("#9C27B0")))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, 28, 28)
    painter.setPen(QColor("white"))
    font = painter.font()
    font.setBold(True)
    font.setPixelSize(16)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "P")
    painter.end()
    return QIcon(pixmap)


# ------------------------------------------------------------------ #
# メインクラス
# ------------------------------------------------------------------ #
class PopAIApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        # 最後のウィンドウが閉じてもアプリを終了しない（トレイ常駐）
        self.app.setQuitOnLastWindowClosed(False)

        # システムトレイが利用可能か確認
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("[PopAI] ERROR: システムトレイが利用できません。", file=sys.stderr)
            sys.exit(1)

        self._float_window = FloatWindow()
        # QMenu の親として非表示 QWidget を使う（Windows 11 での互換性向上）
        self._tray_parent = QWidget()
        self._tray_parent.hide()
        self._setup_tray()
        self._setup_hotkey()

    # ------------------------------------------------------------------ #
    # システムトレイ
    # ------------------------------------------------------------------ #
    def _setup_tray(self):
        icon = make_tray_icon()
        self._tray = QSystemTrayIcon(icon, parent=self._tray_parent)
        self._tray.setToolTip("PopAI - Ctrl+Alt+Space でアシスタントを起動")

        # メニューも同じ親を使う
        menu = QMenu(self._tray_parent)
        show_action = menu.addAction("ウィンドウを表示")
        show_action.triggered.connect(lambda: self._float_window.show_with_text(""))
        menu.addSeparator()
        quit_action = menu.addAction("終了")
        quit_action.triggered.connect(self.app.quit)

        self._tray.setContextMenu(menu)
        self._tray.show()

        # isVisible で表示確認
        if self._tray.isVisible():
            print("[PopAI] システムトレイアイコンの表示に成功しました。")
        else:
            print("[PopAI] WARNING: トレイアイコンが表示されていません。", file=sys.stderr)

        # ダブルクリックでもウィンドウを表示
        self._tray.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._float_window.show_with_text("")

    # ------------------------------------------------------------------ #
    # ホットキースレッド
    # ------------------------------------------------------------------ #
    def _setup_hotkey(self):
        self._hotkey_thread = HotkeyThread()
        self._hotkey_thread.clipboard_ready.connect(self._on_clipboard_ready)
        self._hotkey_thread.start()

    # ------------------------------------------------------------------ #
    # クリップボード受信 → フロートウィンドウ表示
    # ------------------------------------------------------------------ #
    def _on_clipboard_ready(self, text: str):
        print(f"[PopAI] クリップボード取得: {len(text)} 文字")
        self._float_window.show_with_text(text)

    # ------------------------------------------------------------------ #
    # 起動
    # ------------------------------------------------------------------ #
    def run(self) -> int:
        print("[PopAI] 起動しました。Ctrl+Alt+Space でアシスタントを呼び出せます。")
        print("[PopAI] トレイアイコンを右クリックして「終了」を選択すると終了します。")
        print("[PopAI] ※トレイアイコンが見えない場合はタスクバー右端の「^」をクリックしてください。")
        return self.app.exec()


# ------------------------------------------------------------------ #
# エントリポイント
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    popai = PopAIApp()
    sys.exit(popai.run())
