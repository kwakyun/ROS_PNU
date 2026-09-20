# [4주차] PC–Jetson ROS 2 Topic·Service 분산 통신 — 수업 내용

## 0. 수업 개요

### 수업 목표

이번 수업을 마치면 다음 내용을 설명하고 수행할 수 있어야 한다.

- DDS가 같은 네트워크의 ROS 2 노드를 발견하는 원리를 설명한다.
- WSL2와 Jetson의 IP, Ping, SSH 연결을 점검한다.
- 양쪽 장비의 `ROS_DOMAIN_ID`, `ROS_LOCALHOST_ONLY`, RMW 설정을 통일한다.
- Jetson의 실제 관절 상태를 `/joint_states` Topic으로 발행하고 WSL에서 구독한다.
- QoS Reliability 설정에 따라 Topic 연결 가능 여부가 달라지는 이유를 설명한다.
- WSL에서 Jetson의 `/get_joint_state` Service를 호출해 최신 관절값을 받는다.
- ROS 2 Python package의 실행 파일, 설정 파일, launch 파일을 등록하고 빌드한다.

### 실습 완료 기준

다음 항목을 모두 확인하면 실습이 완료된 것이다.

- WSL에서 Jetson으로 Ping과 SSH 연결에 성공한다.
- Jetson의 `/joint_states`를 WSL의 직접 작성한 Listener에서 수신한다.
- `BEST_EFFORT`와 `RELIABLE`의 호환성 차이를 확인한다.
- Python Client와 ROS 2 CLI로 `/get_joint_state`를 호출한다.
- PC와 Jetson의 Domain ID가 다르면 서로 발견되지 않음을 확인한다.

이번 실습은 로봇의 관절값만 읽는다. 토크를 켜거나 목표 관절값을 전송하지 않는다.

---

## 1. 전체 통신 구조

Jetson은 로봇과 직접 연결되고, WSL은 네트워크를 통해 Jetson의 Topic과 Service에 접근한다.

```text
Jetson / PhysicAI Arm                         PC / WSL2
────────────────────────                    ─────────────────────
/dev/ttyACM0
      │
      ▼
joint_state_publisher
      │
      ├──── /joint_states ──────────────────> Topic Listener
      │
      └──── /joint_states
               │
               ▼
      joint_state_service_server <────────── Service Client
               /get_joint_state               Trigger Request
                                     <─────── success + message
```

중요한 원칙은 다음과 같다.

- 시리얼 포트 `/dev/ttyACM0`은 Publisher만 연다.
- Service Server는 시리얼 포트를 다시 열지 않고 `/joint_states`의 최신 메시지를 저장한다.
- PC의 Client는 빈 Trigger Request를 보내고, Jetson은 최신 관절값을 문자열로 반환한다.
- PC와 Jetson에는 같은 ROS 2 package를 설치하지만 실행하는 노드의 역할은 다르다.

### 주요 파일의 역할

| 파일 | 실행 위치 | 역할 |
|---|---|---|
| `hardware_interface.py` | Jetson | Feetech Servo SDK로 실제 관절 위치를 읽는다. |
| `joint_state_topic_publisher.py` | Jetson | 5 Hz로 `/joint_states`를 발행한다. |
| `joint_state_topic_listener.py` | WSL | `/joint_states`를 `BEST_EFFORT`로 구독하고 출력한다. |
| `joint_state_service_server.py` | Jetson | 최신 Topic 메시지를 저장하고 `/get_joint_state`에 응답한다. |
| `joint_state_service_client.py` | WSL | Trigger Service를 한 번 호출하고 응답을 출력한다. |
| `jetson_bringup.launch.py` | Jetson | Publisher와 Service Server를 함께 실행한다. |
| `joints.yaml` | Jetson | 관절 이름, Servo ID, 시리얼 설정을 정의한다. |

Python 파일명과 `ros2 run`에서 사용하는 실행 파일 이름은 다를 수 있다. `setup.py`의
`console_scripts`가 둘을 연결한다.

---

## 2. DDS 기반 분산 통신과 노드 발견

ROS 2는 ROS 1의 Master처럼 하나의 중앙 서버에 의존하지 않고 DDS(Data
Distribution Service)를 통해 노드가 서로를 발견한다.

```text
[Jetson Publisher / Server]
             │
             ├── DDS Discovery: 노드·Topic·Service·QoS 정보 교환
             │
[WSL Subscriber / Client]
```

- **Discovery**: 같은 네트워크와 Domain에 있는 노드가 서로의 존재와 통신 정보를 찾는 과정
- **Data communication**: Discovery 이후 Topic 데이터 또는 Service 요청·응답을 주고받는 과정
- **P2P 구조**: 중앙 Master 없이 각 노드가 직접 통신하는 구조

Ping이 성공하더라도 DDS 설정이 다르면 ROS 2 노드가 보이지 않을 수 있다. 반대로
ROS 2 설정을 맞추기 전에 Ping부터 실패한다면 먼저 IP·케이블·방화벽을 해결해야 한다.

---

## 3. PC–Jetson 네트워크 설정

### 3.1 WSL2 Mirrored Networking

Windows의 네트워크 인터페이스를 WSL2와 공유해 DDS의 UDP 통신을 사용할 수 있도록
`.wslconfig`에 다음 설정을 사용한다.

```text
[wsl2]
networkingMode=mirrored
```

설정 변경 후 `wsl --shutdown`으로 WSL을 재시작해야 한다. Windows 방화벽 설정을
변경하는 명령은 반드시 관리자 권한 PowerShell에서 실행한다.

### 3.2 DDS 관련 환경 변수

| 환경 변수 | 수업 설정 | 의미 |
|---|---:|---|
| `ROS_DOMAIN_ID` | `30` | 같은 Domain의 노드끼리 발견하도록 논리적으로 분리한다. |
| `ROS_LOCALHOST_ONLY` | `0` | 로컬 컴퓨터 밖의 Jetson과 통신할 수 있게 한다. |
| `RMW_IMPLEMENTATION` | `rmw_fastrtps_cpp` | 양쪽에서 같은 DDS 구현체를 사용한다. |

```bash
export ROS_DOMAIN_ID=30
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

환경 변수는 터미널마다 설정해야 한다. 새 터미널을 열었다면 ROS 2 환경과 workspace
overlay도 다시 `source`해야 한다.

---

## 4. Topic과 QoS Reliability

### 4.1 Publisher와 Subscriber

Publisher는 `sensor_msgs/msg/JointState` 메시지를 `/joint_states`에 발행한다.

```text
JointState
├── header.stamp : 측정 시각
├── name[]       : 관절 이름
└── position[]   : 관절 위치(rad)
```

`joint_state_topic_publisher.py`의 TODO에서는 다음 객체를 생성한다.

1. `JointState` 타입의 Publisher
2. `joint_state_qos(reliability)`가 반환한 QoS profile
3. `_publish_state`를 5 Hz, 즉 0.2초 간격으로 호출하는 Timer

`joint_state_topic_listener.py`의 TODO에서는 `JointState` 타입의 Subscription을 만들고
기존 `_on_state` callback을 연결한다.

### 4.2 QoS Reliability 호환성

| Publisher가 제공하는 Reliability | Subscriber가 요구하는 Reliability | 통신 가능 여부 |
|---|---|---|
| `BEST_EFFORT` | `BEST_EFFORT` | 가능 |
| `BEST_EFFORT` | `RELIABLE` | 불가능 |
| `RELIABLE` | `BEST_EFFORT` | 가능 |
| `RELIABLE` | `RELIABLE` | 가능 |

- `BEST_EFFORT`는 일부 데이터가 유실될 수 있지만 최신 센서값을 빠르게 전달하는 데 적합하다.
- `RELIABLE`은 유실된 데이터를 재전송해 전달 신뢰성을 높인다.
- Subscriber가 Publisher보다 높은 수준의 Reliability를 요구하면 연결되지 않는다.

이번 코드에서 Publisher의 기본값과 Listener의 설정은 모두 `BEST_EFFORT`이다.
Service Server가 `/joint_states`를 구독할 때도 launch에서 받은 `reliability` 파라미터로
Publisher와 호환되는 QoS profile을 만들어야 한다.

---

## 5. Service Client와 Server

이번 실습은 별도의 사용자 정의 `.srv` 파일을 만들지 않고 표준
`std_srvs/srv/Trigger`를 사용한다.

```text
---
bool success
string message
```

Request에는 필드가 없다. Server는 다음 순서로 동작한다.

1. `/joint_states`를 구독한다.
2. `_on_state`가 마지막으로 받은 메시지를 `self._latest`에 저장한다.
3. `/get_joint_state` 요청을 받으면 최신 메시지가 있는지 확인한다.
4. 관절값을 `name=value rad (value deg)` 문자열로 변환한다.
5. `response.success`와 `response.message`를 채워 반환한다.

`joint_state_service_server.py`의 TODO를 완성할 때는 Subscription뿐 아니라
`_on_request`가 저장된 `self._latest`를 읽도록 변수 참조도 함께 완성해야 한다.

Client는 다음 순서로 동작한다.

1. `Node`를 초기화한다.
2. `/get_joint_state`의 Trigger Client를 생성한다.
3. 제한 시간 동안 Service가 나타나기를 기다린다.
4. `Trigger.Request()`를 `call_async()`로 한 번 보낸다.
5. Future가 완료될 때까지 spin하고 성공 여부와 메시지를 출력한다.

---

## 6. Launch와 ROS 2 Python package

`ament_python` package에서 Python 파일이 존재하는 것만으로는 `ros2 run`으로 실행할 수
없다. `setup.py`의 `console_scripts`에 실행 파일 이름과 Python module의 `main` 함수를
연결해야 한다.

```text
ros2 run에서 쓰는 이름       Python module
───────────────────────────  ────────────────────────────────
joint_state_publisher        joint_state_topic_publisher.py
joint_state_topic_listener   joint_state_topic_listener.py
joint_state_server           joint_state_service_server.py
joint_state_client           joint_state_service_client.py
```

`jetson_bringup.launch.py`는 다음 두 실행 파일을 시작한다.

- `joint_state_publisher`
- `joint_state_server`

두 노드에는 같은 `reliability` launch argument를 전달하여 Publisher와 Server 내부
Subscriber의 QoS가 일치하도록 한다.

`config/*.yaml`과 `launch/*.launch.py`도 `setup.py`의 `data_files`에 등록해야 설치 공간에서
찾을 수 있다. `hardware_interface.py`가 사용하는 PyYAML은 `package.xml`과
`setup.py`에 실행 의존성으로 추가한다.

---

## 7. 진단 명령

| 목적 | 명령 |
|---|---|
| 현재 IP 확인 | `hostname -I` |
| ROS 환경 확인 | `printenv \| grep -E 'ROS_DOMAIN_ID\|ROS_LOCALHOST_ONLY\|RMW_IMPLEMENTATION'` |
| 노드 발견 확인 | `ros2 node list` |
| Topic 연결·QoS 확인 | `ros2 topic info --verbose /joint_states` |
| Topic 주기 확인 | `ros2 topic hz /joint_states` |
| Service 발견 확인 | `ros2 service list` |
| Service 타입 확인 | `ros2 service type /get_joint_state` |
| Trigger 정의 확인 | `ros2 interface show std_srvs/srv/Trigger` |
| Discovery 정보 초기화 | `ros2 daemon stop` 후 `ros2 daemon start` |
| ROS node 강제종료 | `killall -9 python3` |

---

## 8. 안전 및 종료 원칙

- 제조사 Bringup이나 이전 실습 노드가 `/dev/ttyACM0`을 사용 중이면 먼저 정상 종료한다.
- 터미널 창을 강제로 닫지 말고 실행 중인 노드에서 `Ctrl+C`를 사용한다.
- `killall -9 python3`은 다른 Python 프로그램도 모두 종료하므로 일반적인 종료 방법으로 사용하지 않는다.
- 실습 종료 후 `ros2 node list --no-daemon`으로 남은 노드를 확인한다.
- 이번 주차에는 토크 활성화, 목표 위치 전송, Servo 쓰기 명령을 사용하지 않는다.
