# TranslatePacker — 기획 문서

## 배경 및 문제 정의

### 기존 흐름 (Minecraft Modpack Translator)

```
사용자 → GUI 실행 → CurseForge 모드팩 선택 → LLM 번역
       → 결과물 2개 생성
           ├── 덮어쓰기 파일 (overwrite): 모드팩 폴더에 직접 덮어씌우는 파일들
           └── 리소스팩 파일 (resource pack): 게임 내 리소스팩으로 적용하는 파일
```

### 문제점

수동 설치 절차가 복잡해 일반 사용자가 따라하기 어렵다.

**수동 설치 절차:**
1. 덮어쓰기 파일 압축 해제
2. 압축 해제한 파일들을 모드팩 폴더에 덮어쓰기
3. 리소스팩 파일을 게임 리소스팩 폴더에 복사
4. 게임 내 설정 화면에서 리소스팩을 직접 활성화

→ 이 과정을 다른 사람에게 설명하고 도움을 주는 것이 번거로워 번역의 대중화를 가로막는 장벽이 됨

---

## 목표

**수동 설치 파일 2개 → 실행 한 번으로 끝나는 간편 설치 파일 1개** 로 묶어주는 별도 도구를 만든다.

```
[덮어쓰기 파일] ─┐
                  ├→ [TranslatePacker] → [간편 설치 파일 (.exe)]
[리소스팩 파일] ─┘
                             ↓ 실행하면
                  덮어쓰기 + 리소스팩 복사까지 자동으로 완료
                  (리소스팩 활성화는 게임 내에서 직접 해야 함)
```

---

## 지원 범위

- **플랫폼**: Windows 전용
- **런처**: CurseForge (자동 감지), Prism Launcher, MultiMC (수동 선택)
- **배포**: 독립 배포 (외부 웹사이트 연동 없음)

---

## 사용 흐름

### 번역 배포자
1. `TranslatePacker.exe` 실행
2. 모드팩 선택 (로컬 인스턴스 자동 스캔)
3. 덮어쓰기 zip + 리소스팩 zip 선택
4. 번역자 이름 입력
5. "간편 설치 파일 생성" → `.exe` 저장
6. 만들어진 `.exe`를 디스코드/카페에 공유

### 최종 사용자
1. `.exe` 더블클릭
2. 인스턴스 확인 (자동 감지)
3. "번역 설치 시작"
4. 게임 실행 후 리소스팩 수동 활성화

---

## 구현 완료 기능

### TranslatePacker (`builder/`)

- 로컬 CurseForge / Prism / MultiMC 인스턴스 자동 스캔
  - `%APPDATA%\CurseForge\storage.json`의 `minecraftRoot` 값으로 정확한 경로 탐색
  - 폴백: 공통 기본 경로 3개
- 모드팩 이름 필터링
- 모드팩 썸네일 표시
  - 1순위: `profileImagePath` (사용자가 직접 설정한 로컬 이미지)
  - 2순위: `installedModpack.thumbnailUrl` (CDN, 로컬 캐시 후 재사용)
  - 없는 경우: 흰색 플레이스홀더
- 덮어쓰기 zip / 리소스팩 zip 파일 선택
- 번역자 이름 입력 (앱 재시작 후에도 유지 — QSettings)
- 설치 파일 생성 방식: `installer_stub.exe` 뒤에 payload zip 이어붙이기 (수 초 완료)

### 생성된 설치 파일 (`installer_template/`)

- 창 제목 및 UI에 모드팩 버전 / MC 버전 표시
- 번역자 이름 표시 (`번역: Hamrang`)
- CurseForge 인스턴스 자동 감지 (storage.json → projectID 매칭)
- 감지된 인스턴스 버튼 클릭 시 시각적 강조 (초록색)
- 직접 경로 선택 지원
- 설치 전 기존 파일 백업 (`_번역백업_날짜시간/` 폴더)
- 덮어쓰기 zip 추출 로직
  - 래퍼 폴더(`overrides` 등)만 제거, 실제 MC 폴더(`config`, `kubejs` 등)는 유지
- 리소스팩 zip → `resourcepacks/` 폴더에 복사
- 설치 완료 시 리소스팩 수동 활성화 안내 + 백업 경로 안내

---

## 기술 스택

| 영역 | 선택 |
|------|------|
| 언어 | Python 3.12 |
| GUI (빌더) | PySide6 |
| GUI (설치 파일) | PySide6 |
| 설치 파일 패키징 | 스텁 + payload 이어붙이기 방식 |
| 빌더 배포 | PyInstaller (`--onefile`) + `build.bat` |
| 설치 로직 | zipfile + shutil + pathlib |
| 설정 저장 | QSettings (레지스트리) |
| 이미지 캐시 | `%APPDATA%\MCInstallerBuilder\img_cache\` |

---

## 프로젝트 구조

```
auto/
├── build.py                  ← 스텁 + TranslatePacker.exe 빌드 스크립트
├── build.bat                 ← build.py 실행 단축키
├── installer_stub.exe        ← 미리 컴파일된 설치 파일 스텁
├── pyproject.toml
├── builder/                  ← TranslatePacker 소스
│   ├── __main__.py
│   ├── core/
│   │   ├── local_scanner.py
│   │   └── packager.py
│   └── gui/
│       ├── main_window.py
│       └── workers.py
└── installer_template/
    └── main.py               ← 스텁의 소스 (수정 시 build.bat 재실행)
```

---

## 미결 사항

1. **설치 파일 용량**: PySide6 번들로 인해 100MB+. tkinter로 교체 시 ~15MB로 감소 가능
2. **모드팩 버전 대응**: 모드팩 업데이트 시 설치 파일 재생성 필요 — 별도 가이드 없음
