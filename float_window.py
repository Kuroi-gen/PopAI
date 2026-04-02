"""
float_window.py
クリップボード内容を表示し、Azure OpenAI API の結果を表示するフロートウィンドウ。
最前面・フレームレスで画面中央（またはマウス位置付近）に表示される。
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QSizePolicy, QFrame,
    QApplication, QSizeGrip
)
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtCore import Qt, QPoint, QSettings, QSize
from PyQt6.QtGui import QCursor, QKeySequence, QShortcut, QColor, QWheelEvent, QKeyEvent

from api_worker import ApiWorker, SYSTEM_PROMPTS


class FloatWindow(QWidget):
    """
    フロートポップアップウィンドウ（2ペイン構成）。
    上段: 入力テキスト (クリップボード)
    下段: AI 回答 / ローディング / エラー表示
    """

    BUTTONS = [
        ("要約(&S)", "S", "summary", "選択テキストを要約します (Alt+S)"),
        ("質問(&Q)", "Q", "question", "選択テキストについて質問します (Alt+Q)"),
        ("添削(&T)", "T", "correction", "選択テキストを添削します (Alt+T)"),
        ("チャット(&C)", "C", "chat", "チャットを開始します (Alt+C)"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._drag_pos: QPoint | None = None
        self._api_worker: ApiWorker | None = None
        self._buttons: list[QPushButton] = []

        # 会話履歴を保持するリスト
        self._chat_history: list[dict[str, str]] = []

        # フォントサイズ保持用 (単位: pt)
        self._current_font_size: int = 12

        self._init_ui()
        self._apply_style()

        # フォントサイズ変更（Ctrl + ホイール）をテキストエリアでブロックしないよう設定
        self._input_area.installEventFilter(self)
        self._result_area.installEventFilter(self)

        shortcut = QShortcut(QKeySequence("Escape"), self)
        shortcut.activated.connect(self.close)

        # 履歴クリアのショートカット (Ctrl + L)
        clear_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        clear_shortcut.activated.connect(self._on_clear_clicked)

    def _get_settings(self) -> QSettings:
        # プロジェクトフォルダ内の settings.ini を指定
        settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.ini")
        return QSettings(settings_path, QSettings.Format.IniFormat)

    def _save_settings(self):
        settings = self._get_settings()
        settings.setValue("window/size", self.size())
        settings.setValue("window/pos", self.pos())
        settings.sync()

    def _center_on_primary_screen(self):
        screen = QApplication.primaryScreen().geometry()
        x = screen.left() + (screen.width() - self.width()) // 2
        y = screen.top() + (screen.height() - self.height()) // 2
        self.move(x, y)

    def _ensure_visible(self):
        """
        ウィンドウの中心点が現在有効なディスプレイのいずれかに含まれているか確認し、
        含まれていなければプライマリスクリーンの中央にリセットする。
        """
        center_point = self.geometry().center()
        is_visible = False
        for screen in QApplication.screens():
            if screen.geometry().contains(center_point):
                is_visible = True
                break

        if not is_visible:
            self._center_on_primary_screen()

    def _load_settings_and_apply(self):
        settings = self._get_settings()
        saved_size = settings.value("window/size")
        saved_pos = settings.value("window/pos")

        if saved_size is not None and saved_pos is not None:
            self.resize(saved_size)
            self.move(saved_pos)
            self._ensure_visible()
        else:
            # 初回起動時等のフォールバック
            self.resize(600, 450)
            self._center_on_primary_screen()

    # ------------------------------------------------------------------ #
    # UI 構築
    # ------------------------------------------------------------------ #
    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._container = QWidget(self)
        self._container.setObjectName("container")
        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(10)

        # ── タイトルバー ──
        title_bar = QHBoxLayout()
        title_label = QLabel("📋  PopAI")
        title_label.setObjectName("titleLabel")
        title_bar.addWidget(title_label)
        title_bar.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("closeBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.close)
        title_bar.addWidget(close_btn)
        layout.addLayout(title_bar)

        # ── 入力テキストエリア ──
        input_label = QLabel("📄 選択テキスト")
        input_label.setObjectName("sectionLabel")
        layout.addWidget(input_label)

        self._input_area = QTextEdit()
        self._input_area.setObjectName("inputArea")
        self._input_area.setPlaceholderText("クリップボードのテキストがここに表示されます...")
        self._input_area.setMinimumHeight(150)
        self._input_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._input_area)

        # ── ボタン行 ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        for label, key, color, tip in self.BUTTONS:
            btn = self._make_button(label, key, color, tip)
            btn_layout.addWidget(btn)
            self._buttons.append(btn)

        # クリアボタンを追加
        clear_btn = QPushButton("🗑️")
        clear_btn.setToolTip("会話履歴をクリアします (Ctrl+L)")
        clear_btn.setFixedHeight(36)
        clear_btn.setFixedWidth(40)
        clear_btn.setObjectName("btnClear")
        clear_btn.clicked.connect(self._on_clear_clicked)
        btn_layout.addWidget(clear_btn)
        self._clear_btn = clear_btn

        layout.addLayout(btn_layout)

        # ── セパレータ ──
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # ── 履歴トグルボタン ──
        self._history_toggle_btn = QPushButton("▼ 過去の会話履歴を表示（ここをクリック）")
        self._history_toggle_btn.setObjectName("historyToggleBtn")
        self._history_toggle_btn.setEnabled(False)
        self._history_toggle_btn.setCheckable(True)
        self._history_toggle_btn.clicked.connect(self._on_toggle_history_clicked)
        layout.addWidget(self._history_toggle_btn)

        # ── 履歴展開エリア (初期は非表示) ──
        self._history_area = QTextEdit()
        self._history_area.setObjectName("historyArea")
        self._history_area.setReadOnly(True)
        self._history_area.hide()
        # 高さをある程度制限するかExpandingにするか。
        # _result_areaと同等の扱いにするためExpandingで。
        self._history_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._history_area)

        # ── AI 回答エリア ──
        result_label = QLabel("🤖 最新のAIの回答")
        result_label.setObjectName("sectionLabel")
        layout.addWidget(result_label)

        self._result_area = QTextEdit()
        self._result_area.setObjectName("resultArea")
        self._result_area.setReadOnly(True)
        self._result_area.setPlaceholderText("ボタンを押すと AI の回答がここに表示されます...")
        self._result_area.setMinimumHeight(120)
        self._result_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._result_area)

        root_layout.addWidget(self._container)

        # ── QSizeGrip を右下に追加 ──
        # QSizeGripを確実に機能させ、背面に隠れないように_containerのレイアウトではなく、
        # _containerに直接重ねるような配置にします。（QSizeGripの親をselfにして、resizeEventで右下に配置）

        # QSizeGrip を作成（親を self に設定）
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(16, 16)

        # 背景と重なって見えなくなるのを防ぐため、少し色をつけます
        self.size_grip.setStyleSheet("QSizeGrip { background-color: rgba(255, 255, 255, 0.3); border-radius: 4px; }")

        self.setMinimumWidth(400)
        self.setMinimumHeight(300)

        # ── 前回サイズ・位置の復元 ──
        self._load_settings_and_apply()

        # ── アプリ終了時にも保存する ──
        QApplication.instance().aboutToQuit.connect(self._save_settings)

    def _make_button(self, label: str, key: str, btn_type: str, tip: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setToolTip(tip)
        btn.setFixedHeight(36)
        btn.setObjectName(f"btn_{key}")
        btn.setProperty("btnType", btn_type)
        btn.clicked.connect(lambda _, k=key: self._on_button_clicked(k))
        return btn

    def _on_toggle_history_clicked(self, checked: bool):
        if checked:
            self._history_toggle_btn.setText("▲ 会話履歴を非表示")
            self._history_area.show()
            # 展開されたら一番下までスクロールしておく
            scrollbar = self._history_area.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        else:
            self._history_toggle_btn.setText("▼ 過去の会話履歴を表示（ここをクリック）")
            self._history_area.hide()

    # ------------------------------------------------------------------ #
    # スタイル
    # ------------------------------------------------------------------ #
    def _apply_style(self):
        self.setStyleSheet(f"""
            QWidget#container {{
                background-color: rgba(45, 45, 45, 230);
                border-radius: 14px;
                border: 1px solid rgba(255, 255, 255, 0.10);
            }}

            QLabel#titleLabel {{
                color: #D4D4D4;
                font-size: 14px;
                font-weight: bold;
                font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
            }}

            QLabel#sectionLabel {{
                color: #888;
                font-size: 11px;
                font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
            }}

            QPushButton#closeBtn {{
                background: transparent;
                color: #D4D4D4;
                border: none;
                font-size: 16px;
                font-family: "Segoe UI Symbol", "Inter", "Ubuntu", sans-serif;
                border-radius: 14px;
            }}
            QPushButton#closeBtn:hover {{ background: rgba(255,80,80,0.3); color:#fff; }}

            QTextEdit#inputArea {{
                background-color: rgba(45, 45, 45, 180);
                color: #D4D4D4;
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 8px;
                font-family: "Consolas", "Yu Gothic UI", monospace;
                font-size: {self._current_font_size}pt;
                padding: 8px;
                selection-background-color: #264F78;
            }}

            QFrame#separator {{
                color: rgba(255,255,255,0.08);
                max-height: 1px;
                background: rgba(255,255,255,0.08);
            }}

            QPushButton#historyToggleBtn {{
                background-color: transparent;
                color: #D4D4D4;
                border: none;
                font-size: 12px;
                font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
                text-align: left;
                padding: 4px;
            }}
            QPushButton#historyToggleBtn:hover {{
                color: #FFFFFF;
                background-color: rgba(255, 255, 255, 0.05);
                border-radius: 4px;
            }}
            QPushButton#historyToggleBtn:disabled {{
                color: #555555;
            }}

            QTextEdit#historyArea {{
                background-color: rgba(45, 45, 45, 180);
                color: #D4D4D4;
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 8px;
                font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
                font-size: {self._current_font_size - 1}pt;
                padding: 10px;
                selection-background-color: #264F78;
            }}

            QTextEdit#resultArea {{
                background-color: rgba(45, 45, 45, 200);
                color: #D4D4D4;
                border: 1px solid rgba(0, 122, 204, 0.3);
                border-radius: 8px;
                font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
                font-size: {self._current_font_size}pt;
                padding: 10px;
                selection-background-color: #264F78;
            }}

            QPushButton[btnType="summary"] {{
                background-color: transparent; color:#D4D4D4;
                border: 1px solid #2D2D2D;
                border-radius:8px; font-weight:bold;
                font-family:"Segoe UI","Yu Gothic UI",sans-serif; font-size:12pt;
            }}
            QPushButton[btnType="summary"]:hover   {{ background-color: rgba(255, 255, 255, 0.1); }}
            QPushButton[btnType="summary"]:pressed  {{ background-color: rgba(255, 255, 255, 0.2); }}
            QPushButton[btnType="summary"]:disabled {{ color:#666; border-color:#2D2D2D; }}

            QPushButton[btnType="question"] {{
                background-color: transparent; color:#D4D4D4;
                border: 1px solid #007ACC;
                border-radius:8px; font-weight:bold;
                font-family:"Segoe UI","Yu Gothic UI",sans-serif; font-size:12pt;
            }}
            QPushButton[btnType="question"]:hover   {{ background-color: rgba(0, 122, 204, 0.2); }}
            QPushButton[btnType="question"]:pressed  {{ background-color: rgba(0, 122, 204, 0.4); }}
            QPushButton[btnType="question"]:disabled {{ color:#666; border-color:#1A3A6E; }}

            QPushButton[btnType="correction"] {{
                background-color: transparent; color:#D4D4D4;
                border: 1px solid #6A9955;
                border-radius:8px; font-weight:bold;
                font-family:"Segoe UI","Yu Gothic UI",sans-serif; font-size:12pt;
            }}
            QPushButton[btnType="correction"]:hover   {{ background-color: rgba(106, 153, 85, 0.2); }}
            QPushButton[btnType="correction"]:pressed  {{ background-color: rgba(106, 153, 85, 0.4); }}
            QPushButton[btnType="correction"]:disabled {{ color:#666; border-color:#2E5E30; }}

            QPushButton[btnType="chat"] {{
                background-color: #007ACC; color:white; border:none;
                border-radius:8px; font-weight:bold;
                font-family:"Segoe UI","Yu Gothic UI",sans-serif; font-size:12pt;
            }}
            QPushButton[btnType="chat"]:hover   {{ background-color:#1F8AD2; }}
            QPushButton[btnType="chat"]:pressed  {{ background-color:#005A9E; }}
            QPushButton[btnType="chat"]:disabled {{ background-color:#1A3A6E; color:#666; }}

            QPushButton#btnClear {{
                background-color: transparent;
                color: #888;
                border: 1px solid #E64040;
                border-radius: 8px;
                font-size: 14pt;
            }}
            QPushButton#btnClear:hover {{
                background-color: rgba(230, 64, 64, 0.2);
                color: white;
            }}
            QPushButton#btnClear:pressed {{
                background-color: rgba(230, 64, 64, 0.4);
            }}
            QPushButton#btnClear:disabled {{
                background-color: rgba(255, 255, 255, 0.05);
                border-color: rgba(255, 255, 255, 0.1);
                color: #666;
            }}
        """)

    # ------------------------------------------------------------------ #
    # 公開 API
    # ------------------------------------------------------------------ #
    def show_with_text(self, text: str):
        """テキストをセットしてウィンドウを表示する。"""
        self._input_area.setPlainText(text)

        # 履歴をクリアして新しいテキストでの開始に備える
        self._chat_history.clear()

        self._result_area.clear()
        self._history_area.clear()
        self._history_toggle_btn.setEnabled(False)
        self._history_toggle_btn.setChecked(False)
        self._on_toggle_history_clicked(False)
        self._set_buttons_enabled(True)

        if self.isHidden():
            # 非表示状態から復帰する際は設定を読み込んで適用
            self._load_settings_and_apply()
        else:
            # すでに表示されている場合でも、画面外に移動していないか確認
            self._ensure_visible()

        self.show()
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------ #
    # ボタンアクション
    # ------------------------------------------------------------------ #
    def _on_clear_clicked(self):
        # 履歴をクリア
        self._chat_history.clear()

        # UIをリセット（テキストエリア下段のみ）
        self._result_area.setPlainText("🧹 会話履歴をクリアしました")
        self._history_area.clear()

        # トグルボタンを無効化して非表示状態に戻す
        self._history_toggle_btn.setEnabled(False)
        self._history_toggle_btn.setChecked(False)
        self._on_toggle_history_clicked(False)

    def _on_button_clicked(self, key: str):
        text = self._input_area.toPlainText().strip()
        if not text:
            self._result_area.setPlainText("⚠️ テキストが入力されていません。")
            return

        # システムプロンプトの管理
        # 常に最新のボタンのシステムプロンプトで先頭を上書き（差し替え）する
        system_prompt = SYSTEM_PROMPTS.get(key, "")

        # 履歴が空、または最初の要素がシステムプロンプトでない場合は新しく追加
        if not self._chat_history or self._chat_history[0].get("role") != "system":
            if system_prompt:
                self._chat_history.insert(0, {"role": "system", "content": system_prompt})
        else:
            # 最初の要素がシステムプロンプトの場合
            if system_prompt:
                self._chat_history[0] = {"role": "system", "content": system_prompt}
            else:
                # system_promptが空（チャットボタンなど）の場合は削除
                self._chat_history.pop(0)

        # ユーザー入力を履歴に追加
        self._chat_history.append({"role": "user", "content": text})

        # 前回のワーカーが残っている場合は終了を待たずに破棄
        if self._api_worker and self._api_worker.isRunning():
            self._api_worker.quit()

        # ローディング表示
        self._result_area.setPlainText("⏳ 処理中...（数秒〜数十秒かかります）\n\n")
        self._set_buttons_enabled(False)

        # ワーカー起動
        self._api_worker = ApiWorker(button_key=key, messages=self._chat_history)
        self._api_worker.result_ready.connect(self._on_result)
        self._api_worker.error_occurred.connect(self._on_error)
        self._api_worker.finished.connect(lambda: self._set_buttons_enabled(True))
        self._api_worker.start()

    def _on_result(self, answer: str):
        # AIの回答を履歴に追加
        self._chat_history.append({"role": "assistant", "content": answer})

        # 一括で結果を描画する
        self._result_area.setPlainText(answer)

        # 履歴展開エリアを更新する
        history_text = ""
        for msg in self._chat_history:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                continue
            elif role == "user":
                history_text += f"👤 あなた:\n{content}\n\n"
            elif role == "assistant":
                history_text += f"🤖 AI:\n{content}\n\n"
                history_text += "-" * 40 + "\n\n"

        self._history_area.setPlainText(history_text.strip())

        # もし展開されていれば、一番下までスクロール
        if self._history_toggle_btn.isChecked():
            h_scrollbar = self._history_area.verticalScrollBar()
            h_scrollbar.setValue(h_scrollbar.maximum())

        # スクロールバーを一番下に移動する
        scrollbar = self._result_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        # トグルボタンを有効化
        self._history_toggle_btn.setEnabled(True)

    def _on_error(self, msg: str):
        # エラー時は直前に追加したユーザー入力を取り消す
        if self._chat_history and self._chat_history[-1].get("role") == "user":
            self._chat_history.pop()

        # 最初に来る「⏳ 処理中...（数秒〜数十秒かかります）\n\n」を消すための簡易判定
        current_text = self._result_area.toPlainText()
        if current_text == "⏳ 処理中...（数秒〜数十秒かかります）\n\n":
            self._result_area.clear()

        # エラーメッセージを追記する
        self._result_area.insertPlainText(msg)

        # スクロールバーを一番下に移動する
        scrollbar = self._result_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        # エラー時は結果エリアを赤みがかった色にする（スタイルを一時変更）
        self._result_area.setStyleSheet(
            f"QTextEdit {{ color: #FF6B6B; background-color: rgba(80,10,10,200); "
            f"border: 1px solid rgba(255,80,80,0.4); border-radius:8px; "
            f"font-family:'Segoe UI','Yu Gothic UI',sans-serif; font-size:{self._current_font_size}pt; padding:10px; }}"
        )

    def _set_buttons_enabled(self, enabled: bool):
        for btn in self._buttons:
            btn.setEnabled(enabled)
        if hasattr(self, '_clear_btn'):
            self._clear_btn.setEnabled(enabled)

        if enabled:
            # エラー色をリセット
            self._result_area.setStyleSheet("")
            self._apply_style()

    # ------------------------------------------------------------------ #
    # イベントオーバーライド (ドラッグ移動 / フォントサイズ変更)
    # ------------------------------------------------------------------ #
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # QSizeGrip を常に右下に配置する
        self.size_grip.move(self.width() - self.size_grip.width(), self.height() - self.size_grip.height())
        self.size_grip.raise_()

    def eventFilter(self, obj, event):
        # QTextEdit 上の Ctrl+ホイールイベントをキャッチして処理
        if event.type() == event.Type.Wheel and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.wheelEvent(event)
            return True
        return super().eventFilter(obj, event)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self._current_font_size = min(32, self._current_font_size + 1)
            elif delta < 0:
                self._current_font_size = max(8, self._current_font_size - 1)
            self._apply_style()
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Plus or event.key() == Qt.Key.Key_Equal:
                self._current_font_size = min(32, self._current_font_size + 1)
                self._apply_style()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Minus:
                self._current_font_size = max(8, self._current_font_size - 1)
                self._apply_style()
                event.accept()
                return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def focusOutEvent(self, event):
        super().focusOutEvent(event)

    def hideEvent(self, event):
        # 非表示になる際にサイズと位置を保存する
        self._save_settings()
        super().hideEvent(event)

    def closeEvent(self, event: QCloseEvent):
        # 閉じる（×）ボタンなどが押された際、破棄せず非表示にする
        event.ignore()
        self.hide()
