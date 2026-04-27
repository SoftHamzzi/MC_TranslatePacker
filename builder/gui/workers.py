import hashlib
import os
from pathlib import Path

import httpx
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QPixmap

from builder.core.local_scanner import LocalModpack, scan_all
from builder.core.packager import build_installer

_CACHE_DIR = Path(os.environ.get("APPDATA", Path.home())) / "MCInstallerBuilder" / "img_cache"


class ThumbnailWorker(QThread):
    """스캔된 모드팩 목록의 썸네일을 순차적으로 다운로드해 Signal로 전달."""
    loaded = Signal(int, QPixmap)  # (list index, pixmap)

    def __init__(self, modpacks: list[LocalModpack]):
        super().__init__()
        self.modpacks = modpacks

    def run(self):
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        for i, mp in enumerate(self.modpacks):
            try:
                pixmap = self._load_for(mp)
                if pixmap and not pixmap.isNull():
                    self.loaded.emit(i, pixmap)
            except Exception:
                pass

    def _load_for(self, mp: LocalModpack) -> QPixmap | None:
        # 1순위: 사용자가 직접 설정한 로컬 이미지
        if mp.profile_image_path:
            pixmap = QPixmap()
            pixmap.load(str(mp.profile_image_path))
            if not pixmap.isNull():
                return pixmap

        # 2순위: CurseForge CDN 썸네일 (로컬 캐시 후 반환)
        if mp.thumbnail_url:
            return self._download_cached(mp.thumbnail_url)

        return None

    def _download_cached(self, url: str) -> QPixmap | None:
        key = hashlib.md5(url.encode()).hexdigest()
        cache_file = _CACHE_DIR / f"{key}.webp"

        if not cache_file.exists():
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            resp.raise_for_status()
            cache_file.write_bytes(resp.content)

        pixmap = QPixmap()
        pixmap.load(str(cache_file))
        return pixmap


class ScanWorker(QThread):
    results = Signal(list)
    error = Signal(str)

    def run(self):
        try:
            modpacks = scan_all()
            self.results.emit(modpacks)
        except Exception as e:
            self.error.emit(str(e))


class BuildWorker(QThread):
    progress = Signal(str)
    finished = Signal(str)  # empty = success

    def __init__(
        self,
        modpack: LocalModpack,
        translator: str,
        overwrite_zip: Path,
        resourcepack_zip: Path,
        output_path: Path,
    ):
        super().__init__()
        self.modpack = modpack
        self.translator = translator
        self.overwrite_zip = overwrite_zip
        self.resourcepack_zip = resourcepack_zip
        self.output_path = output_path

    def run(self):
        try:
            build_installer(
                modpack_id=self.modpack.project_id or 0,
                modpack_name=self.modpack.name,
                modpack_slug="",
                modpack_version=self.modpack.modpack_version,
                mc_version=self.modpack.mc_version,
                translator=self.translator,
                overwrite_zip=self.overwrite_zip,
                resourcepack_zip=self.resourcepack_zip,
                output_path=self.output_path,
                progress_callback=lambda msg: self.progress.emit(msg),
            )
            self.finished.emit("")
        except Exception as e:
            self.finished.emit(str(e))
