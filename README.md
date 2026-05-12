# GOE Messenger to Todo26 Auto-Bridge

경기도교육청(GOE) 메신저의 쪽지 내용을 분석하여 Todo26 사이트에 자동으로 등록해주는 자동화 브릿지입니다.

## 주요 기능
- **실시간 복호화**: 32비트 헬퍼(`at_decryptor.exe`)를 사용하여 암호화된 메신저 DB를 실시간으로 복합화 및 스캔합니다.
- **AI 업무 분석**: Google Gemini 1.5 Flash 모델을 사용하여 쪽지 내용 중 실제 '업무'를 판별하고 제목과 내용을 추출합니다.
- **중복 방지**: 이미 처리된 메시지 ID를 추적하여 동일한 업무가 중복 등록되지 않도록 관리합니다.
- **Todo26 연동**: 분석된 업무를 Todo26 사이트의 API를 통해 자동으로 등록합니다.

## 설치 및 설정 방법

### 1. 요구 사항
- Python 3.8 이상
- 경기도교육청 메신저(AtMessenger) 설치 및 로그인 상태

### 2. 라이브러리 설치
```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정 (`.env`) 및 인증
1. 프로젝트 루트 폴더에 `.env` 파일을 생성하고 다음 정보를 입력합니다.
```env
GEMINI_API_KEY=your_gemini_api_key_here
TODO26_TOKEN=your_todo26_token_here
TODO26_URL=https://www.todo26.site
```

### 4. 실행 방법
`run.bat` 파일을 실행하거나 터미널에서 다음 명령어를 입력합니다.
```bash
python goe_bridge.py
```
프로그램은 5분 주기로 새로운 메시지를 확인합니다.

## 주요 파일 설명
- `goe_bridge.py`: 메인 실행 로직 및 데이터 처리
- `task_manager.py`: Todo26 API 통신 모듈
- `at_decryptor.exe`: 메신저 DB 복호화용 32비트 헬퍼
- `processed_ids.json`: 처리 완료된 메시지 기록 (자동 생성)

## 주의 사항
- 깃(Git) 저장소 업로드 시 `.env` 및 `.db` 파일이 포함되지 않도록 주의하세요 (이미 `.gitignore`에 정의되어 있습니다).
