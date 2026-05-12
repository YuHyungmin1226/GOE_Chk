import os
import json
import logging
import task_manager

logger = logging.getLogger(__name__)

MAPPING_FILE = "task_mapping.json"

class SyncManager:
    def __init__(self):
        self.mapping = self._load_mapping()

    def _load_mapping(self):
        if os.path.exists(MAPPING_FILE):
            try:
                with open(MAPPING_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"매핑 파일 로드 오류: {e}")
                return {}
        return {}

    def _save_mapping(self):
        try:
            with open(MAPPING_FILE, 'w') as f:
                json.dump(self.mapping, f, indent=4)
        except Exception as e:
            logger.error(f"매핑 파일 저장 오류: {e}")

    def add_mapping(self, google_id, todo26_id):
        self.mapping[google_id] = str(todo26_id)
        self._save_mapping()

    def sync(self):
        logger.info("동기화 시작...")
        
        # 1. 양쪽 플랫폼에서 데이터 가져오기
        google_tasks = task_manager.list_tasks()
        todo26_tasks = task_manager.get_todo26_tasks()
        
        if not google_tasks and not todo26_tasks:
            logger.info("동기화할 데이터가 없습니다.")
            return

        # 검색 최적화를 위해 Todo26 데이터를 딕셔너리로 변환 (ID 기준)
        # Todo26 API 응답 형식을 가정: [{"id": 123, "content": "...", "completed": False}, ...]
        todo26_dict = {str(t['id']): t for t in todo26_tasks}
        
        # 2. Google Tasks 기준으로 순회
        for g_task in google_tasks:
            g_id = g_task['id']
            g_completed = (g_task['status'] == 'completed')
            g_title = g_task['title']
            
            if g_id not in self.mapping:
                # 2-A. Google에는 있지만 매핑에 없는 경우 -> 제목으로 기존 Todo26 항목 찾기
                logger.info(f"매핑되지 않은 Google Task 발견: {g_title}")
                
                # 이미 매핑된 Todo26 ID 목록 (중복 매핑 방지)
                mapped_todo_ids = set(self.mapping.values())
                
                # 제목이 일치하고 아직 매핑되지 않은 Todo26 항목 검색
                match = next((t for t in todo26_tasks if t['content'] == g_title and str(t['id']) not in mapped_todo_ids), None)
                
                if match:
                    logger.info(f"기존 Todo26 항목과 매칭됨: {match['id']}")
                    self.mapping[g_id] = str(match['id'])
                    # 상태 동기화 (Google 우선 혹은 완료 우선)
                    if g_completed != match.get('completed', False):
                        if g_completed: task_manager.update_todo26_status(match['id'], True)
                        else: task_manager.update_task_status(g_id, True)
                else:
                    # 일치하는 항목이 없으면 새로 생성
                    logger.info(f"일치하는 항목 없음. Todo26에 새로 등록합니다.")
                    new_todo = task_manager.create_todo26_task(g_title)
                    if new_todo and 'id' in new_todo:
                        self.mapping[g_id] = str(new_todo['id'])
                        if g_completed:
                            task_manager.update_todo26_status(new_todo['id'], True)
            else:
                # 2-B. 매핑에 있는 경우 -> 상태 동기화
                t_id = self.mapping[g_id]
                if t_id in todo26_dict:
                    t_task = todo26_dict[t_id]
                    t_completed = t_task.get('completed', False)
                    
                    if g_completed != t_completed:
                        # 상태가 다른 경우 (한쪽에서 체크함)
                        # 원칙: 더 최근에 바뀐 쪽을 따르는 게 좋지만, 단순 구현을 위해 '완료'된 쪽을 우선하거나
                        # 특정 방향을 우선함. 여기서는 '완료' 상태가 된 것을 우선 전파함.
                        if g_completed:
                            logger.info(f"상태 동기화: Google(완료) -> Todo26({t_id})")
                            task_manager.update_todo26_status(t_id, True)
                        elif t_completed:
                            logger.info(f"상태 동기화: Todo26(완료) -> Google({g_id})")
                            task_manager.update_task_status(g_id, True)
                        else:
                            # 둘 다 미완료로 돌아온 경우 (체크 해제)
                            # 체크 해제도 동기화
                            logger.info(f"상태 동기화: 체크 해제 전파")
                            # 일단 Google -> Todo26 방향으로 전파 (임의 선택)
                            task_manager.update_todo26_status(t_id, False)

        # 3. Todo26 기준으로 순회 (매핑에 없는 새로운 항목이 있는지 확인)
        # *참고: Todo26에서 새로 만든 것을 Google로 보내는 기능 (양방향)
        for t_id, t_task in todo26_dict.items():
            # 매핑 값들 중에 t_id가 있는지 확인
            if t_id not in self.mapping.values():
                logger.info(f"새로운 Todo26 항목 발견: {t_task['content']}")
                new_g = task_manager.create_task(t_task['content'])
                if new_g and 'id' in new_g:
                    self.mapping[new_g['id']] = str(t_id)
                    logger.info(f"Google Tasks에 등록됨 (ID: {new_g['id']})")
                    if t_task.get('completed'):
                        task_manager.update_task_status(new_g['id'], True)

        self._save_mapping()
        logger.info("동기화 완료.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync = SyncManager()
    sync.sync()
