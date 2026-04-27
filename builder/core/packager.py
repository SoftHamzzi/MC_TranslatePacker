"""
installer_stub.exe 끝에 payload zip을 이어붙여 설치 파일을 생성합니다.
파일 구조: [stub exe bytes] [payload.zip bytes] [8바이트: payload 시작 오프셋 (LE uint64)]
"""

import io
import json
import struct
import sys
import zipfile
from pathlib import Path


def _stub_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "installer_stub.exe"
    stub = Path(__file__).parent.parent.parent / "installer_stub.exe"
    if not stub.exists():
        raise FileNotFoundError(
            f"installer_stub.exe를 찾을 수 없습니다: {stub}\n"
            "uv run python build.py 를 먼저 실행해서 스텁을 빌드하세요."
        )
    return stub


def build_installer(
    modpack_id: int,
    modpack_name: str,
    modpack_slug: str,
    modpack_version: str,
    mc_version: str,
    translator: str,
    overwrite_zip: Path,
    resourcepack_zip: Path,
    output_path: Path,
    progress_callback=None,
) -> None:
    def _progress(msg: str):
        if progress_callback:
            progress_callback(msg)

    _progress("스텁 읽는 중...")
    stub_bytes = _stub_path().read_bytes()

    _progress("페이로드 압축 중...")
    meta = {
        "modpack_id": modpack_id,
        "modpack_name": modpack_name,
        "modpack_slug": modpack_slug,
        "modpack_version": modpack_version,
        "mc_version": mc_version,
        "translator": translator,
        "rp_filename": resourcepack_zip.name,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(overwrite_zip, "overwrite.zip")
        zf.write(resourcepack_zip, "resourcepack.zip")
        zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
    payload_bytes = buf.getvalue()

    _progress("설치 파일 저장 중...")
    offset = len(stub_bytes)
    with open(output_path, "wb") as f:
        f.write(stub_bytes)
        f.write(payload_bytes)
        f.write(struct.pack("<Q", offset))

    _progress(f"완료: {output_path.name} ({output_path.stat().st_size // 1024 // 1024}MB)")
