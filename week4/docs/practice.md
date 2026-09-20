# [4주차] PC–Jetson ROS 2 Topic·Service 분산 통신 — 실습 안내서

> `lecture.md`를 먼저 읽고 아래 실습을 순서대로 수행한다. 명령의 `<Jetson_IP>`는
> 실제 장비의 IP 주소로 바꾼다.

## 0. 실습 전 확인

- PC와 Jetson을 같은 유선 네트워크에 연결한다.
- 제조사 Bringup과 이전 주차 ROS 2 노드를 종료한다.
- `/dev/ttyACM0`은 이번 실습의 Publisher 한 개만 사용한다.
- 이번 실습에서는 관절값만 읽으며 토크나 목표 관절값을 변경하지 않는다.

---

## 1. WSL2와 Jetson 네트워크 준비

### 1-1. WSL2 Mirrored Networking 설정

Windows PowerShell에서 `.wslconfig`를 연다.

```powershell
notepad $env:USERPROFILE\.wslconfig
```

다음 내용을 저장한다.

```text
[wsl2]
networkingMode=mirrored
```

관리자 권한 PowerShell에서 WSL을 재시작하고 inbound 통신을 허용한다.

```powershell
wsl --shutdown
Set-NetFirewallHyperVVMSetting -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -DefaultInboundAction Allow
```

### 1-2. IP와 Ping 확인

Jetson에서 IP를 확인한다.

```bash
hostname -I
```

WSL에서 Jetson으로 Ping이 되는지 확인한다.

```bash
ping -c 3 <Jetson_IP>
```

Ping이 실패하면 ROS 2 실습을 진행하기 전에 케이블, IP 대역, Windows 방화벽을 먼저
확인한다.

---

## 2. Package 생성과 파일 구성

### 2-1. WSL에서 기본 package 생성

ROS 2 workspace로 사용할 디렉터리를 자유롭게 정하고, 그 workspace의 최상위에서 다음
명령을 실행한다.

```bash
source /opt/ros/humble/setup.bash

ros2 pkg create week04_pc_jetson_comm \
  --build-type ament_python \
  --dependencies \
    ament_index_python \
    launch \
    launch_ros \
    rclpy \
    sensor_msgs \
    std_srvs
```

이미 `week04_pc_jetson_comm` 디렉터리가 있다면 다시 생성하지 않는다.

### 2-2. 최종 파일 구조

제공 파일을 배치한 뒤 package가 다음 구조인지 확인한다.

```text
week04_pc_jetson_comm/
├── config/
│   └── joints.yaml
├── launch/
│   └── jetson_bringup.launch.py
├── resource/
│   └── week04_pc_jetson_comm
├── week04_pc_jetson_comm/
│   ├── __init__.py
│   ├── hardware_interface.py
│   ├── joint_state_topic_publisher.py
│   ├── joint_state_topic_listener.py
│   ├── joint_state_service_server.py
│   └── joint_state_service_client.py
├── package.xml
├── setup.cfg
└── setup.py
```

### 2-3. `setup.py` 수정

상단에 다음 import를 추가한다.

```python
from glob import glob
import os
```

`data_files`에 config와 launch 설치 항목을 추가한다.

```python
(os.path.join("share", package_name, "config"), glob("config/*.yaml")),
(os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
```

`console_scripts`에 각 Node의 진입점을 등록한다.

PyYAML을 설치 의존성에 추가한다.

```python
install_requires=["setuptools", "PyYAML"],
```

### 2-4. `package.xml` 수정

다음 실행 의존성을 추가한다.

```xml
<exec_depend>python3-yaml</exec_depend>
```

---

## 3. Python 코드와 Launch 완성

### 3-1. JointState Publisher

`joint_state_topic_publisher.py`의 TODO를 완성한다.

- `JointState` 타입의 `/joint_states` Publisher 생성
- `joint_state_qos(reliability)`의 반환값을 QoS로 사용
- `_publish_state`를 호출하는 Timer 생성
- Publisher 객체를 `self._publisher`에 저장

### 3-2. Topic Listener

`joint_state_topic_listener.py`의 TODO를 완성한다.

- `JointState` 타입으로 `/joint_states` 구독
- 기존 `_on_state` callback 연결
- QoS depth를 `10`으로 설정
- Reliability를 `QoSReliabilityPolicy.BEST_EFFORT`로 설정

### 3-3. Service Server

`joint_state_service_server.py`의 TODO와 Service callback을 완성한다.

- `reliability` 파라미터를 선언하고 기본값을 `best_effort`로 설정
- `/joint_states`를 `JointState` 타입으로 구독
- 기존 `_on_state` callback 연결
- 전달받은 reliability에 맞는 QoS profile 생성
- `_on_request`에서 `self._latest`에 저장된 최신 메시지 사용
- 최신 메시지가 없으면 `success=False` 반환
- 최신 메시지가 있으면 `format_joint_state()`의 결과와 `success=True` 반환

Service 이름과 타입은 다음과 같다.

```text
/get_joint_state
std_srvs/srv/Trigger
```

### 3-4. Service Client

3주차 코드를 참고하여 `joint_state_service_client.py`의
`JointStateServiceClient` 클래스를 완성한다.

- 노드 이름: `joint_state_service_client`
- Service 타입: `Trigger`
- Service 이름: `/get_joint_state`
- Service가 나타날 때까지 제한 시간을 두고 대기
- `request_once()`에서 `Trigger.Request()`를 비동기로 한 번 호출
- 응답 성공 여부와 메시지를 출력하고 `True` 또는 `False` 반환

### 3-5. Jetson Launch

`jetson_bringup.launch.py`의 TODO에 Service Server `Node`를 추가한다.

- package: `week04_pc_jetson_comm`
- executable: `joint_state_server`
- node name: `joint_state_service_server`
- output: `screen`
- `reliability` launch argument를 parameter로 전달

Launch에는 `joint_state_publisher`와 `joint_state_server`가 모두 포함되어야 한다.

---

## 4. 양쪽 장비에서 빌드 및 환경 설정

완성한 package를 PC와 Jetson에서 각각 선택한 ROS 2 workspace에 동일하게 준비한다.
아래 명령은 각 장비에서 **package가 들어 있는 workspace 최상위로 이동한 상태에서 실행한다.**

### 4-1. Jetson

```bash
source ~/ros2_base/install/setup.bash
colcon build --symlink-install --packages-select week04_pc_jetson_comm
source install/setup.bash

export ROS_DOMAIN_ID=30
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

### 4-2. WSL

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select week04_pc_jetson_comm
source install/setup.bash

export ROS_DOMAIN_ID=30
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ros2 daemon start
```

새 터미널을 열면 해당 장비의 ROS 2 환경, workspace overlay, DDS 환경 변수를 다시
설정해야 한다.

---

## 5. 기본 통신 점검

### 5-1. Jetson Bringup 실행

Jetson에서 Publisher와 Service Server를 함께 실행한다.

```bash
ros2 launch week04_pc_jetson_comm jetson_bringup.launch.py \
  reliability:=best_effort
```

### 5-2. WSL에서 노드와 Topic 확인

```bash
ros2 node list
ros2 topic list
```

Jetson에서 실행 중인 다음 노드와 `/joint_states`가 보여야 한다.

```text
/joint_state_publisher
/joint_state_service_server
```

직접 작성한 Listener로 관절값을 확인한다.

```bash
ros2 run week04_pc_jetson_comm joint_state_topic_listener
```

### 5-3. WSL에서 Service 확인

```bash
ros2 service list
ros2 service type /get_joint_state
ros2 service info /get_joint_state
```

`/get_joint_state`의 타입이 `std_srvs/srv/Trigger`인지 확인한다.

Python Client로 Service를 호출한다.

```bash
ros2 run week04_pc_jetson_comm joint_state_client
```

---

## 6. Reliability 변경 확인

WSL의 구독 명령은 바꾸지 않고, Jetson의 bringup을 서로 다른 reliability 옵션으로
종료·재실행하면서 수신 결과가 달라지는지 확인한다.

### 6-1. WSL에서 Reliable Subscriber 실행

WSL에서 다음 명령을 실행한 상태로 둔다.

```bash
ros2 topic echo /joint_states --qos-reliability reliable
```

### 6-2. Jetson Bringup을 Best Effort로 실행

Jetson에서 기존 bringup을 `Ctrl+C`로 종료한 뒤 다음 옵션으로 다시 실행한다.

```bash
ros2 launch week04_pc_jetson_comm jetson_bringup.launch.py \
  reliability:=best_effort
```

Publisher가 `BEST_EFFORT`인데 WSL Subscriber가 `RELIABLE`을 요구하므로 WSL에 관절값이
출력되지 않아야 한다.

### 6-3. Jetson Bringup을 Reliable로 변경

Jetson bringup을 다시 `Ctrl+C`로 종료하고 reliability 옵션만 변경하여 실행한다.

```bash
ros2 launch week04_pc_jetson_comm jetson_bringup.launch.py \
  reliability:=reliable
```

WSL의 Subscriber는 종료하거나 옵션을 바꾸지 않는다. 같은 WSL 터미널에 관절값이
출력되기 시작해야 한다. Launch가 같은 reliability 값을 Publisher와 Service Server의
Subscriber에 전달하므로 `/get_joint_state`도 계속 정상 동작해야 한다.

---

## 7. Domain ID 변경 확인

Jetson은 Domain 30으로 실행한 상태를 유지한다. WSL에서 기존 daemon을 종료하고
`ROS_DOMAIN_ID`를 31로 변경한 뒤 daemon을 다시 시작한다.

```bash
ros2 daemon stop
export ROS_DOMAIN_ID=31
ros2 daemon start

ros2 node list
ros2 topic list
ros2 service list
```

Jetson의 노드, `/joint_states`, `/get_joint_state`가 보이지 않아야 한다.

WSL의 기존 daemon을 종료하고 `ROS_DOMAIN_ID`를 다시 30으로 복구한 뒤 daemon을
시작한다.

```bash
ros2 daemon stop
export ROS_DOMAIN_ID=30
ros2 daemon start

ros2 node list
ros2 topic list
ros2 service list
```

Jetson의 Publisher, Service Server, Topic, Service가 다시 보여야 한다.
