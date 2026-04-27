import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


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


def _extract_version(filename: str) -> str:
    """파일명에서 버전 문자열 추출. 예: 'Modpack-v1.2.zip' → 'v1.2'"""
    m = re.search(r'(v?\d+[\.\d]*\d)', filename)
    return m.group(1) if m else ""


@dataclass
class LocalModpack:
    launcher: str
    name: str
    project_id: Optional[int]
    mc_version: str
    modpack_version: str                         # 모드팩 버전 (예: v1.2)
    instance_path: Path
    minecraft_path: Path
    profile_image_path: Optional[Path] = None   # 사용자가 직접 설정한 로컬 이미지
    thumbnail_url: Optional[str] = None          # CurseForge CDN 썸네일 (폴백)


def _curseforge_candidates() -> list[Path]:
    home = Path.home()
    appdata = _appdata()
    candidates = []

    # storage.json에서 실제 설정 경로 읽기 (가장 신뢰할 수 있는 소스)
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


def _scan_curseforge() -> list[LocalModpack]:
    results = []
    seen: set[Path] = set()

    for base in _curseforge_candidates():
        if not base.exists() or base in seen:
            continue
        seen.add(base)

        for folder in sorted(base.iterdir()):
            if not folder.is_dir():
                continue
            manifest = folder / "minecraftinstance.json"
            if not manifest.exists():
                continue
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except Exception:
                continue

            name = data.get("name") or folder.name
            project_id = data.get("projectID")
            mc_version = data.get("gameVersion", "")
            imp = data.get("installedModpack") or {}
            thumbnail_url = imp.get("thumbnailUrl")
            inst_file = imp.get("installedFile") or {}
            modpack_version = _extract_version(inst_file.get("fileName") or "")

            # 사용자가 직접 설정한 로컬 이미지
            raw_img = data.get("profileImagePath")
            profile_image_path = Path(raw_img) if raw_img and Path(raw_img).is_file() else None

            results.append(LocalModpack(
                launcher="CurseForge",
                name=name,
                project_id=project_id,
                mc_version=mc_version,
                modpack_version=modpack_version,
                instance_path=folder,
                minecraft_path=folder,
                profile_image_path=profile_image_path,
                thumbnail_url=thumbnail_url,
            ))

    return results


def _scan_prism() -> list[LocalModpack]:
    results = []
    cfg = _appdata() / "PrismLauncher" / "prismlauncher.cfg"
    instances_dir = Path(
        _read_cfg_value(cfg, "InstanceDir")
        or str(_appdata() / "PrismLauncher" / "instances")
    )
    if not instances_dir.exists():
        return results

    for folder in sorted(instances_dir.iterdir()):
        mc = folder / ".minecraft"
        if not folder.is_dir() or folder.name.startswith(".") or not mc.exists():
            continue
        name = _read_cfg_value(folder / "instance.cfg", "name") or folder.name
        mc_version = _read_cfg_value(folder / "instance.cfg", "IntendedVersion") or ""
        results.append(LocalModpack(
            launcher="Prism Launcher",
            name=name,
            project_id=None,
            mc_version=mc_version,
            modpack_version="",
            instance_path=folder,
            minecraft_path=mc,
        ))

    return results


def _scan_multimc() -> list[LocalModpack]:
    results = []
    cfg = _appdata() / "MultiMC" / "multimc.cfg"
    instances_dir = Path(
        _read_cfg_value(cfg, "InstanceDir")
        or str(_appdata() / "MultiMC" / "instances")
    )
    if not instances_dir.exists():
        return results

    for folder in sorted(instances_dir.iterdir()):
        mc = folder / ".minecraft"
        if not folder.is_dir() or folder.name.startswith(".") or not mc.exists():
            continue
        name = _read_cfg_value(folder / "instance.cfg", "name") or folder.name
        mc_version = _read_cfg_value(folder / "instance.cfg", "IntendedVersion") or ""
        results.append(LocalModpack(
            launcher="MultiMC",
            name=name,
            project_id=None,
            mc_version=mc_version,
            modpack_version="",
            instance_path=folder,
            minecraft_path=mc,
        ))

    return results


def scan_all() -> list[LocalModpack]:
    return _scan_curseforge() + _scan_prism() + _scan_multimc()
