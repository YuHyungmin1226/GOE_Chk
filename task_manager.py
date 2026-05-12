import os
import requests
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()
TODO26_TOKEN = os.environ.get("TODO26_TOKEN")
TODO26_BASE_URL = os.environ.get("TODO26_URL", "https://www.todo26.site")

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
    if not TODO26_TOKEN: 
        logger.error("TODO26_TOKEN이 설정되지 않았습니다.")
        return None
    url = f"{TODO26_BASE_URL}/api/add_todo"
    headers = {"Authorization": f"Bearer {TODO26_TOKEN}", "Content-Type": "application/json"}
    data = {"content": content}
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=10)
        if resp.ok: return resp.json()
        logger.error(f"Todo26 등록 실패: {resp.status_code} - {resp.text}")
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
    print("Todo26 API 연결 테스트 중...")
    tasks = get_todo26_tasks()
    if isinstance(tasks, (list, dict)):
        print(f"연결 성공! 현재 할 일 개수: {len(tasks)}")
    else:
        print("연결 실패. TODO26_TOKEN을 확인하세요.")
