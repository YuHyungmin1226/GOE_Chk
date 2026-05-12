import os
import sqlite3
import glob
import re
import json
import time
import datetime
import logging
import contextlib
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 내부 모듈
import task_manager
from sync_manager import SyncManager
import subprocess
import shutil

# --- 로깅 설정 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("bridge.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- 환경 변수 설정 ---
load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

PROCESSED_IDS_FILE = "processed_ids.json"

# 최신 SDK Client 초기화 (Gemini 1.5 Flash 최적화)
client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)

# --- AtMessenger 복호화 설정 ---
# 64비트 파이썬에서 32비트 메신저 DLL을 직접 쓸 수 없으므로 32비트 C# 헬퍼를 사용합니다.
AT_DECRYPTOR_EXE = "at_decryptor.exe"
MAIN_DB_PATH = os.path.join(os.environ['LOCALAPPDATA'], 'AtMessenger', '@Talk.db')
DECRYPTED_SNAP_PATH = "AtMessenger_Latest.db"
DECRYPTION_KEY = os.environ.get("DECRYPTION_KEY", "49100hsy")

def load_processed_ids():
    if os.path.exists(PROCESSED_IDS_FILE):
        try:
            with open(PROCESSED_IDS_FILE, 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_processed_ids(processed_ids):
    with open(PROCESSED_IDS_FILE, 'w') as f:
        json.dump(list(processed_ids), f)

def sync_database():
    """at_decryptor.exe를 호출하여 실시간 @Talk.db를 복호화 스냅샷으로 생성합니다."""
    if not os.path.exists(MAIN_DB_PATH):
        print(f"   [오류] 메신저 원본 DB를 찾을 수 없습니다: {MAIN_DB_PATH}")
        return False
        
    if not os.path.exists(AT_DECRYPTOR_EXE):
        print(f"   [오류] 복호화 헬퍼({AT_DECRYPTOR_EXE})가 없습니다. 빌드가 필요합니다.")
        return False

    try:
        # 1. 원본 DB 카피 (WAL 모드 대응을 위해 사본 제작)
        temp_copy = "Talk_temp.db"
        shutil.copy2(MAIN_DB_PATH, temp_copy)
        # WAL 파일이 있다면 함께 복사 (SQLite 정합성 유지)
        if os.path.exists(MAIN_DB_PATH + "-wal"):
            shutil.copy2(MAIN_DB_PATH + "-wal", temp_copy + "-wal")
            
        # 2. 32비트 복호화 헬퍼 실행
        result = subprocess.run(
            [AT_DECRYPTOR_EXE, temp_copy, DECRYPTED_SNAP_PATH, DECRYPTION_KEY],
            capture_output=True, text=True, timeout=15
        )
        
        # 임시 카피본 삭제
        if os.path.exists(temp_copy): os.remove(temp_copy)
        if os.path.exists(temp_copy + "-wal"): os.remove(temp_copy + "-wal")

        if "SUCCESS" in result.stdout:
            return True
        else:
            logger.warning(f"직접 복호화 실패: {result.stdout.strip()}")
            return False
    except Exception as e:
        logger.error(f"동기화 중 예외 발생: {e}")
        return False

def get_latest_db():
    # 1. 먼저 직접 복호화(실시간) 시도
    if sync_database():
        return DECRYPTED_SNAP_PATH
        
    # 2. 실패 시 기존의 Temp 폴더 내 복호화 파일 검색 (Fallback)
    temp_dir = os.path.join(os.environ['LOCALAPPDATA'], 'Temp')
    db_files = glob.glob(os.path.join(temp_dir, 'goe_dec_*.db'))
    if not db_files: return None
    
    valid_files = []
    for f in db_files:
        try:
            mtime = os.path.getmtime(f)
            valid_files.append((mtime, f))
        except OSError:
            continue
    if not valid_files: return None
    valid_files.sort(key=lambda x: x[0], reverse=True)
    
    latest_db = valid_files[0][1]
    logger.info(f"메신저가 생성한 이전 복호화 파일을 사용합니다: {os.path.basename(latest_db)}")
    return latest_db

def decode_rtf_korean(text):
    """RTF 내의 \'b8\'bc 형태의 16진수 코드를 한글(CP949)로 변환하고 태스크 정보를 정리합니다."""
    if not text: return ""
    
    # {RTF} 태그가 있으면 그 이전의 일반 텍스트 프리뷰만 사용 (중복 및 지저분한 태그 문제 해결)
    if "{RTF}" in text:
        return text.split("{RTF}", 1)[0].strip()
    
    # {RTF} 태그가 없는 경우에만 하단 RTF 디코딩 로직 수행
    pattern = re.compile(r"(\\\' [a-fA-F0-9]{2})+".replace(" ", ""))
    
    def decode_match(m):
        hex_data = m.group(0).replace("\\'", "")
        try:
            return bytes.fromhex(hex_data).decode('cp949', errors='ignore')
        except:
            return m.group(0)
    
    try:
        decoded_text = pattern.sub(decode_match, text)
        decoded_text = re.sub(r'{\\.*?}', '', decoded_text)
        decoded_text = re.sub(r'\\[a-z0-9]+', '', decoded_text)
        decoded_text = decoded_text.replace('\\', '').strip()
        return decoded_text
    except Exception as e:
        print(f"디코딩 오류: {e}")
        return text

def get_new_messages(processed_ids):
    db_path = get_latest_db()
    if not db_path: 
        logger.warning("DB 파일을 찾을 수 없습니다. 메신저가 실행 중인지 확인하세요.")
        return []
        
    messages = []
    try:
        with contextlib.closing(sqlite3.connect(db_path)) as conn:
            conn.text_factory = bytes
            cursor = conn.cursor()
            # 최근 7일간의 모든 메시지를 소급 분석하여 누락된 업무를 보완합니다.
            lookback_date = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y%m%d000000')
            cursor.execute("SELECT sMsgId, sSenderName, sContent, sDate, sReceivers, sOwnerId FROM tblMessage WHERE cIsSend = 'N' AND sDate >= ? ORDER BY sDate DESC LIMIT 500;", (lookback_date,))
            
            for row in cursor.fetchall():
                msg_id = row[0].decode('utf-8', errors='ignore') if isinstance(row[0], bytes) else row[0]
                if msg_id in processed_ids:
                    continue
                    
                sender = row[1].decode('utf-8', errors='ignore') if isinstance(row[1], bytes) else row[1]
                content_raw = row[2].decode('utf-8', errors='ignore') if isinstance(row[2], bytes) else row[2]
                content = decode_rtf_korean(content_raw)
                date_str = row[3].decode('utf-8', errors='ignore') if isinstance(row[3], bytes) else row[3]
                
                # 수신인 분석 (1명인 경우 체크)
                receivers_raw = row[4].decode('utf-8', errors='ignore') if isinstance(row[4], bytes) else row[4]
                is_direct = False
                if receivers_raw:
                    # 수신자 목록이 '/'로 구분되어 있음. '/'가 없으면 수신자가 1명인 것으로 간주
                    if '/' not in receivers_raw.strip('/'):
                        is_direct = True
                
                if content:
                    messages.append({
                        "id": msg_id, 
                        "sender": sender, 
                        "content": content, 
                        "date": date_str,
                        "is_direct": is_direct
                    })
    except Exception as e:
        logger.error(f"DB 읽기 오류: {e}")
        
    return messages

def analyze_tasks_batch(messages):
    """여러 메시지를 한 번에 분석하여 할당량을 절약합니다."""
    global client
    if not client: 
        print("Gemini 클라이언트가 초기화되지 않았습니다. API 키를 확인하세요.")
        return []

    if not messages:
        return []

    # 메시지 리스트를 텍스트로 구성
    messages_input = ""
    for idx, msg in enumerate(messages):
        direct_info = "(1:1 쪽지)" if msg.get("is_direct") else ""
        messages_input += f"--- MESSAGE #{idx} (ID: {msg['id']}) {direct_info} ---\n{msg['content']}\n\n"

    prompt = (
        "다음은 교사 간의 메신저 쪽지 리스트야. 각 메시지에서 수행해야 할 '업무'나 '일정' 정보가 있다면 추출해줘.\n"
        "반드시 아래의 JSON 배열 형식으로만 응답해. 업무가 없는 메시지도 반드시 포함해서 'is_task': false로 표시해줘.\n"
        "형식: [{\"id\": \"메시지ID\", \"is_task\": true, \"title\": \"업무 제목\", \"notes\": \"상세 내용\", \"due_date\": \"YYYY-MM-DD\"}, ...]\n\n"
        "마감일(due_date)을 알 수 없다면 null로 설정해.\n"
        f"분석할 메시지들:\n{messages_input}"
    )
    
    for i in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-flash-latest',
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return json.loads(response.text)
        except Exception as e:
            if "429" in str(e): return [{"error": "quota_exceeded"}]
            if i < 2: time.sleep(5)
            else: logger.error(f"Gemini 분석 오류: {e}")
    return []

def process_cycle():
    logger.info("동기화 및 새 메시지 확인 중...")
    sync_mgr = SyncManager()
    
    # 1. 플랫폼 간 동기화 먼저 수행
    try:
        sync_mgr.sync()
    except Exception as e:
        logger.error(f"동기화 중 오류 발생: {e}")

    # 2. 새 메시지 확인 및 등록
    processed_ids = load_processed_ids()
    new_messages = get_new_messages(processed_ids)
    
    if not new_messages:
        return
        
    new_count = len(new_messages)
    task_count = 0
    BATCH_SIZE = 20
    total_batches = (new_count + BATCH_SIZE - 1) // BATCH_SIZE
    
    for i in range(0, new_count, BATCH_SIZE):
        batch = new_messages[i:i + BATCH_SIZE]
        current_batch_num = (i // BATCH_SIZE) + 1
        logger.info(f"묶음 분석 중... ({current_batch_num}/{total_batches} 그룹)")
        
        batch_results = analyze_tasks_batch(batch)
        if batch_results and isinstance(batch_results[0], dict) and batch_results[0].get("error") == "quota_exceeded":
            logger.warning("API 할당량이 소진되어 이번 주기는 여기서 종료합니다.")
            break

        for res in batch_results:
            msg_id = res.get("id")
            if not msg_id: continue
            orig_msg = next((m for m in batch if m['id'] == msg_id), None)
            if not orig_msg: continue

            if res.get("is_task"):
                logger.info(f"업무 감지: {res['title']} (보낸이: {orig_msg['sender']})")
                
                # Google Tasks 등록 (개선된 포맷: 본문에 원문 포함)
                notes = (
                    f"상세내용: {res.get('notes', '')}\n\n"
                    f"원문참조:\n{orig_msg['content']}\n\n"
                    f"보낸이: {orig_msg['sender']}"
                )
                due = f"{res['due_date']}T09:00:00Z" if res.get('due_date') else None
                
                reg_result = task_manager.create_task(res['title'], notes, due)
                if reg_result:
                    logger.info("Google Tasks에 등록되었습니다.")
                    g_id = reg_result.get('id')
                    
                    # Todo26에도 동시 등록 및 매핑 저장
                    todo_res = task_manager.create_todo26_task(res['title'])
                    if todo_res and 'id' in todo_res:
                        sync_mgr.add_mapping(g_id, todo_res['id'])
                        logger.info(f"Todo26에도 등록 및 매핑 완료 (ID: {todo_res['id']})")
                    
                    task_count += 1
            
            processed_ids.add(msg_id)
            
        if current_batch_num < total_batches:
            time.sleep(10) # 묶음 사이 딜레이 (RPM 보호)
    
    save_processed_ids(processed_ids)
    logger.info(f"처리 완료: 새 메시지 {new_count}개 확인, {task_count}개의 업무 등록됨")

def main():
    logger.info("=== GOE Messenger to Google Tasks Auto-Bridge (Gemini 1.5 Flash) ===")
    print("프로그램이 시작되었습니다. 종료하려면 Ctrl+C를 누르세요. 진행 로그는 bridge.log에 저장됩니다.")
    
    try:
        while True:
            try:
                process_cycle()
            except Exception as e:
                logger.error(f"루프 실행 중 예기치 못한 오류 발생: {e}")
            
            logger.info("다음 확인까지 5분간 대기합니다...")
            time.sleep(300)
    except KeyboardInterrupt:
        logger.info("프로그램을 종료합니다.")
        print("프로그램이 종료되었습니다.")

if __name__ == "__main__":
    main()
