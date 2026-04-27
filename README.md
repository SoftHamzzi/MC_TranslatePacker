# TranslatePacker

마인크래프트 모드팩 번역 파일을 **클릭 한 번으로 설치**할 수 있는 설치 파일로 묶어주는 도구입니다.

---

## 개요

[Minecraft Modpack Translator](https://github.com/kunho-park/minecraft-translator)로 번역을 완료하면 **덮어쓰기 파일**과 **리소스팩 파일** 두 개가 생성됩니다.  
이 두 파일을 직접 설치하는 과정은 일반 사용자에게 복잡하고 번거롭습니다.

**TranslatePacker**는 이 두 파일을 받아 누구나 더블클릭 한 번으로 설치할 수 있는 단일 `.exe` 파일을 만들어줍니다.

```
[덮어쓰기 파일] ─┐
                  ├→ TranslatePacker → 설치파일.exe
[리소스팩 파일] ─┘
                          ↓ 실행하면
              모드팩에 번역이 자동으로 적용됨
```

---

## 주요 기능

- 🔍 **로컬 모드팩 자동 탐색** — CurseForge, Prism Launcher, MultiMC 지원
- 🖼️ **모드팩 썸네일 표시** — 로컬 이미지 또는 CurseForge CDN에서 자동 로드
- 👤 **번역자 이름 포함** — 생성된 설치 파일에 번역자 정보 표시
- 💾 **기존 파일 자동 백업** — 설치 전 원본 파일 보존
- ⚡ **빠른 생성** — 수 초 만에 설치 파일 생성 (컴파일 없음)

---

## 사용 방법

### 번역 배포자

1. `TranslatePacker.exe` 실행
2. 목록에서 모드팩 선택
3. 덮어쓰기 파일(zip)과 리소스팩 파일(zip) 선택
4. 번역자 이름 입력 (선택)
5. **간편 설치 파일 생성** 클릭
6. 생성된 `.exe`를 디스코드, 카페 등에 공유

### 최종 사용자 (번역 받는 사람)

1. 공유받은 `.exe` 더블클릭
2. 자동 감지된 인스턴스 확인 (또는 직접 선택)
3. **번역 설치 시작** 클릭
4. 게임 실행 후 설정 → 리소스팩에서 번역 리소스팩 활성화

---

## 지원 환경

- **OS**: Windows
- **런처**: CurseForge, Prism Launcher, MultiMC

---

## 빌드 방법

### 요구사항

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)

### 설치

```bash
git clone https://github.com/softhamzzi/MC_TranslatePacker.git
cd MC_TranslatePacker
uv sync
```

### 빌드

```bash
# build.bat 더블클릭 또는:
uv run python build.py
```

`dist/TranslatePacker.exe` 가 생성됩니다.

### 소스에서 직접 실행

```bash
uv run python -m builder
```

---

## 프로젝트 구조

```
TranslatePacker/
├── build.py                  # 빌드 스크립트
├── build.bat                 # 빌드 단축키
├── installer_stub.exe        # 미리 컴파일된 설치 파일 스텁
├── builder/                  # TranslatePacker 소스
│   ├── core/
│   │   ├── local_scanner.py  # 로컬 런처 인스턴스 탐색
│   │   └── packager.py       # 설치 파일 생성
│   └── gui/
│       ├── main_window.py
│       └── workers.py
└── installer_template/
    └── main.py               # 생성되는 설치 파일의 소스
```

---

## 기술 스택

| 영역 | 선택 |
|------|------|
| 언어 | Python 3.12 |
| GUI | PySide6 |
| 패키징 | PyInstaller + 스텁 이어붙이기 방식 |
