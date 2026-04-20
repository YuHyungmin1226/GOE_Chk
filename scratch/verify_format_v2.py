import task_manager

def verify_format():
    print("=== Todo26 개선된 포맷 검증 시작 ===")
    
    title = "교육연구부 보고서 제출 요청"
    notes = "4/25(금)까지 2026학년도 연수 계획서를 제출해 주세요."
    content = "박혜정 선생님 안녕하세요. 교육연구부입니다. 다름이 아니라 이번 주 금요일까지 공람된 보고서를 작성하여 회신 부탁드립니다. 감사합니다."
    sender = "박혜정 교육연구부장"
    
    # 새로운 포맷 구성
    todo26_content = (
        f"[{title}]\n\n"
        f"상세내용: {notes}\n\n"
        f"원문참조:\n{content}\n\n"
        f"보낸이: {sender}"
    )
    
    print("--- 생성된 문자열 미리보기 ---")
    print(todo26_content)
    print("------------------------------")
    
    # 실제 전송 시뮬레이션
    print("전송 테스트 중...")
    result = task_manager.create_todo26_task(todo26_content)
    if result:
        print(f"테스트 성공! 반환 ID: {result.get('todo', {}).get('id')}")
    else:
        print("테스트 실패.")

if __name__ == "__main__":
    verify_format()
