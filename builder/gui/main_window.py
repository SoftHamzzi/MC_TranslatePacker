from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSettings, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from builder.core.local_scanner import LocalModpack
from builder.gui.workers import BuildWorker, ScanWorker, ThumbnailWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minecraft 번역 간편 설치 파일 생성기")
        self.setMinimumSize(660, 600)

        self._modpacks: list[LocalModpack] = []
        self._filtered: list[LocalModpack] = []
        self._icons: dict[int, QIcon] = {}   # modpack 인덱스 → 아이콘 캐시
        self._placeholder_icon = self._make_placeholder_icon()
        self._selected: Optional[LocalModpack] = None
        self._overwrite_zip: Optional[Path] = None
        self._resourcepack_zip: Optional[Path] = None
        self._scan_worker: Optional[ScanWorker] = None
        self._thumb_worker: Optional[ThumbnailWorker] = None
        self._build_worker: Optional[BuildWorker] = None

        self._settings = QSettings("MCInstallerBuilder", "Builder")

        self._build_ui()
        self._load_settings()
        self._do_scan()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        root.addWidget(self._make_modpack_section())
        root.addWidget(self._make_files_section())
        root.addWidget(self._make_build_section())
        root.addWidget(self._make_log_section())

    def _make_modpack_section(self) -> QGroupBox:
        group = QGroupBox("1단계 — 모드팩 선택")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)

        # Filter + Scan row
        top_row = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("이름으로 필터...")
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.scan_btn = QPushButton("새로고침")
        self.scan_btn.setFixedWidth(80)
        self.scan_btn.clicked.connect(self._do_scan)
        top_row.addWidget(self.filter_edit)
        top_row.addWidget(self.scan_btn)
        layout.addLayout(top_row)

        # List
        self.modpack_list = QListWidget()
        self.modpack_list.setFixedHeight(200)
        self.modpack_list.setIconSize(QSize(48, 48))
        self.modpack_list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self.modpack_list)

        # Selected label
        self.selected_label = QLabel("선택된 모드팩: 없음")
        self.selected_label.setStyleSheet("color: #888;")
        layout.addWidget(self.selected_label)

        return group

    def _make_files_section(self) -> QGroupBox:
        group = QGroupBox("2단계 — 번역 파일 선택 및 번역자")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self._file_row("덮어쓰기 파일 (zip):", "overwrite_label", self._pick_overwrite))
        layout.addWidget(self._file_row("리소스팩 파일 (zip):", "resourcepack_label", self._pick_resourcepack))

        # 번역자 입력
        translator_row = QWidget()
        row = QHBoxLayout(translator_row)
        row.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("번역자 이름:")
        lbl.setFixedWidth(160)
        self.translator_edit = QLineEdit()
        self.translator_edit.setPlaceholderText("예: Hamrang (공백 가능)")
        self.translator_edit.textChanged.connect(
            lambda t: self._settings.setValue("translator", t)
        )
        row.addWidget(lbl)
        row.addWidget(self.translator_edit)
        layout.addWidget(translator_row)

        return group

    def _file_row(self, label_text: str, attr: str, callback) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel(label_text)
        lbl.setFixedWidth(160)

        path_lbl = QLabel("선택 안 됨")
        path_lbl.setStyleSheet("color: #888;")
        path_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        setattr(self, attr, path_lbl)

        btn = QPushButton("파일 선택")
        btn.setFixedWidth(80)
        btn.clicked.connect(callback)

        row.addWidget(lbl)
        row.addWidget(path_lbl)
        row.addWidget(btn)
        return widget

    def _make_build_section(self) -> QGroupBox:
        group = QGroupBox("3단계 — 생성")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)

        self.build_btn = QPushButton("간편 설치 파일 생성")
        self.build_btn.setEnabled(False)
        self.build_btn.setMinimumHeight(40)
        f = QFont()
        f.setPointSize(11)
        f.setBold(True)
        self.build_btn.setFont(f)
        self.build_btn.clicked.connect(self._do_build)
        layout.addWidget(self.build_btn)

        return group

    def _make_log_section(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel("진행 상태")
        lbl.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(90)
        self.log_box.setStyleSheet("font-family: monospace; font-size: 11px;")
        layout.addWidget(self.log_box)

        return widget

    @staticmethod
    def _make_placeholder_icon() -> QIcon:
        px = QPixmap(48, 48)
        px.fill(QColor("white"))
        return QIcon(px)

    def _load_settings(self):
        self.translator_edit.setText(self._settings.value("translator", ""))

    # ── Logic ─────────────────────────────────────────────────────────────────

    def _do_scan(self):
        self.scan_btn.setEnabled(False)
        self.modpack_list.clear()
        self._modpacks = []
        self._filtered = []
        self._icons = {}
        self._selected = None
        self._log("로컬 런처에서 모드팩을 스캔하는 중...")

        self._scan_worker = ScanWorker()
        self._scan_worker.results.connect(self._on_scan_results)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _on_scan_results(self, modpacks: list):
        self._modpacks = modpacks
        self._apply_filter(self.filter_edit.text())
        self.scan_btn.setEnabled(True)
        self._log(f"{len(modpacks)}개 모드팩을 찾았습니다.")

        # 썸네일 백그라운드 다운로드 시작
        self._thumb_worker = ThumbnailWorker(modpacks)
        self._thumb_worker.loaded.connect(self._on_thumbnail_loaded)
        self._thumb_worker.start()

    def _on_scan_error(self, error: str):
        self.scan_btn.setEnabled(True)
        self._log(f"스캔 오류: {error}")

    def _on_thumbnail_loaded(self, modpack_index: int, pixmap: QPixmap):
        scaled = pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        icon = QIcon(scaled)
        self._icons[modpack_index] = icon  # 캐시에 저장

        # 현재 필터된 목록에 보이고 있으면 바로 적용
        mp = self._modpacks[modpack_index]
        try:
            row = self._filtered.index(mp)
            item = self.modpack_list.item(row)
            if item:
                item.setIcon(icon)
        except ValueError:
            pass

    def _apply_filter(self, text: str):
        keyword = text.strip().lower()
        self.modpack_list.clear()
        self._filtered = []
        for i, mp in enumerate(self._modpacks):
            if keyword and keyword not in mp.name.lower():
                continue
            self._filtered.append(mp)
            ver = f" ({mp.mc_version})" if mp.mc_version else ""
            item = QListWidgetItem(f"[{mp.launcher}]  {mp.name}{ver}")
            item.setIcon(self._icons.get(i, self._placeholder_icon))
            self.modpack_list.addItem(item)

    def _on_row_changed(self, row: int):
        filtered = getattr(self, "_filtered", self._modpacks)
        if row < 0 or row >= len(filtered):
            self._selected = None
            self.selected_label.setText("선택된 모드팩: 없음")
            self.selected_label.setStyleSheet("color: #888;")
        else:
            self._selected = filtered[row]
            self.selected_label.setText(
                f"선택됨: {self._selected.name}  [{self._selected.launcher}]"
            )
            self.selected_label.setStyleSheet("color: #1a6a1a; font-weight: bold;")
        self._refresh_build_btn()

    def _pick_overwrite(self):
        path, _ = QFileDialog.getOpenFileName(self, "덮어쓰기 파일 선택", "", "ZIP 파일 (*.zip)")
        if path:
            self._overwrite_zip = Path(path)
            self.overwrite_label.setText(path)
            self.overwrite_label.setStyleSheet("color: #1a1a8a;")
        self._refresh_build_btn()

    def _pick_resourcepack(self):
        path, _ = QFileDialog.getOpenFileName(self, "리소스팩 파일 선택", "", "ZIP 파일 (*.zip)")
        if path:
            self._resourcepack_zip = Path(path)
            self.resourcepack_label.setText(path)
            self.resourcepack_label.setStyleSheet("color: #1a1a8a;")
        self._refresh_build_btn()

    def _refresh_build_btn(self):
        self.build_btn.setEnabled(
            bool(self._selected and self._overwrite_zip and self._resourcepack_zip)
        )

    def _do_build(self):
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "설치 파일 저장 위치",
            f"{self._selected.name}_번역설치.exe",
            "실행 파일 (*.exe)",
        )
        if not output_path:
            return

        self.build_btn.setEnabled(False)
        self._log("빌드 시작... (수 분 소요될 수 있습니다)")

        self._build_worker = BuildWorker(
            modpack=self._selected,
            translator=self.translator_edit.text().strip(),
            overwrite_zip=self._overwrite_zip,
            resourcepack_zip=self._resourcepack_zip,
            output_path=Path(output_path),
        )
        self._build_worker.progress.connect(self._log)
        self._build_worker.finished.connect(self._on_build_finished)
        self._build_worker.start()

    def _on_build_finished(self, error: str):
        if error:
            self._log(f"빌드 실패: {error}")
            QMessageBox.critical(self, "빌드 실패", f"설치 파일 생성 실패:\n\n{error}")
        else:
            self._log("빌드 완료!")
            QMessageBox.information(
                self,
                "완료",
                "간편 설치 파일이 생성되었습니다.\n\n"
                "이 .exe 파일을 디스코드, 카페 등에 공유하면\n"
                "사용자가 더블클릭 한 번으로 번역을 설치할 수 있습니다.",
            )
        self._refresh_build_btn()

    def _log(self, message: str):
        self.log_box.append(message)
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum()
        )
