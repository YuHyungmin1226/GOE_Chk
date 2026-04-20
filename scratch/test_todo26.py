import task_manager

def test_todo26():
    print("Todo26 API 테스트 중...")
    test_content = "[테스트] GOE 브릿지 연동 테스트입니다."
    result = task_manager.create_todo26_task(test_content)
    if result:
        print(f"테스트 성공! 반환값: {result}")
    else:
        print("테스트 실패. API 응답을 확인하세요.")

if __name__ == "__main__":
    test_todo26()
