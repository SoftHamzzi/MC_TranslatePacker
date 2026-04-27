"""
빌드 순서:
  1. installer_stub.exe 빌드 (installer_template/main.py → installer_stub.exe)
  2. 빌더 exe 빌드 (builder/ → TranslatePacker.exe), 스텁을 내부에 포함
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def run(cmd: list):
    print("$", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)


def build_stub():
    print("\n=== 1단계: installer_stub.exe 빌드 ===")
    run([
        sys.executable, "-m", "PyInstaller",
        str(ROOT / "installer_template" / "main.py"),
        "--name", "installer_stub",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--distpath", str(ROOT / "builds"),
        "--workpath", str(ROOT / "build_tmp" / "stub"),
        "--specpath", str(ROOT / "build_tmp"),
    ])
    stub_src = ROOT / "builds" / "installer_stub.exe"
    stub_dst = ROOT / "installer_stub.exe"
    shutil.copy2(stub_src, stub_dst)
    print(f"스텁 저장됨: {stub_dst} ({stub_dst.stat().st_size // 1024 // 1024}MB)")


def build_builder():
    print("\n=== 2단계: 빌더 exe 빌드 ===")
    stub = ROOT / "installer_stub.exe"
    if not stub.exists():
        raise FileNotFoundError("installer_stub.exe 가 없습니다. 먼저 1단계를 실행하세요.")

    run([
        sys.executable, "-m", "PyInstaller",
        str(ROOT / "builder" / "__main__.py"),
        "--name", "TranslatePacker",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--distpath", str(ROOT / "builds"),
        "--workpath", str(ROOT / "build_tmp" / "builder"),
        "--specpath", str(ROOT / "build_tmp"),
        "--add-data", f"{stub};.",
    ])
    result = ROOT / "builds" / "TranslatePacker.exe"
    print(f"\n빌드 완료: {result} ({result.stat().st_size // 1024 // 1024}MB)")


if __name__ == "__main__":
    build_stub()
    build_builder()
