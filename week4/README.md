# 4주차 완성 코드

현재 `docs/lecture.md`, `docs/practice.md`, `source_code/`의 요구사항을 반영한 완성본이다.
발표자료 20~21·34쪽의 BEST_EFFORT 기본값·Listener 변경 설명은 이전 실습 흐름이다.
이 프로젝트는 최신 Markdown 문서의 **RELIABLE 기본값·Listener 고정** 기준을 따른다.

- **배포할 ROS 2 패키지:** `week04_pc_jetson_comm/`
- **Ubuntu 파일 배치·설치·실습 순서:** [Ubuntu 실습 가이드](UBUNTU_GUIDE.md)
- **증상별 진단·해결 방법:** [실습 트러블슈팅](docs/troubleshooting.md)
- **제공 파일별 완성 코드:** `source_code/` (배포 패키지와 동일한 내용)
- **로컬 검증:** `tests/test_week4.py`

PC와 Jetson 각각 `~/ros2_ws/src/week04_pc_jetson_comm/`에 패키지를 놓는다.
Python 파일만 복사하거나 `ros2 pkg create`를 다시 실행할 필요가 없다.
이 저장소의 `build`, `install`, Windows용 테스트 의존성은 옮기지 않고 Ubuntu에서 빌드한다.

Publisher는 제공 소스 기준 기본 50 Hz, Listener는 RELIABLE, Server는 최신 Topic 값을
Trigger 응답으로 반환한다. Client는 발견과 응답을 각각 최대 5초 기다린다.
Launch의 `reliability`는 Publisher와 Server 양쪽에 전달된다.

```bash
# Jetson: 기본 통신 (reliable)
ros2 launch week04_pc_jetson_comm jetson_bringup.launch.py
# PC: 서로 다른 터미널에서 실행
ros2 run week04_pc_jetson_comm joint_state_topic_listener
ros2 run week04_pc_jetson_comm joint_state_client
```

Jetson Launch를 종료한 뒤 `reliability:=best_effort`로 다시 실행하면 PC Listener는
수신을 멈춘다. Server는 Publisher와 같은 QoS로 계속 구독하므로 Client 호출은 가능하다.
`reliability:=reliable`로 다시 실행하면 같은 Listener의 수신이 복구된다.
발행 주기는 `config/joints.yaml`의 `publish_hz`로 조정하며 실제 속도는 시리얼 읽기 시간에 좌우된다.

ROS가 없는 개발 환경에서도 저장소 최상위에서 검증할 수 있다.

```bash
python3 -m pip install -r week4/tests/requirements.txt
python3 -m unittest discover -s week4/tests -v
```

SDK의 `ServoController`에는 연결·종료 때 설정과 토크를 변경하는 동작이 있어,
완성본은 번들 `scservo_sdk`의 위치 읽기 API를 사용한다. 토크·목표 위치·phase를
변경하지 않는다. 상세 근거와 검증 범위는 가이드에 기록했다.
