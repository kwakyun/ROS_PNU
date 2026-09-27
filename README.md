# ROS_PNU · ROS 2 통신 학습 기록

ROS 2의 Topic·Service·QoS를 학습하고 PC–Jetson 통신 흐름을 실습하는 수업 기반 저장소입니다.
완성 서비스보다는 제공 자료, 실습 코드, 문제 해결 방법을 함께 읽는 학습 기록입니다.

## 살펴볼 내용

- [3주차 자료](week3/): Publisher·Subscriber 및 Service 기초
- [4주차 안내](week4/README.md): PC–Jetson 구성, 실행 명령, QoS 조건
- [배포용 패키지](week4/week04_pc_jetson_comm/): ROS 2 노드와 launch 설정
- [Ubuntu 실행 가이드](week4/UBUNTU_GUIDE.md)
- [트러블슈팅](week4/docs/troubleshooting.md)
- [검증 코드](week4/tests/test_week4.py)

기술: Python, ROS 2, Ubuntu, Jetson. 제공 코드와 실습 결과가 함께 있으므로 전체를 독자 구현한 로봇 시스템으로 보지 않습니다.

## 시작하기

~~~bash
git clone https://github.com/kwakyun/ROS_PNU.git
cd ROS_PNU
python3 -m pip install -r week4/tests/requirements.txt
python3 -m unittest discover -s week4/tests -v
~~~

위 명령은 ROS가 없는 환경에서 수행하는 코드 검증입니다. 실제 장치 통신 검증과는 구분됩니다.
장치 실습은 Ubuntu 가이드에 따라 패키지를 워크스페이스에 배치하고 빌드한 뒤 진행합니다.

~~~bash
ros2 launch week04_pc_jetson_comm jetson_bringup.launch.py
ros2 run week04_pc_jetson_comm joint_state_topic_listener
ros2 run week04_pc_jetson_comm joint_state_client
~~~

각 명령은 가이드의 PC·Jetson 구분에 맞게 별도 터미널에서 실행합니다.

## 관찰할 점과 현재 범위

- Publisher와 Listener의 QoS가 맞지 않을 때 수신이 어떻게 달라지는지
- 최신 Topic 값을 Service 응답으로 전달하는 흐름
- 장치 연결·응답 시간 제한과 통신 실패를 구분하는 방법
- 이번 문서 정리에서는 장치 연결과 하드웨어 동작을 검증하지 않았습니다.

[AI 활용 기록](AI_NOTES.md) · [변경 기록](CHANGELOG.md) · [작업 방법](CONTRIBUTING.md)
