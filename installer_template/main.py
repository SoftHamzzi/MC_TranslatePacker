"""
installer_stub.exe로 컴파일된 뒤, 빌더가 exe 끝에 payload zip을 이어붙입니다.
실행 시 자기 자신의 끝부분에서 payload를 읽어 임시 폴더에 추출합니다.
"""

import atexit
import io
import json
import os
import shutil
import struct
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


# ── Resource Path ──────────────────────────────────────────────────────────────
# exe 파일 구조: [stub exe bytes] [payload.zip bytes] [8바이트: payload 시작 오프셋]

_data_path: Optional[Path] = None


def _init_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        with open(exe, "rb") as f:
            f.seek(-8, 2)
            offset = struct.unpack("<Q", f.read(8))[0]
            f.seek(offset)
            payload = f.read(exe.stat().st_size - offset - 8)

        tmp = Path(tempfile.mkdtemp(prefix="mc_trans_"))
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            zf.extractall(tmp)
        atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
        return tmp

    # 소스 실행 시 (개발용)
    return Path(__file__).parent / "data"


def _data_dir() -> Path:
    global _data_path
    if _data_path is None:
        _data_path = _init_data_dir()
    return _data_path


def _load_meta() -> dict:
    return json.loads((_data_dir() / "meta.json").read_text(encoding="utf-8"))


# ── Launcher / Instance Detection ──────────────────────────────────────────────

def _appdata() -> Path:
    return Path(os.environ.get("APPDATA", Path.home()))


def _read_cfg_value(cfg_path: Path, key: str) -> Optional[str]:
    try:
        for line in cfg_path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None


def _instance_name(folder: Path) -> str:
    cfg = folder / "instance.cfg"
    return _read_cfg_value(cfg, "name") or folder.name


def _curseforge_candidates() -> list[Path]:
    home = Path.home()
    appdata = _appdata()
    candidates = []

    # storage.json에서 실제 설정 경로 읽기
    storage = appdata / "CurseForge" / "storage.json"
    if storage.exists():
        try:
            raw = json.loads(storage.read_text(encoding="utf-8"))
            mc_settings = raw.get("minecraft-settings", "{}")
            if isinstance(mc_settings, str):
                mc_settings = json.loads(mc_settings)
            root = mc_settings.get("minecraftRoot")
            if root:
                candidates.append(Path(root) / "Instances")
        except Exception:
            pass

    # 폴백: 공통 기본 경로들
    candidates += [
        appdata / "CurseForge" / "minecraft" / "Instances",
        home / "curseforge" / "minecraft" / "Instances",
        home / "CurseForge" / "minecraft" / "Instances",
    ]
    return candidates


def find_instances(modpack_id: int) -> list[dict]:
    results = []
    seen: set[Path] = set()

    # ── CurseForge ──
    for cf_root in _curseforge_candidates():
        if not cf_root.exists() or cf_root in seen:
            continue
        seen.add(cf_root)

        for folder in sorted(cf_root.iterdir()):
            if not folder.is_dir():
                continue
            manifest = folder / "minecraftinstance.json"
            if not manifest.exists():
                continue
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except Exception:
                continue
            if data.get("projectID") == modpack_id:
                results.append({
                    "launcher": "CurseForge",
                    "name": data.get("name", folder.name),
                    # CurseForge 인스턴스 폴더 자체가 .minecraft 역할을 함
                    "minecraft_path": folder,
                })

    # ── Prism Launcher ──
    prism_cfg = _appdata() / "PrismLauncher" / "prismlauncher.cfg"
    prism_instances = Path(
        _read_cfg_value(prism_cfg, "InstanceDir")
        or str(_appdata() / "PrismLauncher" / "instances")
    )
    if prism_instances.exists():
        for folder in sorted(prism_instances.iterdir()):
            mc = folder / ".minecraft"
            if not folder.is_dir() or folder.name.startswith(".") or not mc.exists():
                continue
            results.append({
                "launcher": "Prism Launcher",
                "name": _instance_name(folder),
                "minecraft_path": mc,
            })

    # ── MultiMC ──
    mmc_cfg = _appdata() / "MultiMC" / "multimc.cfg"
    mmc_instances = Path(
        _read_cfg_value(mmc_cfg, "InstanceDir")
        or str(_appdata() / "MultiMC" / "instances")
    )
    if mmc_instances.exists():
        for folder in sorted(mmc_instances.iterdir()):
            mc = folder / ".minecraft"
            if not folder.is_dir() or folder.name.startswith(".") or not mc.exists():
                continue
            results.append({
                "launcher": "MultiMC",
                "name": _instance_name(folder),
                "minecraft_path": mc,
            })

    return results


# ── Install Worker ─────────────────────────────────────────────────────────────

class InstallWorker(QThread):
    progress = Signal(int, int, str)
    finished = Signal(str)   # empty = success

    def __init__(self, minecraft_path: Path, rp_filename: str):
        super().__init__()
        self.minecraft_path = minecraft_path
        self.rp_filename = rp_filename

    def run(self):
        try:
            data = _data_dir()
            overwrite_zip = data / "overwrite.zip"
            rp_zip = data / "resourcepack.zip"

            with zipfile.ZipFile(overwrite_zip, "r") as zf:
                entries = [e for e in zf.namelist() if not e.endswith("/")]
                strip = _strip_root(zf)
                total = len(entries) + 1

                # 덮어쓸 파일 중 이미 존재하는 것만 백업
                backup_dir = self.minecraft_path / f"_번역백업_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                backed_up = False
                for entry in entries:
                    parts = Path(entry).parts
                    rel = Path(*parts[1:]) if (len(parts) > 1 and strip) else Path(entry)
                    dest = self.minecraft_path / rel
                    if dest.exists():
                        backup_dest = backup_dir / rel
                        backup_dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(dest, backup_dest)
                        backed_up = True

                for i, entry in enumerate(entries):
                    self.progress.emit(i, total, f"적용 중: {entry}")
                    parts = Path(entry).parts
                    rel = Path(*parts[1:]) if (len(parts) > 1 and strip) else Path(entry)
                    dest = self.minecraft_path / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(zf.read(entry))

            self._backed_up = backup_dir if backed_up else None

            rp_dest_dir = self.minecraft_path / "resourcepacks"
            rp_dest_dir.mkdir(parents=True, exist_ok=True)
            dest_name = self.rp_filename if self.rp_filename else rp_zip.name
            self.progress.emit(len(entries), len(entries) + 1, "리소스팩 복사 중...")
            shutil.copy2(rp_zip, rp_dest_dir / dest_name)

            self.finished.emit("")
        except Exception as exc:
            self.finished.emit(str(exc))


_MC_CONTENT_DIRS = {
    "config", "mods", "resourcepacks", "saves", "screenshots", "logs",
    "kubejs", "scripts", "data", "journeymap", "shaderpacks", "texturepacks",
    "defaultconfigs", "openloader", "assets", "global_packs", "patchouli_books",
}

def _strip_root(zf: zipfile.ZipFile) -> bool:
    """최상위 폴더가 래퍼(overrides 등)일 때만 True — 실제 MC 폴더면 스트립하지 않음."""
    roots = {Path(n).parts[0] for n in zf.namelist() if Path(n).parts}
    if len(roots) != 1:
        return False
    return roots.pop().lower() not in _MC_CONTENT_DIRS


# ── GUI ────────────────────────────────────────────────────────────────────────

class InstallerWindow(QMainWindow):
    def __init__(self, meta: dict, instances: list[dict]):
        super().__init__()
        self.meta = meta
        self.instances = instances
        self.selected_path: Optional[Path] = None
        self._worker: Optional[InstallWorker] = None

        ver = meta.get("modpack_version", "")
        mc_ver = meta.get("mc_version", "")
        ver_str = " ".join(filter(None, [ver, f"MC {mc_ver}" if mc_ver else ""]))
        self.setWindowTitle(f"{meta['modpack_name']} 번역 설치" + (f" ({ver_str})" if ver_str else ""))
        self.setMinimumWidth(560)
        self.setFixedWidth(560)

        self._build_ui()

        if instances and self._instance_btns:
            self._select(instances[0]["minecraft_path"], instances[0], self._instance_btns[0])

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(10)
        root.setContentsMargins(18, 18, 18, 18)

        # Title
        ver_str = " ".join(filter(None, [self.meta.get("modpack_version",""), f"MC {self.meta.get('mc_version','')}" if self.meta.get('mc_version') else ""]))
        title_text = f"🎮 {self.meta['modpack_name']} — 번역 설치" + (f"  ({ver_str})" if ver_str else "")
        title = QLabel(title_text)
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        title.setFont(font)
        root.addWidget(title)

        translator = self.meta.get("translator", "").strip()
        if translator:
            tl = QLabel(f"번역: {translator}")
            tl.setStyleSheet("color: #555;")
            root.addWidget(tl)

        # Detected instances
        self._instance_btns: list[QPushButton] = []
        if self.instances:
            detected = QGroupBox("인스턴스 선택")
            dl = QVBoxLayout(detected)
            dl.setSpacing(4)
            for inst in self.instances[:6]:
                btn = QPushButton(f"[{inst['launcher']}]  {inst['name']}")
                btn.setStyleSheet("text-align: left; padding: 6px 10px;")
                btn.setCheckable(True)
                p = inst["minecraft_path"]
                btn.setToolTip(str(p))
                btn.clicked.connect(lambda _, path=p, i=inst, b=btn: self._select(path, i, b))
                dl.addWidget(btn)
                self._instance_btns.append(btn)
            root.addWidget(detected)
        else:
            note = QLabel(
                "⚠️ 이 모드팩의 인스턴스를 자동으로 찾을 수 없습니다.\n"
                "아래 '직접 선택'으로 경로를 지정해 주세요."
            )
            note.setStyleSheet("color: #b85c00;")
            note.setWordWrap(True)
            root.addWidget(note)

        # Selected path display
        path_group = QGroupBox("선택된 경로")
        pl = QVBoxLayout(path_group)
        self.path_label = QLabel("선택 안 됨")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("color: #888;")
        pl.addWidget(self.path_label)
        browse_btn = QPushButton("직접 선택...")
        browse_btn.setFixedWidth(100)
        browse_btn.clicked.connect(self._browse)
        pl.addWidget(browse_btn, alignment=Qt.AlignmentFlag.AlignRight)
        root.addWidget(path_group)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        root.addStretch()

        # Install button
        self.install_btn = QPushButton("번역 설치 시작")
        self.install_btn.setEnabled(False)
        self.install_btn.setMinimumHeight(44)
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        self.install_btn.setFont(f)
        self.install_btn.clicked.connect(self._start_install)
        root.addWidget(self.install_btn)

    def _select(self, path: Path, inst: Optional[dict] = None, active_btn: Optional[QPushButton] = None):
        self.selected_path = path
        label = str(path)
        if inst:
            label = f"[{inst['launcher']}] {inst['name']}\n{path}"
        self.path_label.setText(label)
        self.path_label.setStyleSheet("color: #1a6a1a; font-weight: bold;")
        self.install_btn.setEnabled(True)

        # 선택된 버튼만 강조
        for btn in self._instance_btns:
            is_active = (btn is active_btn)
            btn.setChecked(is_active)
            btn.setStyleSheet(
                "text-align: left; padding: 6px 10px; background-color: #c8e6c9; font-weight: bold;"
                if is_active else
                "text-align: left; padding: 6px 10px;"
            )

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, "모드팩 게임 폴더 선택 (.minecraft 또는 인스턴스 폴더)", str(Path.home())
        )
        if folder:
            self._select(Path(folder))

    def _start_install(self):
        if not self.selected_path:
            return
        self.install_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("설치 중...")

        rp_filename = self.meta.get("rp_filename", "resourcepack.zip")
        self._worker = InstallWorker(self.selected_path, rp_filename)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, current: int, total: int, message: str):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.status_label.setText(message)

    def _on_finished(self, error: str):
        self.progress_bar.setVisible(False)
        if error:
            self.status_label.setText("설치 실패.")
            self.install_btn.setEnabled(True)
            QMessageBox.critical(self, "설치 실패", f"설치 중 오류가 발생했습니다:\n{error}")
        else:
            self.status_label.setText("✅ 설치 완료!")
            backup_note = ""
            if self._worker and self._worker._backed_up:
                backup_note = f"\n\n💾 기존 파일 백업 위치:\n{self._worker._backed_up}"
            QMessageBox.information(
                self,
                "설치 완료",
                "번역이 성공적으로 설치되었습니다! 🎉\n\n"
                "📌 리소스팩 활성화 방법 (필수):\n"
                "게임을 실행한 뒤\n"
                "설정 (Options) → 리소스팩 (Resource Packs)\n"
                f"화면에서 번역 리소스팩을 직접 활성화해 주세요.{backup_note}",
            )
            self.close()


# ── Entry Point ────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    try:
        meta = _load_meta()
    except Exception as e:
        QMessageBox.critical(None, "오류", f"설치 파일이 손상되었습니다:\n{e}")
        sys.exit(1)

    instances = find_instances(meta.get("modpack_id", -1))

    window = InstallerWindow(meta, instances)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
