import os
import json
import requests
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()
TASK_LIST_ID = os.environ.get("GOOGLE_TASK_LIST_ID", "@default")
TODO26_TOKEN = os.environ.get("TODO26_TOKEN")
TODO26_BASE_URL = os.environ.get("TODO26_URL", "https://www.todo26.site")

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
            try:
                creds.refresh(Request())
            except RefreshError as e:
                logger.warning(f"토큰 갱신 실패 (아마도 만료됨). 재인증을 진행합니다: {e}")
                if os.path.exists('token.json'):
                    os.remove('token.json')
                creds = None
        
        if not creds or not creds.valid:
            if not os.path.exists('credentials.json'):
                logger.error("'credentials.json' 파일이 없습니다. Google Cloud Console에서 다운로드하여 배치해주세요.")
                return None
            
            logger.info("웹 브라우저를 열어 새로운 Google 인증을 진행합니다...")
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

def list_tasks():
    """Google Tasks 목록을 가져옵니다."""
    service = get_service()
    if not service: return []
    try:
        results = service.tasks().list(tasklist=TASK_LIST_ID, showCompleted=True, showHidden=True).execute()
        return results.get('items', [])
    except HttpError as err:
        logger.error(f"Google Tasks 목록 가져오기 실패: {err}")
        return []

def update_task_status(task_id, completed):
    """Google Tasks의 완료 상태를 업데이트합니다."""
    service = get_service()
    if not service: return None
    try:
        # Patch를 사용하려면 'status' 필드를 'completed' 또는 'needsAction'으로 설정해야 함
        status = 'completed' if completed else 'needsAction'
        task = service.tasks().get(tasklist=TASK_LIST_ID, task=task_id).execute()
        task['status'] = status
        # 완료 처리 시 완료 시간 정보가 필요할 수 있음 (선택 사항)
        if completed:
            from datetime import datetime
            task['completed'] = datetime.utcnow().isoformat() + 'Z'
        else:
            task['completed'] = None
            
        result = service.tasks().update(tasklist=TASK_LIST_ID, task=task_id, body=task).execute()
        return result
    except HttpError as err:
        logger.error(f"Google Tasks 상태 업데이트 실패: {err}")
        return None

# --- Todo26 API Functions ---

def get_todo26_tasks():
    """Todo26 사이트에서 할 일 목록을 가져옵니다."""
    if not TODO26_TOKEN: return []
    url = f"{TODO26_BASE_URL}/api/get_todos"
    headers = {"Authorization": f"Bearer {TODO26_TOKEN}"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.ok: return resp.json()
        logger.error(f"Todo26 목록 가져오기 실패: {resp.status_code}")
        return []
    except Exception as e:
        logger.error(f"Todo26 API 연결 오류: {e}")
        return []

def create_todo26_task(content):
    """Todo26 사이트에 새로운 할 일을 등록합니다."""
    if not TODO26_TOKEN: return None
    url = f"{TODO26_BASE_URL}/api/add_todo"
    headers = {"Authorization": f"Bearer {TODO26_TOKEN}", "Content-Type": "application/json"}
    data = {"content": content}
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=10)
        if resp.ok: return resp.json()
        logger.error(f"Todo26 등록 실패: {resp.status_code}")
        return None
    except Exception as e:
        logger.error(f"Todo26 API 연결 오류: {e}")
        return None

def update_todo26_status(todo_id, completed):
    """Todo26 사이트의 할 일 완료 상태를 업데이트합니다."""
    if not TODO26_TOKEN: return None
    url = f"{TODO26_BASE_URL}/api/update_todo/{todo_id}"
    headers = {"Authorization": f"Bearer {TODO26_TOKEN}", "Content-Type": "application/json"}
    data = {"completed": completed}
    try:
        resp = requests.patch(url, headers=headers, json=data, timeout=10)
        if resp.ok: return resp.json()
        logger.error(f"Todo26 업데이트 실패: {resp.status_code}")
        return None
    except Exception as e:
        logger.error(f"Todo26 API 연결 오류: {e}")
        return None


if __name__ == "__main__":
    # 간단한 테스트
    print("Google Tasks API 연결 테스트 중...")
    s = get_service()
    if s:
        print("연결 성공!")
    else:
        print("연결 실패. credentials.json이 있는지 확인하세요.")
