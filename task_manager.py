import os
import json
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()
TASK_LIST_ID = os.environ.get("GOOGLE_TASK_LIST_ID", "@default")

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/tasks']

def get_service():
    """Google Tasks API 서비스를 반환합니다."""
    creds = None
    # token.json은 사용자의 액세스 및 리프레시 토큰을 저장합니다.
    # 첫 번째 인증 후 자동으로 생성됩니다.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # 유효한 자격 증명이 없으면 로그인을 요청합니다.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                logger.error("'credentials.json' 파일이 없습니다. Google Cloud Console에서 다운로드하여 배치해주세요.")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 다음 실행을 위해 자격 증명을 저장합니다.
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('tasks', 'v1', credentials=creds)
        return service
    except HttpError as err:
        logger.error(f"Google Tasks API 연결 오류: {err}")
        return None

def create_task(title, notes=None, due=None):
    """새로운 할 일을 등록합니다.
    due: ISO 8601 형식 (예: '2026-04-20T00:00:00Z')
    """
    service = get_service()
    if not service:
        return None

    task_body = {
        'title': title,
        'notes': notes if notes else 'GOE 메신저에서 자동 추출됨'
    }
    if due:
        task_body['due'] = due

    try:
        result = service.tasks().insert(tasklist=TASK_LIST_ID, body=task_body).execute()
        return result
    except HttpError as err:
        logger.error(f"Task 생성 실패: {err}")
        return None


if __name__ == "__main__":
    # 간단한 테스트
    print("Google Tasks API 연결 테스트 중...")
    s = get_service()
    if s:
        print("연결 성공!")
    else:
        print("연결 실패. credentials.json이 있는지 확인하세요.")
