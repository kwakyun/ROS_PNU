# Ubuntu 실습 환경 배치 및 실행

이 가이드는 **현재 Windows 개발 컴퓨터가 아닌 실습용 Ubuntu PC와 Jetson**을 대상으로 한다.
자료 기준은 ROS 2 Humble이며, 두 장비에서 같은 ROS 2 배포판을 사용하는 것을 전제로 한다.
Ubuntu PC에서는 자료의 “WSL” 명령을 Ubuntu 터미널에서 실행한다.
Windows `.wslconfig`와 Hyper-V 방화벽 설정은 순수 Ubuntu PC에는 적용하지 않는다.
실습 PC가 Windows + WSL2인 경우에만 `docs/practice.md`의 WSL2 준비 절차를 추가한다.

## 1. 어떤 파일을 어디에 놓는가

두 장비 모두 아래 구조로 배치한다. `~`는 **해당 장비에 로그인한 사용자**의 홈이다.
예를 들어 PC 사용자가 `student`라면 `/home/student/ros2_ws`, Jetson 사용자가
`jetson`이라면 `/home/jetson/ros2_ws`가 된다. 두 사용자 이름이 같을 필요는 없다.

```text
~/ros2_ws/                                  ← colcon build 실행 위치
├── src/
│   └── week04_pc_jetson_comm/               ← 이 저장소의 완성 패키지를 통째로 복사
│       ├── config/
│       │   └── joints.yaml
│       ├── launch/
│       │   └── jetson_bringup.launch.py
│       ├── resource/
│       │   └── week04_pc_jetson_comm         ← 내용이 없는 ament 식별 파일도 필요
│       ├── week04_pc_jetson_comm/           ← 실제 Python 모듈
│       │   ├── __init__.py
│       │   ├── hardware_interface.py
│       │   ├── qos.py
│       │   ├── joint_state_topic_publisher.py
│       │   ├── joint_state_topic_listener.py
│       │   ├── joint_state_service_server.py
│       │   └── joint_state_service_client.py
│       ├── package.xml
│       ├── setup.cfg
│       └── setup.py
├── build/                                  ← Ubuntu에서 빌드하면 자동 생성
├── install/                                ← 빌드 후 source할 overlay
└── log/                                    ← 빌드 로그
```

| 현재 저장소에서 가져갈 파일/폴더 | 실습 장비의 위치 |
|---|---|
| `week4/week04_pc_jetson_comm/` 전체 | `~/ros2_ws/src/week04_pc_jetson_comm/` |
| 패키지의 `config/joints.yaml` | `~/ros2_ws/src/week04_pc_jetson_comm/config/joints.yaml` |
| 패키지의 `launch/jetson_bringup.launch.py` | `~/ros2_ws/src/week04_pc_jetson_comm/launch/jetson_bringup.launch.py` |
| 패키지의 안쪽 `week04_pc_jetson_comm/*.py` | `~/ros2_ws/src/week04_pc_jetson_comm/week04_pc_jetson_comm/*.py` |

`docs/`와 `source_code/`는 참고용이며 ROS workspace에 별도로 배치할 필요가 없다.
`qos.py`는 Publisher와 Server가 같은 QoS 설정을 사용하도록 추가한 공통 모듈이므로 함께 복사한다.
자료의 `~/week4`는 workspace 예시이고, 이 가이드에서는 `~/ros2_ws`로 통일한다.
기존 `~/ros2_base`는 ROS 설치 기반(underlay)이므로 이 패키지로 덮어쓰지 않는다.

### Ubuntu PC로 복사

USB 등으로 저장소를 Ubuntu의 `~/ROS`에 옮겼다고 가정한 명령이다.
다른 위치에 옮겼다면 `~/ROS` 부분만 실제 경로로 바꾼다.

```bash
mkdir -p ~/ros2_ws/src
cp -a ~/ROS/week4/week04_pc_jetson_comm ~/ros2_ws/src/
test -f ~/ros2_ws/src/week04_pc_jetson_comm/package.xml
```

기존 동명 패키지가 있으면 실습 중 수정한 내용을 백업한 뒤 이 완성본으로 갱신한다.
`ros2 pkg create`는 실행하지 않는다. 같은 workspace에 동일 이름의 패키지를 두 개 놓지 않는다.

### Ubuntu PC에서 Jetson으로 복사

아래의 사용자명과 IP를 실제 값으로 바꾼다. 이 명령의 `~`는 SSH 접속 계정의 홈이다.

```bash
JETSON_USER='실제_Jetson_사용자명'
JETSON_IP='실제_Jetson_IP'
ping -c 3 "$JETSON_IP"
ssh "$JETSON_USER@$JETSON_IP" 'mkdir -p ~/ros2_ws/src'
scp -r ~/ros2_ws/src/week04_pc_jetson_comm "$JETSON_USER@$JETSON_IP:~/ros2_ws/src/"
ssh "$JETSON_USER@$JETSON_IP"
```

SSH가 없는 환경이면 USB로 같은 패키지 폴더를 Jetson의 위 경로에 복사한다.

## 2. 장비와 네트워크 준비

- PC와 Jetson을 같은 유선 네트워크에 연결한다.
- 각 장비의 `hostname -I`와 `ip -br addr`로 주소를 확인한다.
- 직결이고 DHCP가 없다면 예를 들어 PC `192.168.50.10/24`, Jetson `192.168.50.20/24`처럼
  같은 서브넷의 서로 다른 주소를 설정한다. 이 주소는 예시이며 기존 네트워크와 겹치지 않게 정한다.
- `ping -c 3 <Jetson_IP>`와 `ssh <Jetson_사용자>@<Jetson_IP>`로 연결을 확인한다.
- 제조사 Bringup과 3주차 노드는 해당 터미널에서 `Ctrl+C`로 종료한다.
  `/dev/ttyACM0`을 여는 프로그램은 이번 Publisher 한 개만 실행한다.

장비가 보이지 않으면 IP 설정뿐 아니라 방화벽의 DDS UDP/멀티캐스트 허용 여부도 확인한다.

## 3. 의존성과 하드웨어 설정

PC는 `/opt/ros/humble/setup.bash`, Jetson은 자료에 있는 `~/ros2_base/install/setup.bash`가
이미 설치되어 있다고 가정한다. Jetson에도 apt 방식으로 Humble이 설치되어 있다면
Jetson 명령의 underlay만 `/opt/ros/humble/setup.bash`로 바꾼다.
파일이 없다면 먼저 실습 장비의 ROS 설치 위치와 배포판을 확인한다.

### 양쪽 장비

빌드 도구와 YAML을 설치한다. 이미 설치되어 있으면 그대로 사용한다.

```bash
sudo apt update
sudo apt install python3-colcon-common-extensions python3-yaml python3-pip
```

ROS 패키지 의존성은 `package.xml`에 선언했다. `rosdep`이 준비된 환경이면
**해당 장비 underlay를 source한 후** 아래 명령으로 누락 의존성을 설치할 수 있다.

```bash
cd ~/ros2_ws
rosdep install --from-paths src --ignore-src --rosdistro humble -y
```

`rosdep` 자체가 없다면 실습 장비 관리자와 기존 설치 방식을 확인한다.
아래 빌드 전 점검에서 `rclpy`, `sensor_msgs`, `std_srvs`, `launch`, `launch_ros`,
`ament_index_python`, `rmw_fastrtps_cpp`를 찾을 수 있어야 한다.

### Jetson에서만

기존 ROS Python 환경과 같은 `python3`에 SDK를 설치한다. 검증에 사용한 버전은 1.5.0이다.
PC의 Listener와 Client에는 SDK가 필요하지 않다.

```bash
python3 -m pip install --user 'vassar-feetech-servo-sdk==1.5.0'
python3 -c 'from scservo_sdk import PortHandler, sms_sts, COMM_SUCCESS; print("SDK import OK")'
ls -l /dev/ttyACM0
id -nG
```

시리얼 권한이 없으면 다음 명령을 실행하고 **로그아웃 후 다시 로그인**한다.

```bash
sudo usermod -aG dialout "$USER"
```

장치 이름이 다르거나 실습 로봇의 서보 설정이 다르면 다음 파일을 수정한다.

```bash
nano ~/ros2_ws/src/week04_pc_jetson_comm/config/joints.yaml
```

제공 설정은 장치 `/dev/ttyACM0`, baudrate `1000000`, STS3215, 서보 ID `1..6`,
4096 ticks/rev, 중심 2048, 발행 목표 주기 **50 Hz**다. 제공 소스의 기본 주기를 따르며,
실제 속도는 시리얼 읽기 시간에 따라 낮아질 수 있다. 이 값들은 실습 장비와 대조해야 한다.
`sign`과 `zero_offset_rad`는 표시할 각도의 변환값이며 로봇에 보정값을 쓰지 않는다.
설정 변경 후에는 아래 빌드를 다시 실행한다. 설치된 YAML이 바뀌었는지 직접 확인하는 것이 확실하다.

### 읽기 전용 SDK 구현을 변경한 이유

제공 코드의 `ServoController.connect()`는 phase를 확인해 0으로 변경할 수 있고,
`disconnect()`는 `disable_all_servos()`를 호출한다.
따라서 토크와 설정을 바꾸지 않는다는 강의 지침에 맞도록, 같은 SDK에 포함된
`scservo_sdk.PortHandler`와 `sms_sts.ReadPos()`를 직접 사용했다.
초기화는 시리얼 포트를 열고, 종료는 포트만 닫는다.
읽기 요청 패킷은 전송하지만 토크·목표 위치·EEPROM 쓰기 명령은 전송하지 않는다.
근거: [SDK controller 구현](https://github.com/vassar-robotics/feetech-servo-sdk/blob/main/vassar_feetech_servo_sdk/controller.py),
[STS 위치 읽기 구현](https://github.com/vassar-robotics/feetech-servo-sdk/blob/main/scservo_sdk/sms_sts.py).

## 4. 양쪽에서 각각 빌드

### Ubuntu PC

```bash
source /opt/ros/humble/setup.bash
cd ~/ros2_ws
python3 -c 'import rclpy, yaml, launch, launch_ros, ament_index_python; from sensor_msgs.msg import JointState; from std_srvs.srv import Trigger; print("ROS dependencies OK")'
ros2 pkg prefix rmw_fastrtps_cpp
colcon list
colcon build --symlink-install --packages-select week04_pc_jetson_comm
source ~/ros2_ws/install/setup.bash
ros2 pkg executables week04_pc_jetson_comm
```

### Jetson

```bash
source ~/ros2_base/install/setup.bash
cd ~/ros2_ws
python3 -c 'import rclpy, yaml, launch, launch_ros, ament_index_python; from sensor_msgs.msg import JointState; from std_srvs.srv import Trigger; print("ROS dependencies OK")'
ros2 pkg prefix rmw_fastrtps_cpp
colcon list
colcon build --symlink-install --packages-select week04_pc_jetson_comm
source ~/ros2_ws/install/setup.bash
ros2 pkg executables week04_pc_jetson_comm
```

두 장비 모두 다음 네 실행 파일이 나와야 한다.

```text
week04_pc_jetson_comm joint_state_publisher
week04_pc_jetson_comm joint_state_topic_listener
week04_pc_jetson_comm joint_state_server
week04_pc_jetson_comm joint_state_client
```

`colcon list`에서 패키지가 안 보이면 경로, `package.xml`, 상위 `COLCON_IGNORE` 여부를 확인한다.
이 코드는 상대 import와 ROS 설치 데이터를 사용하므로 Python 파일을 더블클릭하거나
`python3 joint_state_topic_publisher.py`로 직접 실행하지 않는다.

## 5. 매 터미널마다 환경 설정

**PC의 새 터미널**에서는 아래를 실행한다.

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=30
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

**Jetson의 새 터미널 또는 SSH 접속**에서는 아래를 실행한다.

```bash
source ~/ros2_base/install/setup.bash
source ~/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=30
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

이전 실습의 daemon이 남아 있으면 환경을 바꾸기 전에 그 환경에서 `ros2 daemon stop`을 실행하고,
새 환경에서 `ros2 daemon start`를 실행한다. 처음이면 PC에서 `ros2 daemon start`로 시작한다.

## 6. 실제 실습 실행 순서

### 터미널 A: Jetson에서 Publisher와 Server 실행

```bash
ros2 launch week04_pc_jetson_comm jetson_bringup.launch.py
```

이 터미널은 실행 상태로 둔다. 기본 Reliability는 `reliable`이다.
Publisher는 포트를 단독 소유하고 Server는 Topic만 구독한다.

### 터미널 B: PC에서 Topic 확인 및 Listener 실행

5절의 PC 환경 설정을 한 후 실행한다.

```bash
ros2 node list
ros2 topic list
ros2 topic info /joint_states --verbose
ros2 run week04_pc_jetson_comm joint_state_topic_listener
```

`/joint_state_publisher`, `/joint_state_service_server`와 `/joint_states`가 보여야 한다.
Listener에는 6개 관절의 이름과 rad/deg 값이 계속 출력되어야 한다.
Listener는 `RELIABLE`로 고정되어 있다. 발행 목표 주기는 50 Hz이며 실제 수신 속도는
시리얼 읽기 시간과 네트워크 영향을 받는다.

### 터미널 C: PC에서 Service 호출

5절의 PC 환경 설정을 한 후 실행한다.

```bash
ros2 service list
ros2 service type /get_joint_state
ros2 interface show std_srvs/srv/Trigger
ros2 run week04_pc_jetson_comm joint_state_client
echo $?
ros2 service call /get_joint_state std_srvs/srv/Trigger '{}'
```

Client는 `success=True`와 관절값을 출력하고 종료 코드 0으로 끝난다.
실패하면 메시지를 출력하고 종료 코드 1로 끝난다. Server가 아직 Topic을 받지 못한 경우
`success=False`로 응답한다. 발견 5초 + 응답 5초의 제한이 있으므로 영원히 기다리지 않는다.
`ros2 service info`는 설치된 CLI 버전에 없을 수 있어 위의 `list`, `type`, `call`을 기본으로 사용한다.

Server는 마지막 메시지를 보관한다. Publisher가 중단되어도 이미 받은 값은 계속 응답하며,
이 실습 코드에는 오래된 데이터 판정 기능이 없다. 실시간 여부는 Topic 수신도 함께 확인한다.

## 7. QoS 불일치 및 복구

6절의 PC Listener를 실행한 채로 유지한다. Jetson의 터미널 A를 `Ctrl+C`로 종료한 뒤
Publisher와 Server의 Reliability를 함께 변경한다.

```bash
ros2 launch week04_pc_jetson_comm jetson_bringup.launch.py reliability:=best_effort
```

PC Listener는 `RELIABLE`로 고정되어 있으므로 관절값 출력이 멈추어야 한다.
Jetson Server의 Subscriber는 Publisher와 같은 `BEST_EFFORT`여서 계속 값을 받는다.
PC의 다른 터미널에서 `joint_state_client`를 실행하면 Service 응답은 계속 성공해야 한다.
Launch의 `reliability`는 JointState Topic에만 적용되며 Trigger Service QoS는 기본값을 사용한다.

Jetson Launch를 `Ctrl+C`로 종료한 뒤 다음과 같이 다시 실행한다.

```bash
ros2 launch week04_pc_jetson_comm jetson_bringup.launch.py reliability:=reliable
```

PC의 같은 Listener 터미널에 값이 다시 출력되어야 한다.
PC에서 `joint_state_client`도 다시 실행해 Service 응답을 확인한다.
Server Subscriber에도 같은 reliability가 전달되므로 두 모드에서 모두 동작해야 한다.
발표자료 20~21·34쪽에는 이전 BEST_EFFORT 기본값과 Listener 변경 절차가 남아 있다.
현재 `lecture.md`·`practice.md`와 제공 소스의 “Listener는 RELIABLE 고정,
Jetson launch argument만 변경” 절차를 기준으로 구현했다.

## 8. Domain 불일치 및 복구

PC에서 실행한 Listener와 echo를 `Ctrl+C`로 종료한다.
환경 변수 변경은 이미 실행 중인 노드에는 적용되지 않는다.
Jetson은 Domain 30에서 계속 실행하고, PC의 진단 터미널에서 다음을 실행한다.

```bash
ros2 daemon stop
export ROS_DOMAIN_ID=31
ros2 daemon start
ros2 node list
ros2 topic list
ros2 service list
```

Jetson의 두 노드, `/joint_states`, `/get_joint_state`가 사라져야 한다.
`/rosout`, `/parameter_events` 등 로컬 항목은 남을 수 있다.
다음 명령으로 복구하고 Listener와 Client를 다시 실행한다.

```bash
ros2 daemon stop
export ROS_DOMAIN_ID=30
ros2 daemon start
ros2 node list
ros2 topic list
ros2 service list
ros2 run week04_pc_jetson_comm joint_state_client
```

## 9. 현장에서 완료 확인할 항목

- [ ] PC에서 Jetson Ping 및 SSH 연결 성공
- [ ] 양쪽 `colcon build` 성공 및 실행 파일 네 개 등록 확인
- [ ] PC Listener가 실제 관절 6개의 값을 수신
- [ ] BEST_EFFORT Publisher + RELIABLE Listener에서 미수신, Client 응답은 성공
- [ ] Publisher를 RELIABLE로 재실행한 뒤 같은 Listener가 수신
- [ ] Python Client와 CLI Trigger 호출이 모두 성공
- [ ] Domain 31에서 Jetson 미발견, 30 복구 후 재발견
- [ ] 종료 시 각 노드 터미널에서 `Ctrl+C`, 필요하면 `ros2 node list --no-daemon`으로 확인

## 10. 개발 컴퓨터에서 검증한 범위

로컬에서는 ROS 노드를 대체한 단위 테스트와, SDK 1.5.0의 실제 패킷 구현을 사용한
가상 시리얼 테스트 **21개가 통과**했다. Python 배포물(wheel) 빌드도 성공했고,
모듈·ament 식별 파일·YAML·Launch·실행 진입점 네 개가 포함되는지 검사했다.
Python 3.8 이상 문법 호환성을 검사했으며, 실제 테스트 실행 인터프리터는 Python 3.12였다.
물리 로봇이나 현재 PC의 시리얼 포트에는 연결하지 않았다.

검증 대상은 발행 주기·메시지, QoS 두 모드, Listener, 최신값·미수신 Service 응답,
Client 성공·실패·시간 초과·취소, 설정 오류, 패키지 등록, Launch, 서보 읽기 오류 처리다.
실제 SDK 테스트에서는 초기화·종료 때 서보 명령이 없고 관절 ID 1..6에 위치 읽기 명령만
전송되는 것을 확인했다.

재검증하려면 저장소 최상위에서 실행한다. SDK는 테스트용 가상 시리얼에만 연결된다.

```bash
python3 -m pip install --user -r week4/tests/requirements.txt
python3 -m unittest discover -s week4/tests -v
```

**이 검증은 ROS 2 실기 실행을 대신하지 않는다.** 현재 Windows 환경에서는 Ubuntu의
`colcon build`, DDS 네트워크, 실물 관절값 수신을 검증하지 않았다.
실습 컴퓨터에서는 4~9절을 실행해 그 환경에서의 결과를 확인한다.

원본 자료: `docs/lecture.md`, `docs/practice.md`, `docs/week4_ROS2_pc_jetson_comm.pptx`.
Client의 유한 대기와 비동기 호출 API는
[ROS 2 Humble rclpy 구현](https://github.com/ros2/rclpy/blob/humble/rclpy/rclpy/client.py)을 확인했다.
