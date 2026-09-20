# 4주차 완성 코드

`docs/lecture.md`, `docs/practice.md`, 발표자료의 요구사항을 반영한 완성본이다.

- **배포할 ROS 2 패키지:** `week04_pc_jetson_comm/`
- **Ubuntu 파일 배치·설치·실습 순서:** [Ubuntu 실습 가이드](UBUNTU_GUIDE.md)
- **증상별 진단·해결 방법:** [실습 트러블슈팅](docs/troubleshooting.md)
- **제공 파일별 완성 코드:** `source_code/` (배포 패키지와 동일한 내용)
- **로컬 검증:** `tests/test_week4.py`

PC와 Jetson 각각 `~/ros2_ws/src/week04_pc_jetson_comm/`에 패키지를 놓는다.
Python 파일만 복사하거나 `ros2 pkg create`를 다시 실행할 필요가 없다.
이 저장소의 `build`, `install`, Windows용 테스트 의존성은 옮기지 않고 Ubuntu에서 빌드한다.

Publisher는 기본 5 Hz, Listener는 BEST_EFFORT, Server는 최신 Topic 값을
Trigger 응답으로 반환한다. Client는 발견과 응답을 각각 최대 5초 기다린다.
Launch의 `reliability`는 Publisher와 Server 양쪽에 전달된다.

SDK의 `ServoController`에는 연결·종료 때 설정과 토크를 변경하는 동작이 있어,
완성본은 번들 `scservo_sdk`의 위치 읽기 API를 사용한다. 토크·목표 위치·phase를
변경하지 않는다. 상세 근거와 검증 범위는 가이드에 기록했다.
