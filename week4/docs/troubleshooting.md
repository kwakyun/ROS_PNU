# 4주차 PC–Jetson 통신 실습 트러블슈팅

[practice.md](practice.md)의 0~7절과 현재 완성 코드 `week04_pc_jetson_comm`을 기준으로 작성했다.
일반 설치·파일 배치는 [Ubuntu 실습 가이드](../UBUNTU_GUIDE.md)를 먼저 참고한다.
아래 내용은 예상 장애의 진단 절차이며, 실습 장비에서 장애를 재현했다는 의미는 아니다.

**기본 환경:** Ubuntu PC + Jetson, ROS 2 Humble, workspace `~/ros2_ws`.
실습 PC가 Windows + WSL2라면 PC용 Linux 명령은 WSL Ubuntu에서 실행하고,
Windows PowerShell 명령은 9절에서만 실행한다. 순수 Ubuntu PC는 9절을 건너뛴다.

## 목차

- [빠른 증상 찾기](#quick)
- [0. 진단 전에 맞춰 둘 기준](#baseline)
- [1. IP·Ping·SSH 문제 — practice 1절](#network)
- [2. 파일 배치·빌드·패키지 실행 문제 — practice 2~4절](#build)
- [3. Python·SDK·YAML 문제 — practice 3~4절](#python)
- [4. 시리얼·관절값 읽기 문제 — practice 0절, 5-1절](#hardware)
- [5. DDS 발견·Topic 수신 문제 — practice 5-2절](#topic)
- [6. Service 응답 문제 — practice 5-3절](#service)
- [7. QoS·Domain 실험 결과가 예상과 다를 때 — practice 6~7절](#experiments)
- [8. 로봇 없이 통신 코드만 분리 검사하기](#isolation)
- [9. Windows + WSL2 전용 문제](#wsl)
- [10. 정상 상태로 복구하고 결과 기록하기](#recovery)
- [참고 자료](#sources)

<a id="quick"></a>
## 빠른 증상 찾기

| 증상 또는 오류 | 먼저 확인할 것 | 상세 위치 |
|---|---|---|
| `Network is unreachable`, Ping 무응답 | 유선 링크, IP 대역, 경로 | 1-1 |
| Ping은 되지만 SSH 실패 | SSH 서버·사용자명·22번 포트 | 1-2 |
| `ros2: command not found` | 장비별 ROS underlay source | 2-1 |
| `colcon: command not found` | colcon 설치 | 2-2 |
| `0 packages finished`, 패키지 무시됨 | `colcon list`, package.xml, COLCON_IGNORE | 2-3 |
| `Duplicate package names` | workspace 안의 동명 패키지 복사본 | 2-3 |
| `Package 'week04_pc_jetson_comm' not found` | 빌드 성공 여부, overlay source | 2-4 |
| `No executable found` | console_scripts, setup.cfg, 실행 이름 | 2-5 |
| Launch 또는 `joints.yaml`을 찾지 못함 | 설치 데이터, 실제 선택된 패키지 경로 | 2-6 |
| 코드 수정 후에도 옛 동작 | 다른 복사본·overlay·실행 중인 프로세스 | 2-7 |
| `No module named rclpy`, `_rclpy_pybind11` 오류 | ROS 환경·Python 버전·가상환경 | 3-1 |
| `No module named yaml` | PyYAML 설치 대상 Python | 3-2 |
| `scservo_sdk import failed` | Jetson SDK 설치·import 경로 | 3-3 |
| YAML 파싱 오류, `KeyError` | 들여쓰기·필수 키·설정 값 | 3-4 |
| `/dev/ttyACM0` 없음 | USB 연결·장치 번호 변경 | 4-1 |
| `Permission denied` | dialout 그룹·현재 로그인 세션 | 4-2 |
| `Device or resource busy`, 읽기가 불안정 | 포트를 동시에 연 프로그램 | 4-3 |
| `관절값 읽기 실패`, servo timeout | 전원·서보 ID·baudrate·케이블 | 4-4 |
| Ping 성공, ROS 노드는 안 보임 | Domain·localhost·RMW·멀티캐스트 | 5-1 |
| `/joint_states`는 있는데 출력이 없음 | Publisher 수, 읽기 오류, QoS | 5-2 |
| 50 Hz가 안 나옴, 값이 정지함 | 실제 수신·시리얼 지연·로봇 정지 상태 | 5-3 |
| Service 발견 5초 시간 초과 | Server 실행·이름·DDS 발견 | 6-1 |
| Service 응답 5초 시간 초과 | Server 생존·요청/응답 경로 | 6-2 |
| `success=False`, 아직 수신하지 못함 | Server의 Topic 수신 | 6-3 |
| `success=True`인데 값이 오래됨 | Server가 마지막 값을 보관하는 동작 | 6-4 |
| `ros2 service info`가 없는 명령 | Humble CLI 지원 명령 | 6-5 |
| BEST_EFFORT에서도 RELIABLE Listener가 출력 | 실제 QoS·중복 Publisher | 7-1 |
| Domain 31에서도 Jetson이 보임 | 현재 셸·daemon·실행 중인 노드의 Domain | 7-2 |

<a id="baseline"></a>
## 0. 진단 전에 맞춰 둘 기준

### 0-1. 터미널마다 장비와 환경부터 확인

SSH 터미널에서는 `~`가 Jetson 계정의 홈이고, PC 터미널에서는 PC 계정의 홈이다.
새 터미널에서 다음을 실행하면 현재 위치를 혼동하기 어렵다.

```bash
hostname
whoami
pwd
```

**Ubuntu PC/WSL에서 새 터미널을 열었을 때:**

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=30
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

**Jetson에서 새 터미널을 열었을 때:**

```bash
source ~/ros2_base/install/setup.bash
source ~/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=30
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

Jetson의 실제 ROS 설치가 `/opt/ros/humble`이면 첫 source 경로만 그에 맞게 바꾼다.
첫 빌드 전에는 `~/ros2_ws/install/setup.bash`가 없는 것이 정상이다. underlay만 source하여
빌드하고, 빌드가 성공한 뒤 overlay를 source한다.

양쪽에서 다음 출력이 같은지 비교한다.

```bash
printenv ROS_DISTRO ROS_DOMAIN_ID ROS_LOCALHOST_ONLY RMW_IMPLEMENTATION
```

예상값은 순서대로 `humble`, `30`, `0`, `rmw_fastrtps_cpp`다.
환경 변수는 이미 실행 중인 노드에 소급 적용되지 않는다. 변경 후 해당 노드를 재실행한다.
daemon은 변경 **전 환경**에서 종료하고 변경 후 다시 시작하는 것이 좋다. 자세한 순서는 7-2절에 있다.

### 0-2. 정상 상태와 실패 단계를 구분

```text
유선 연결·IP → 양방향 네트워크 → ROS 환경 → 노드 발견 → Topic 데이터 → Service 응답
```

| 확인 대상 | 정상 기준 |
|---|---|
| Jetson Launch | Publisher와 Service Server 프로세스가 둘 다 살아 있음 |
| 노드 | `/joint_state_publisher`, `/joint_state_service_server` 발견 |
| Topic | `/joint_states`, 타입 `sensor_msgs/msg/JointState`, 실습 Publisher 한 개 |
| Topic 데이터 | `name`과 `position`에 6개 값, 반복 수신 |
| Service | `/get_joint_state`, 타입 `std_srvs/srv/Trigger` |
| Client | 성공 메시지 후 정상 종료, 종료 코드 0 |

Ping은 ICMP 연결 확인이다. Ping 성공만으로 DDS가 통과한다는 뜻은 아니며,
ICMP만 차단된 네트워크에서는 Ping 실패와 SSH 성공이 함께 나타날 수도 있다.

### 0-3. 실습의 읽기 전용 원칙

`practice.md` 0절에 따라 포트는 Publisher 한 개만 사용하며 토크·목표 위치를 바꾸지 않는다.
포트 문제를 확인한다고 제조사 Bringup이나 별도 SDK 읽기 프로그램을 동시에 실행하지 않는다.
종료는 실행 터미널의 `Ctrl+C`를 우선 사용한다.
`killall -9 python3`, 모든 사용자에게 쓰기 권한을 주는 `chmod 777`은 기본 복구 방법으로 사용하지 않는다.

<a id="network"></a>
## 1. IP·Ping·SSH 문제 — practice 1절

### 1-1. Ping이 되지 않는다

**확인 — 양쪽 장비:**

```bash
ip -br link
ip -br addr
ip route
hostname -I
```

**확인 — PC:** 아래 예시 IP는 실제 Jetson 유선 IP로 바꾼다.

```bash
JETSON_IP='192.168.50.20'
ip route get "$JETSON_IP"
ping -c 3 "$JETSON_IP"
ip neigh
```

**출력 해석과 조치:**

- 유선 인터페이스가 `DOWN` 또는 `NO-CARRIER`: 케이블·USB Ethernet 어댑터·링크 LED를 확인한다.
- 유선 인터페이스에 IPv4가 없음: DHCP 서버가 있는 망인지 확인한다. 직결이면 두 장비에 수동 주소가 필요할 수 있다.
- `Network is unreachable`: 목적지 대역으로 나가는 경로가 없다. IP·넷마스크·인터페이스를 점검한다.
- `Destination Host Unreachable`, 이웃 상태 `INCOMPLETE`/`FAILED`: 상대가 꺼졌거나 주소·물리 연결이 잘못됐을 가능성이 있다.
- 무응답만 발생: 상대 IP, 중복 IP, 방화벽의 ICMP 정책을 확인한다.
- `ip route get`이 Wi-Fi나 VPN으로 나감: 겹치는 서브넷·VPN 경로를 확인한다. 실습 Ethernet으로 도달하도록 네트워크 설정을 수정한다.

직결 예시는 PC `192.168.50.10/24`, Jetson `192.168.50.20/24`다.
두 주소는 달라야 하며 같은 `/24` 대역이어야 한다. 기존 학교망·VPN과 겹치면 다른 승인된 대역을 사용한다.
직결용 게이트웨이와 DNS는 비워 둘 수 있지만 인터넷 패키지 설치에는 별도 인터넷 연결이 필요하다.

**복구 확인:** PC→Jetson과 Jetson→PC 각각 Ping을 확인한다.
SSH를 통해 Jetson의 네트워크를 변경하면 연결이 끊길 수 있으므로, 주소 변경은 현장 콘솔에서 하는 편이 확실하다.

### 1-2. Ping은 되지만 SSH가 안 된다

**PC:** 실제 사용자명과 IP를 사용한다.

```bash
ssh -v student@192.168.50.20
```

| 오류 | 의미·조치 |
|---|---|
| `Connection refused` | 해당 주소에는 도달했지만 SSH 서버가 안 듣거나 연결을 거부함 |
| `Connection timed out` | 주소·경로·22번 포트 방화벽부터 확인 |
| `Permission denied` | 사용자명·암호·키 인증 문제. ROS 코드 수정과 무관 |
| `REMOTE HOST IDENTIFICATION HAS CHANGED` | 같은 IP의 장비가 바뀌었거나 재설치됐는지 현장에서 확인 |

**Jetson 현장 터미널 — SSH 서버가 없는 경우:**

```bash
systemctl status ssh --no-pager
sudo apt install openssh-server
sudo systemctl enable --now ssh
```

호스트 키가 바뀌었다면 장비 정체를 확인한 뒤 해당 주소의 이전 기록만 갱신한다.
확인 없이 `known_hosts` 전체를 삭제하지 않는다.

```bash
ssh-keygen -R 192.168.50.20
```

**복구 확인:** SSH 접속 후 `hostname`으로 Jetson에 들어왔는지 확인한다.

### 1-3. Ping은 되는데 apt/pip 다운로드가 실패한다

직결 Ethernet으로 Jetson에 닿는 것과 인터넷 접속은 별개다.

```bash
ip route
getent hosts pypi.org
getent hosts packages.ros.org
```

기본 경로 또는 DNS가 없으면 실습실에서 제공하는 인터넷 연결·프록시를 사용한다.
오프라인 실습이라면 의존성을 미리 준비한다. 현재 Windows용 `site-packages`나
테스트 의존성 폴더를 Jetson에 복사하는 방식으로 해결하지 않는다.

<a id="build"></a>
## 2. 파일 배치·빌드·패키지 실행 문제 — practice 2~4절

### 2-1. `ros2: command not found`, source 파일이 없다

**해당 장비:**

```bash
ls /opt/ros
ls ~/ros2_base/install/setup.bash
command -v ros2
```

PC는 `/opt/ros/humble/setup.bash`, 자료의 Jetson은 `~/ros2_base/install/setup.bash`를 source한다.
경로가 없다면 장비의 실제 설치 위치와 배포판부터 확인한다. 없는 `setup.bash`를 직접 만들지 않는다.
새 SSH 접속에서도 다시 source해야 한다.

**복구 확인:** `ros2 --help`가 출력되고 `printenv ROS_DISTRO`가 `humble`인지 확인한다.

### 2-2. `colcon: command not found`

**해당 Ubuntu 장비:**

```bash
sudo apt update
sudo apt install python3-colcon-common-extensions
command -v colcon
```

빌드는 일반 사용자로 수행한다. `sudo colcon build`는 권한·Python 환경을 달라지게 만들 수 있다.

### 2-3. 패키지를 못 찾거나 중복 패키지가 나온다

**해당 장비의 workspace:**

```bash
cd ~/ros2_ws
pwd
find src -name package.xml -print
find src -name COLCON_IGNORE -print
ls -l ~/COLCON_IGNORE ~/ros2_ws/COLCON_IGNORE 2>/dev/null
colcon list
```

정상 패키지 파일은 `~/ros2_ws/src/week04_pc_jetson_comm/package.xml`에 있다.
Python 모듈은 그 안의 또 다른 `week04_pc_jetson_comm/` 폴더에 들어간다.
완성 패키지가 있으면 `ros2 pkg create`를 다시 실행하지 않는다.

- `0 packages finished`, `ignoring unknown package`: `package.xml`의 이름과 `colcon list` 결과를 확인한다.
- `COLCON_IGNORE`가 관련 상위 경로에 있음: 해당 폴더를 의도적으로 제외한 것인지 확인한다. 파일을 무조건 지우지 않는다.
- `Duplicate package names`: 같은 이름의 완성본·백업·저장소 복사본이 workspace 검색 범위에 함께 있다.
  사용할 패키지 한 개를 정하고 백업은 `~/ros2_ws` 밖에 보관한다.

**복구 확인:** `colcon list`에 `week04_pc_jetson_comm`이 한 번만 나타난다.

### 2-4. 빌드는 했는데 `Package ... not found`

**해당 장비, underlay를 source한 상태:**

```bash
cd ~/ros2_ws
colcon build --symlink-install --packages-select week04_pc_jetson_comm
source ~/ros2_ws/install/setup.bash
ros2 pkg prefix week04_pc_jetson_comm
```

빌드 로그에서 실제로 `Failed`가 없는지 확인한다. 출력 중 경고가 있다는 이유만으로 실패한 것은 아니다.
마지막 요약과 프로세스 종료 코드를 본다. `ros2 pkg prefix`는 현재 workspace의 install 경로를 가리켜야 한다.

```bash
ls ~/ros2_ws/log/latest_build/week04_pc_jetson_comm/
cat ~/ros2_ws/log/latest_build/week04_pc_jetson_comm/stderr.log
```

### 2-5. `No executable found`

**확인:**

```bash
ros2 pkg executables week04_pc_jetson_comm
cat ~/ros2_ws/src/week04_pc_jetson_comm/setup.cfg
```

실행 파일 이름은 Python 파일 이름과 다르다.

| 역할 | 올바른 명령 |
|---|---|
| Publisher | `ros2 run week04_pc_jetson_comm joint_state_publisher` |
| Listener | `ros2 run week04_pc_jetson_comm joint_state_topic_listener` |
| Server | `ros2 run week04_pc_jetson_comm joint_state_server` |
| Client | `ros2 run week04_pc_jetson_comm joint_state_client` |

Publisher 단독 실행은 Launch가 종료된 상태에서만 한다.
`setup.py`의 `console_scripts` 네 항목과 `setup.cfg`의 설치 위치
`$base/lib/week04_pc_jetson_comm`을 확인한 뒤 재빌드·source한다.
`.py` 파일에 실행 권한을 추가하는 것만으로 console_scripts 누락이 해결되지는 않는다.

### 2-6. Launch 또는 `config/joints.yaml`을 찾지 못한다

**확인:**

```bash
ros2 pkg prefix week04_pc_jetson_comm
python3 - <<'PY'
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
share = Path(get_package_share_directory('week04_pc_jetson_comm'))
print('실제로 사용하는 share:', share)
for relative in ('config/joints.yaml', 'launch/jetson_bringup.launch.py'):
    path = share / relative
    print(path, '존재:', path.is_file())
PY
```

소스에만 파일이 있으면 충분하지 않다. `setup.py`의 `data_files`에 config와 launch가 있어야 한다.
`resource/week04_pc_jetson_comm` 파일도 필요하다. 수정 후 2-4절 명령으로 재빌드한다.

**복구 확인:**

```bash
ros2 launch week04_pc_jetson_comm jetson_bringup.launch.py --show-args
```

이 명령은 launch 인자를 보여 주며 노드를 실행하지 않는다. `reliability`가 표시되어야 한다.

### 2-7. 코드를 고쳤는데 이전 코드가 실행된다

**확인:**

```bash
ros2 pkg prefix week04_pc_jetson_comm
python3 -c 'import week04_pc_jetson_comm; print(week04_pc_jetson_comm.__file__)'
printenv AMENT_PREFIX_PATH
```

가장 흔한 원인은 다음과 같다.

1. 참고용 `source_code/`만 수정하고 실제 배포 패키지는 수정하지 않았다.
2. PC 코드만 수정하고 Jetson 코드에는 반영하지 않았다.
3. 다른 workspace의 overlay를 나중에 source했다.
4. 새 코드가 있어도 기존 Python 노드를 재시작하지 않았다.
5. YAML·launch·진입점 변경 후 설치 결과를 갱신하지 않았다.

실제 패키지를 확인하고 두 장비에 같은 코드를 배치한다. 노드를 종료하고 재빌드한 뒤
새 터미널에서 underlay와 올바른 overlay만 source해 재실행한다.

설치 캐시 문제인지 구분하기 위해 기존 결과를 지우지 않고 별도 위치에서 빌드할 수도 있다.
아래는 **underlay만 source한 새 터미널**에서 실행한다.

```bash
cd ~/ros2_ws
colcon --log-base log_diagnose build \
  --build-base build_diagnose --install-base install_diagnose \
  --symlink-install --packages-select week04_pc_jetson_comm
source ~/ros2_ws/install_diagnose/setup.bash
ros2 pkg prefix week04_pc_jetson_comm
```

이 검사는 진단용이다. 원인을 고친 뒤 일반 `install`로 다시 빌드하고 새 터미널로 돌아간다.

<a id="python"></a>
## 3. Python·SDK·YAML 문제 — practice 3~4절

### 3-1. `rclpy` import 또는 `_rclpy_pybind11` 로딩 실패

**확인 — 오류가 발생한 같은 터미널:**

```bash
command -v python3
python3 --version
command -v ros2
printenv VIRTUAL_ENV CONDA_PREFIX PYTHONPATH
python3 -c 'import sys; print(sys.executable); import rclpy; print(rclpy.__file__)'
```

`No module named rclpy`이면 underlay source와 ROS 설치를 확인한다.
`_rclpy_pybind11`, `undefined symbol`, 다른 Python 버전이 붙은 `.so` 오류는
ROS를 빌드한 Python과 현재 인터프리터가 다른지 확인한다.
Conda/venv를 활성화했다면 해당 환경에서 빠져나온 새 터미널로 원래 ROS 환경을 다시 확인한다.
apt로 설치한 Humble/Ubuntu 22.04 환경은 시스템 Python을 기준으로 확인하고,
소스 빌드 Jetson은 그 underlay를 빌드한 Python을 따른다.

`pip install rclpy`, `.so` 파일 이름 변경, Windows 패키지 복사는 복구 방법으로 사용하지 않는다.
다른 CPU의 `build/`, `install/`도 복사하지 않고 각 장비에서 빌드한다.
근거: [ROS 설치 문제 해결 문서](https://github.com/ros2/ros2_documentation/blob/humble/source/How-To-Guides/Installation-Troubleshooting.rst).

### 3-2. `No module named yaml`

**Ubuntu 시스템 Python을 쓰는 해당 장비:**

```bash
sudo apt install python3-yaml
python3 -c 'import yaml; print(yaml.__file__)'
```

설치했는데도 실패하면 3-1절에서 실제 인터프리터를 확인한다.
`setup.py` 의존성을 적었다고 해서 모든 colcon 실행 방식이 Python 의존성을 자동 설치하는 것은 아니다.

### 3-3. `scservo_sdk import failed`, `serial` import 오류

**Jetson에서만:**

```bash
python3 -m pip show vassar-feetech-servo-sdk pyserial
python3 -m pip install --user 'vassar-feetech-servo-sdk==1.5.0'
python3 -c 'import scservo_sdk, serial; print(scservo_sdk.__file__); print(serial.__file__)'
```

완성본은 `vassar-feetech-servo-sdk`에 포함된 `scservo_sdk`를 사용한다.
비슷한 이름의 다른 SDK 패키지를 설치하지 않는다. `serial` import에 필요한 배포 패키지 이름은 `pyserial`이다.
로컬에 `serial.py`, `yaml.py` 등의 파일을 만들면 라이브러리와 이름이 충돌할 수 있으므로 출력 경로를 본다.

`pip` 자체가 없다면 `sudo apt install python3-pip`로 준비한다.
`externally-managed-environment`가 뜨면 현재 OS/Python이 실습 전제와 다른지 먼저 확인한다.
시스템 보호를 강제로 우회하기보다 장비에서 사용하는 ROS Python 환경에 맞춰 설치 방식을 정한다.
PC에서 Listener와 Client만 실행할 때는 SDK가 필요하지 않다.

### 3-4. YAML 오류 또는 설정 검증 실패

**Jetson:**

```bash
nl -ba ~/ros2_ws/src/week04_pc_jetson_comm/config/joints.yaml
python3 - <<'PY'
from pathlib import Path
from week04_pc_jetson_comm.hardware_interface import load_joint_config
path = Path.home() / 'ros2_ws/src/week04_pc_jetson_comm/config/joints.yaml'
print(load_joint_config(str(path)))
PY
```

이 명령은 설정만 읽고 시리얼 포트를 열지 않는다.

| 오류 | 점검·수정 |
|---|---|
| `ScannerError`, `ParserError` | 탭 대신 공백, 콜론·들여쓰기·목록 형식 확인 |
| `KeyError: joint_names` | `joint_names` 필수 키 복구 |
| 특정 관절 이름의 `KeyError` | `joint_names`와 `servo_id`의 이름이 정확히 같은지 확인 |
| `publish_hz must be ...` | 유한한 양수, 제공 소스 기준 기본 `50.0` 사용 |
| `ticks_per_rev must be ...` | 양수 사용, 제공 STS3215 설정은 `4096` |
| `servo_id values must be ...` | 중복 없는 실제 서보 ID 사용, 제공 설정은 1~6 |
| `supports ... STS/STS3215` | 모델 설정과 실물 확인. 다른 모델을 STS로 가장해 실행하지 않음 |

수정 후 재빌드하고 2-6절의 share 경로에서 **설치된 YAML**도 확인한다.
이 파일은 자체 설정 로더가 읽는 YAML이다. ROS 파라미터 파일의 `ros__parameters` 구조로 바꾸거나
그대로 `--params-file`에 전달하지 않는다.

### 3-5. `attempted relative import with no known parent package`

Python 파일을 직접 실행한 경우인지 확인한다.

```bash
ros2 run week04_pc_jetson_comm joint_state_topic_listener
```

설치된 console entry point를 사용한다. `sys.path`를 임의로 수정하는 방식으로 우회하지 않는다.

<a id="hardware"></a>
## 4. 시리얼·관절값 읽기 문제 — practice 0절, 5-1절

### 4-1. `/dev/ttyACM0`이 없다

**Jetson:**

```bash
ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
ls -l /dev/serial/by-id/ 2>/dev/null
lsusb
```

USB 장치가 아예 없으면 전원·데이터 케이블·커넥터를 확인한다.
장치가 `/dev/ttyACM1`처럼 바뀌었다면 어떤 장치인지 확인하고 `joints.yaml`의 `device`를 변경한다.
안정적인 `by-id` 링크가 존재하면 그 절대 경로를 사용할 수도 있다.

연결 로그는 다음으로 확인한다.

```bash
sudo dmesg --ctime | tail -n 60
```

반복 연결 해제·재연결 로그가 보이면 ROS 코드보다 전원·케이블·허브 문제를 먼저 조사한다.
로봇 상태를 확인한 뒤 노드를 종료하고 연결을 점검한다.

### 4-2. `Permission denied`

**Jetson:**

```bash
ls -l /dev/ttyACM0
id -nG
test -r /dev/ttyACM0 && test -w /dev/ttyACM0 && echo '현재 세션에서 읽기/쓰기 권한 있음'
```

Ubuntu의 일반적인 시리얼 장치 그룹이 `dialout`이면 다음으로 사용자를 추가한다.

```bash
sudo usermod -aG dialout "$USER"
```

로그아웃 후 다시 로그인한다. SSH라면 기존 접속을 종료하고 새로 연결한다.
`id -nG`에 `dialout`이 나타나는지 재확인한다. 장치 그룹이 다르면 실제 udev 정책을 확인한다.
권한 문제를 피하려고 ROS 노드를 `sudo`로 실행하면 환경과 설치 경로가 달라질 수 있다.

### 4-3. 포트를 다른 프로그램이 사용한다

**Jetson:**

```bash
sudo fuser -v /dev/ttyACM0
```

PID가 나오면 실제 프로세스 명령을 확인한다. `1234`는 발견한 PID로 바꾼다.

```bash
ps -p 1234 -o pid,user,args
```

제조사 Bringup·3주차 노드·중복 Publisher이면 해당 실행 터미널에서 `Ctrl+C`로 종료한다.
터미널을 찾을 수 없고 종료할 프로세스임을 확인한 경우 그 PID에만 `kill -INT 1234`를 보낸다.

`fuser`에 아무것도 안 나와도 모든 순간의 충돌을 배제하는 것은 아니다.
시리얼 장치가 중복 open을 허용하면 `busy` 없이 응답 패킷이 섞여 읽기 오류만 나타날 수도 있다.
Launch 실행 중 Publisher 단독 실행을 추가하지 않는다.

**복구 확인:** Launch 한 개만 실행한 상태에서 포트 사용자와 Publisher 수를 다시 확인한다.

### 4-4. `관절값 읽기 실패: servo N: ...`

현재 Publisher는 관절 하나라도 읽기에 실패하면 해당 주기의 **전체 JointState 발행을 건너뛴다**.
노드와 Topic 이름은 있어도 데이터가 없을 수 있다.

| 메시지·증상 | 가능한 원인 | 조치 순서 |
|---|---|---|
| `There is no status packet`, timeout | 모터 전원, ID 불일치, baudrate, 케이블 | 전원 상태 → 설정과 실물 ID 대조 → 배선 확인 |
| `Incorrect status packet`, checksum 오류 | 중복 포트 사용, 불안정한 통신 | 4-3절 확인 → 케이블·전원 점검 |
| `Cannot open ... at ... baud` | 지원하지 않는 baudrate 또는 포트 문제 | 포트·권한 확인, 제공 baudrate 1000000과 장비 설정 대조 |
| 특정 servo ID만 반복 실패 | 해당 서보 또는 그 뒤의 연결 문제 | 해당 ID와 연결 구간 점검 |
| 전압·과열·과부하 등 장치 오류 | 서보가 자체 오류 비트를 보고함 | 오류를 기록하고 장비 상태·제조사 절차에 따라 점검 |

USB 인터페이스가 보이는 것과 모터 전원이 정상인 것은 별개다.
토크 활성화·서보 ID 재설정·중심 보정 명령을 진단용으로 보내지 않는다.
완성 코드의 읽기 전용 연결 방식을 유지한다.

**복구 확인 — Jetson의 다른 터미널:**

```bash
ros2 topic echo /joint_states sensor_msgs/msg/JointState --qos-reliability best_effort --once
```

기다려도 출력이 없으면 `Ctrl+C`로 종료하고 Publisher 로그를 다시 확인한다.
`--once` 자체에 시간 제한이 있는 것은 아니다.

### 4-5. 각도가 이상하거나 0이 아니다

변환식은 다음과 같다.

```text
rad = (tick - center_tick) × 2π / ticks_per_rev × sign + zero_offset_rad
```

제공 설정에서 tick 2048은 0 rad, tick 3072는 약 +1.5708 rad(+90°)다.
로봇이 정지해도 모든 관절이 0이어야 하는 것은 아니다.
좌우 방향·기준 자세가 다른 경우 `sign`, `zero_offset_rad`, 관절 이름과 ID 대응을 확인한다.
그리퍼도 제공 실습 코드에서는 서보 회전각으로 표시하므로 미터 단위 개방 폭으로 해석하지 않는다.
값을 맞추려고 로봇을 임의로 움직이거나 SDK의 영점 보정 명령을 실행하지 않는다.

<a id="topic"></a>
## 5. DDS 발견·Topic 수신 문제 — practice 5-2절

### 5-1. Ping은 되지만 Jetson 노드가 안 보인다

**먼저 Jetson에서 확인:**

```bash
ros2 node list --no-daemon
ros2 topic info /joint_states --verbose
```

Jetson에서도 노드가 없으면 Launch 터미널의 `process has died`와 traceback을 먼저 확인한다.
한 노드가 죽고 다른 노드만 남을 수도 있으므로 두 노드를 각각 확인한다.

Jetson에서는 보이고 PC에서만 안 보이면 다음 순서로 확인한다.

1. 양쪽 터미널의 Domain 30, localhost 0, RMW 설정을 비교한다.
2. 설정을 바꾼 뒤 노드를 재시작했는지 확인한다.
3. 각 환경의 daemon을 정리하고 `ros2 node list --no-daemon`과 비교한다.
4. RMW 패키지가 실제로 설치되어 있는지 확인한다.

```bash
ros2 pkg prefix rmw_fastrtps_cpp
```

RMW 로딩 오류가 나면 apt 기반 Humble 장비에서는 누락 패키지를 설치한다.

```bash
sudo apt install ros-humble-rmw-fastrtps-cpp
```

소스 빌드 Jetson은 기존 `ros2_base`에 맞는 의존성 구성을 확인한다.
환경 변수를 지정하는 것만으로 구현체가 설치되지는 않는다.
RMW 변경 뒤 daemon도 재시작해야 한다.
근거: [ROS RMW 전환 문서](https://github.com/ros2/ros2_documentation/blob/humble/source/How-To-Guides/Working-with-multiple-RMW-implementations.rst).

**양방향 멀티캐스트 확인:**

| 터미널 | 명령 |
|---|---|
| PC에서 먼저 실행 | `ros2 multicast receive` |
| Jetson에서 실행 | `ros2 multicast send` |

PC에서 수신 문구가 나오면 반대로 Jetson에서 receive, PC에서 send를 실행한다.
완료 후 receive는 `Ctrl+C`로 종료한다. 명령 자체가 없다면 CLI 도구 미설치와 통신 실패를 구분한다.
이 검사는 멀티캐스트 경로의 단서이며 DDS의 모든 포트·데이터 경로를 검증하지는 않는다.
근거: [ROS 멀티캐스트 진단](https://github.com/ros2/ros2_documentation/blob/humble/source/How-To-Guides/Installation-Troubleshooting.rst).

**네트워크 설정 확인:**

```bash
ip route
ip -br addr
sudo ufw status verbose
printenv ROS_DISCOVERY_SERVER FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
```

VPN·다중 NIC·기존 Fast DDS XML·Discovery Server 설정이 있으면 실습용 경로를 제한하는지 확인한다.
학교에서 의도적으로 사용하는 설정이면 유지하고 담당자와 맞춘다.
이전 개인 실험의 설정임이 확인된 경우에만 해당 새 터미널에서 해제하고 노드를 재시작한다.

```bash
unset ROS_DISCOVERY_SERVER FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
```

방화벽이 원인이라면 실습 NIC·상대 주소·DDS 통신에 필요한 범위로 규칙을 조정한다.
전체 방화벽을 영구 해제하거나 7400번 포트 하나만 열면 해결된다고 가정하지 않는다.
DDS 포트는 Domain과 참여 프로세스 구성의 영향을 받는다.

### 5-2. `/joint_states`는 보이는데 출력이 없다

**Jetson과 PC에서 비교:**

```bash
ros2 topic info /joint_states --verbose
ros2 node info /joint_state_publisher
ros2 node info /joint_state_service_server
```

- `Publisher count: 0`: Subscriber가 Topic을 만들었거나 발견 정보가 남아 있을 수 있다. Publisher 생존부터 확인한다.
- Publisher는 있지만 Jetson에서도 데이터가 없음: 4-4절의 실제 관절 읽기 실패를 확인한다.
- Jetson에서는 수신하고 PC에서는 안 됨: 5-1절 네트워크와 실제 endpoint QoS를 확인한다.
- 타입이 `sensor_msgs/msg/JointState`가 아님: 다른 노드나 잘못된 Topic을 보고 있는지 확인한다.

**데이터 수신 확인 — 각각의 장비:**

```bash
ros2 topic echo /joint_states sensor_msgs/msg/JointState --qos-reliability best_effort
```

정상 데이터 확인 후 `Ctrl+C`로 종료한다. 수신 검사는 BEST_EFFORT로 하고,
`practice.md` 6절의 불일치 실험에서는 RELIABLE로 고정된 Python Listener를 유지한다.
`Could not determine the type`이면 위처럼 타입을 명시할 수 있지만, 발행 자체가 없으면 계속 기다린다.

### 5-3. 50 Hz가 안 나오거나 값이 변하지 않는다

**Jetson과 PC에서 각각:**

```bash
ros2 topic hz /joint_states
ros2 topic info /joint_states --verbose
```

`hz`는 해당 Subscriber가 받은 속도다. Publisher 설정값과 항상 일치하는 보장은 없다.
10초 정도 여러 샘플을 보고 판단한다. 명령의 QoS 옵션은 설치 버전별로 다를 수 있으므로
`ros2 topic hz --help`에 없는 옵션을 억지로 추가하지 않는다.
근거: [Humble topic hz 구현과 옵션](https://github.com/ros2/ros2cli/blob/humble/ros2topic/ros2topic/verb/hz.py).

- 양쪽 모두 느림: Publisher의 읽기 오류, CPU 부하, USB·서보 응답 지연 확인.
- Jetson은 정상이고 PC만 느림: 네트워크 손실, PC 부하, DDS 경로 확인.
- 설정한 50 Hz보다 빠름: 중복 Publisher 또는 변경된 YAML 확인.
- 값은 같지만 `header.stamp`가 계속 갱신됨: 정지한 로봇의 정상 반복 측정일 수 있음.
- `header.stamp`까지 고정되거나 새 출력이 멎음: 발행 중단·다른 Publisher·수신 중단 구분.

설치된 YAML의 `publish_hz: 50.0`을 확인한다. 타이머는 0.02초마다 실행되도록 설정되어 있지만
읽기가 오래 걸리면 이를 충족하지 못할 수 있다. 문제를 숨기기 위해 주파수만 높이지 않는다.

### 5-4. 다른 조의 값이나 중복 노드가 보인다

```bash
ros2 topic info /joint_states --verbose
ros2 node list
```

같은 네트워크에서 모든 조가 Domain 30을 쓰면 서로 발견될 수 있다.
자신의 Jetson Launch를 종료했는데도 Publisher가 남는다면 다른 장비나 백그라운드 노드를 확인한다.
실습 담당자가 조별 Domain을 배정한다면 PC와 Jetson을 함께 변경한다.
이 경우 Domain 불일치 실험의 “정상 Domain”도 배정된 값으로 맞춰 기록한다.
다른 조의 노드를 종료하려고 하지 않는다.

<a id="service"></a>
## 6. Service 응답 문제 — practice 5-3절

### 6-1. `/get_joint_state 서비스를 5초 안에 찾지 못했습니다`

**PC:**

```bash
ros2 service list -t
ros2 service type /get_joint_state
ros2 node info /joint_state_service_server
```

예상 타입은 `std_srvs/srv/Trigger`다.
Jetson Launch에서 Server가 살아 있는지, 실행 파일이 `joint_state_server`인지 확인한다.
Jetson에서는 보이고 PC에서 안 보이면 5-1절의 DDS 발견 문제로 돌아간다.

방금 시작하여 발견이 늦었을 수 있으므로 노드가 확인된 뒤 Client를 다시 한 번 실행한다.
무한 대기로 바꾸면 원인 구분이 어려워진다.

### 6-2. `서비스 응답 대기 시간(5초)을 초과했습니다`

발견은 됐지만 정해진 시간 안에 응답을 받지 못한 상태다.
발견 직후 Server가 종료되거나 데이터 경로가 막히거나 잘못된 동명 Server가 있을 수 있다.

**Jetson의 다른 터미널에서 로컬 호출:**

```bash
ros2 run week04_pc_jetson_comm joint_state_client
```

| 결과 | 다음 조사 |
|---|---|
| Jetson에서도 시간 초과 | Server traceback·프로세스 생존·동명 Server 확인 |
| Jetson 성공, PC만 시간 초과 | 요청·응답 네트워크 경로와 PC 환경 확인 |
| 즉시 `success=False` | 통신 응답은 받음. 6-3절의 Topic 수신 문제 조사 |

현재 Server는 요청할 때 시리얼 포트를 읽지 않는다. 저장된 메시지를 즉시 포맷하므로
응답 지연을 단순히 서보 읽기 지연 탓으로 판단하지 않는다.

### 6-3. `success=False`, 아직 `/joint_states`를 수신하지 못했다

Service 통신은 성공했지만 Server의 캐시에 데이터가 없는 상태다.

**Jetson:**

```bash
ros2 topic info /joint_states --verbose
ros2 param get /joint_state_publisher reliability
ros2 param get /joint_state_service_server reliability
ros2 topic echo /joint_states sensor_msgs/msg/JointState --qos-reliability best_effort --once
```

시작 직후라면 첫 Topic 수신 후 다시 호출한다.
계속 실패하면 Publisher 읽기 오류와 Server Subscriber의 QoS를 확인한다.
직접 두 노드를 따로 실행하다 설정이 달라졌다면 모두 종료하고 한 Launch로 재실행한다.

`수신한 JointState의 이름과 위치 배열이 올바르지 않습니다`가 나오면
`name`이 비어 있거나 `name`과 `position` 길이가 다른 메시지를 받은 것이다.
완성 Publisher는 정상 측정 시 같은 길이의 배열을 만들므로 다른 Publisher·수정 코드도 확인한다.

### 6-4. `success=True`인데 같은 옛날 값만 나온다

현재 Server는 **마지막 수신 메시지를 계속 보관**하며 데이터 만료 시간을 검사하지 않는다.
Publisher가 종료되어도 Server가 살아 있으면 이전 값으로 성공 응답할 수 있다.

**확인:**

```bash
ros2 topic echo /joint_states sensor_msgs/msg/JointState --qos-reliability best_effort
```

새 메시지와 `header.stamp` 갱신 여부를 확인한다. 정지 상태에서는 관절값이 같아도 정상이다.
Service 성공만을 실시간 하드웨어 측정의 증거로 사용하지 않는다.
이 동작은 `practice.md`의 최신 메시지 캐시 설계에 따른 것이며,
오래된 데이터 거부 기능은 별도 확장이다.

### 6-5. `ros2 service info`가 `invalid choice`로 실패한다

Humble의 기본 `ros2service`에는 `info` 하위 명령이 없다.
`practice.md`의 이 명령에서 실패해도 Server 코드의 오류로 단정하지 않는다.

```bash
ros2 service --help
ros2 service list -t
ros2 service type /get_joint_state
ros2 node info /joint_state_service_server
ros2 service call /get_joint_state std_srvs/srv/Trigger '{}'
```

지원 명령 근거: [Humble ros2service 등록 목록](https://github.com/ros2/ros2cli/blob/humble/ros2service/setup.py).
CLI 호출이 계속 기다리면 `Ctrl+C`로 종료한다. 이 패키지의 Python Client와 달리
CLI가 동일한 5초 제한을 갖는다고 가정하지 않는다.

### 6-6. Client가 출력한 뒤 바로 종료된다

정상 동작일 수 있다. 이번 Client는 한 번 호출하고 종료하도록 작성했다.

```bash
ros2 run week04_pc_jetson_comm joint_state_client
echo $?
```

바로 다음 명령에서 확인한 종료 코드가 0이면 성공, 1이면 실패다.
중간에 다른 명령을 실행하면 `$?`는 그 명령의 결과가 되므로 함께 기록한다.
연속 모니터링에는 `joint_state_topic_listener`를 사용한다.

<a id="experiments"></a>
## 7. QoS·Domain 실험 결과가 예상과 다를 때 — practice 6~7절

### 7-1. Reliability 불일치 실험

| Publisher | Subscriber | 예상 |
|---|---|---|
| BEST_EFFORT | BEST_EFFORT | 수신 |
| BEST_EFFORT | RELIABLE | 미수신 |
| RELIABLE | BEST_EFFORT | 수신 |
| RELIABLE | RELIABLE | 수신 |

호환성 근거: [ROS QoS 문서](https://github.com/ros2/ros2_documentation/blob/humble/source/Concepts/Intermediate/About-Quality-of-Service-Settings.rst).

**PC — 실습 중 그대로 유지할 RELIABLE Listener:**

```bash
ros2 run week04_pc_jetson_comm joint_state_topic_listener
```

**Jetson — 이전 Launch를 Ctrl+C로 종료하고 실행:**

```bash
ros2 launch week04_pc_jetson_comm jetson_bringup.launch.py reliability:=best_effort
```

이때 PC Listener의 미수신과 incompatible QoS 경고는 예상한 실험 결과다.
Server는 Publisher와 같은 BEST_EFFORT로 구독하므로 Client 호출은 성공해야 한다.
데이터 자체를 분리 확인하려면 별도 터미널에서 BEST_EFFORT echo를 사용할 수 있다.

Jetson Launch를 종료한 뒤 `reliability:=reliable`로 재실행하면
PC의 같은 Listener에서 수신이 다시 시작되어야 한다.

**예상과 다를 때:**

- BEST_EFFORT에서도 Listener가 수신: 이전 BEST_EFFORT Listener 사본을 실행 중인지, RELIABLE Publisher가 추가로 있는지 확인한다.
- RELIABLE로 바꿨는데 미수신: 새 Launch가 성공했는지, 실제 Topic 데이터가 있는지, PC Domain이 같은지 확인한다.
- BEST_EFFORT echo도 미수신: 의도한 QoS 불일치 외에 하드웨어·네트워크 문제가 겹쳤을 가능성이 있다.
- `reliability must be ...` 또는 launch 인자 오류: 소문자 `best_effort`/`reliable`만 사용한다.

```bash
ros2 topic info /joint_states --verbose
ros2 param get /joint_state_publisher reliability
ros2 param get /joint_state_service_server reliability
```

현재 구현은 노드 생성 시 QoS 객체를 만든다. `ros2 param set`으로 값만 바꾸어도
기존 Publisher/Subscription의 QoS는 재생성되지 않는다.
실습 안내대로 Launch를 종료·재실행하고 실제 endpoint QoS를 확인한다.

### 7-2. Domain 31에서 여전히 Jetson이 보인다

**PC의 기존 Listener/echo를 Ctrl+C로 종료한 뒤, Domain 30 진단 터미널에서:**

```bash
ros2 daemon stop
export ROS_DOMAIN_ID=31
ros2 daemon start
printenv ROS_DOMAIN_ID
ros2 node list
ros2 node list --no-daemon
ros2 topic list
ros2 service list
```

Jetson은 Domain 30을 유지해야 한다. PC와 Jetson을 모두 31로 바꾸면 계속 통신하는 것이 정상이다.
`/rosout`, `/parameter_events` 등은 남을 수 있으므로 목록 전체가 비는 것을 기대하지 않는다.

**여전히 보일 때 확인:**

1. 환경 변수를 바꾼 터미널과 `ros2 node list`를 실행한 터미널이 같은가?
2. `export`를 사용했는가?
3. 이전 Listener가 다른 터미널에서 Domain 30으로 계속 실행 중인가?
4. Jetson도 실수로 31로 바꾸지 않았는가?
5. 같은 Domain에 다른 조의 동명 노드가 있는가?
6. daemon 결과와 `--no-daemon` 결과가 다른가?

**Domain 30으로 복구 — 현재 31인 같은 터미널:**

```bash
ros2 daemon stop
export ROS_DOMAIN_ID=30
ros2 daemon start
ros2 node list
ros2 run week04_pc_jetson_comm joint_state_client
```

환경을 먼저 31로 바꾼 뒤 daemon stop을 하면 기존 Domain 30 daemon을 정리하지 못할 수 있다.
각 Domain에 남은 daemon을 정리해야 한다면 해당 Domain을 지정해서 종료한다.

```bash
ROS_DOMAIN_ID=30 ros2 daemon stop
ROS_DOMAIN_ID=31 ros2 daemon stop
```

daemon 종료는 Publisher나 Server를 종료하는 명령이 아니다.

<a id="isolation"></a>
## 8. 로봇 없이 통신 코드만 분리 검사하기

하드웨어 문제인지 ROS 코드 문제인지 구분할 때 사용한다.
**하나의 Ubuntu 장비에서**, 실제 실습 노드와 별개로 Domain 130·localhost 전용으로 실행한다.
세 터미널 모두 같은 장비의 underlay와 `~/ros2_ws/install/setup.bash`를 source해야 한다.
아래 값은 인위적으로 만든 시험 데이터다.

**터미널 A — Server만 실행:**

```bash
env ROS_DOMAIN_ID=130 ROS_LOCALHOST_ONLY=1 RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
  ros2 run week04_pc_jetson_comm joint_state_server
```

**터미널 C — 아직 데이터가 없을 때 Client 호출:**

```bash
env ROS_DOMAIN_ID=130 ROS_LOCALHOST_ONLY=1 RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
  ros2 run week04_pc_jetson_comm joint_state_client
```

예상은 `success=False`와 아직 Topic을 받지 못했다는 메시지다.

**터미널 B — 임의 JointState 발행:**

```bash
env ROS_DOMAIN_ID=130 ROS_LOCALHOST_ONLY=1 RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
  ros2 topic pub /joint_states sensor_msgs/msg/JointState \
  '{name: [test_joint], position: [0.5]}' \
  --rate 5 --qos-reliability reliable
```

터미널 C의 같은 Client 명령을 다시 실행한다.
예상은 `success=True`와 `test_joint=+0.5000 rad (+28.65 deg)`다.

선택적으로 네 번째 터미널에서 같은 `env ...` 접두어로
`ros2 run week04_pc_jetson_comm joint_state_topic_listener`를 실행해 출력을 확인한다.

이 검사는 SDK·시리얼 포트·물리 로봇·장비 간 네트워크를 검증하지 않는다.
성공하면 최소한 같은 장비의 Topic→Server→Client 흐름은 동작한다는 뜻이다.
완료 후 A·B와 추가 Listener를 `Ctrl+C`로 종료한다.
`env` 설정은 각 명령에만 적용되므로 원래 터미널의 Domain 값은 바뀌지 않는다.
남은 시험용 daemon은 `ROS_DOMAIN_ID=130 ros2 daemon stop`으로 정리할 수 있다.

<a id="wsl"></a>
## 9. Windows + WSL2 전용 문제

순수 Ubuntu PC에서는 이 절차를 적용하지 않는다.

### 9-1. Windows는 Ping이 되지만 WSL에서는 안 된다

**Windows PowerShell:**

```powershell
wsl --version
wsl --list --verbose
Get-Content "$env:USERPROFILE\.wslconfig"
```

배포판이 WSL2인지 확인한다. `.wslconfig`는 Windows 사용자 프로필에 놓으며,
파일명이 `.wslconfig.txt`가 아닌지 확인한다.
기존 설정을 보존하면서 같은 `[wsl2]` 구역에 다음 항목을 설정한다.

```ini
[wsl2]
networkingMode=mirrored
```

Mirrored networking의 OS 조건은 Windows 11 22H2 이상이다.
변경 후 실행 중인 WSL 작업을 저장하고 PowerShell에서 `wsl --shutdown`을 실행한 뒤 WSL을 다시 연다.
필요하면 `wsl --update` 후 재확인한다.
근거: [Microsoft WSL 네트워킹](https://learn.microsoft.com/en-us/windows/wsl/networking).

**WSL Ubuntu:**

```bash
ip -br addr
ip route
ping -c 3 192.168.50.20
```

IP는 실제 Jetson 주소로 바꾼다. Windows에서의 성공을 WSL에서도 성공한 것으로 기록하지 않는다.

### 9-2. Ping은 되지만 WSL의 DDS 수신이 안 된다

5-1절 환경·양방향 멀티캐스트를 먼저 확인한다.
`practice.md`는 관리자 PowerShell에서 다음 Hyper-V inbound 설정을 사용한다.

```powershell
Set-NetFirewallHyperVVMSetting -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -DefaultInboundAction Allow
```

이는 WSL VM의 기본 inbound 정책을 넓히는 설정이다. 실습실 관리 정책에 맞게 적용한다.
명령을 찾지 못하면 관리자 여부뿐 아니라 Windows 빌드와 Hyper-V 방화벽 기능 지원 여부를 확인한다.
없는 명령을 Linux에서 실행하거나 Ubuntu 방화벽 설정으로 대체하지 않는다.
적용 후 WSL↔Jetson 멀티캐스트와 실제 Topic 수신을 다시 확인한다.
근거: [Microsoft WSL 네트워킹 및 방화벽 안내](https://learn.microsoft.com/en-us/windows/wsl/networking).

### 9-3. WSL을 재시작한 뒤 패키지가 안 보인다

WSL 재시작은 Linux 프로세스와 이전 셸 환경을 종료한다.
새 WSL 터미널에서 0-1절의 PC 환경 설정을 다시 적용하고 노드를 재실행한다.
Windows 경로의 빌드 결과 대신 WSL 홈의 `~/ros2_ws`에서 만든 결과를 사용한다.

<a id="recovery"></a>
## 10. 정상 상태로 복구하고 결과 기록하기

### 10-1. 기본 실습 상태로 복구

1. 직접 실행한 PC Listener·echo와 Jetson Launch를 각각 `Ctrl+C`로 종료한다.
2. 각 장비의 새 터미널에서 0-1절의 올바른 underlay와 overlay를 source한다.
3. 해당 터미널을 Domain 30, localhost 0, Fast DDS로 맞춘다.
4. Domain 실험을 했다면 7-2절에 따라 daemon을 정리한다.
5. Jetson에서 포트 중복 사용이 없는지 확인한다.
6. Jetson에서 아래 Launch를 한 번만 실행한다.

```bash
ros2 launch week04_pc_jetson_comm jetson_bringup.launch.py
```

PC의 준비된 터미널에서 확인한다.

```bash
ros2 node list
ros2 topic info /joint_states --verbose
ros2 run week04_pc_jetson_comm joint_state_client
```

그다음 Listener를 실행해 반복 수신을 확인한다.
기본 상태가 회복된 후에만 QoS와 Domain 실험을 각각 다시 진행한다.

### 10-2. 해결되지 않을 때 수집할 정보

PC와 Jetson 각각 아래 정보를 텍스트로 저장하면 어느 단계가 다른지 비교하기 쉽다.
기록 파일에는 내부 IP·사용자 경로가 포함될 수 있으므로 필요한 실습 담당자에게 전달한다.

```bash
mkdir -p ~/ros2_ws/diagnostics
DIAG_FILE="$HOME/ros2_ws/diagnostics/$(hostname)-$(date +%Y%m%d-%H%M%S).txt"
{
  date -Is
  hostname
  uname -m
  cat /etc/os-release
  command -v python3
  python3 --version
  printenv ROS_DISTRO ROS_DOMAIN_ID ROS_LOCALHOST_ONLY RMW_IMPLEMENTATION
  ip -br addr
  ip route
  ros2 pkg prefix week04_pc_jetson_comm
  ros2 pkg executables week04_pc_jetson_comm
  timeout 15s ros2 node list --no-daemon
  timeout 15s ros2 topic info /joint_states --verbose
  timeout 15s ros2 service list -t
} > "$DIAG_FILE" 2>&1
echo "$DIAG_FILE"
```

`timeout`으로 종료된 조회는 실패 원인과 함께 기록된 것이므로 전체 정상 출력으로 해석하지 않는다.
여기에 다음을 추가한다.

- 오류가 처음 나타난 `practice.md` 절 번호와 실행 명령
- Jetson Launch 터미널의 traceback 전체
- Client의 메시지와 직후 종료 코드
- Jetson 로컬에서는 수신되는지, PC에서만 실패하는지
- 변경한 `joints.yaml` 항목과 `reliability`, Domain 값
- 마지막으로 성공했던 단계와 변경한 내용

### 10-3. 현장 확인 표

| 항목 | 실제 결과 기록 |
|---|---|
| PC→Jetson / Jetson→PC 네트워크 | |
| 양쪽 빌드·패키지 경로 | |
| Jetson 로컬 JointState 반복 수신 | |
| PC Listener 반복 수신 | |
| Python Client 및 CLI 응답 | |
| BEST_EFFORT Publisher + RELIABLE Listener 미수신, Client 성공 | |
| RELIABLE로 재실행 후 같은 Listener 수신 | |
| PC Domain 31에서 Jetson 미발견 | |
| PC Domain 30 복구 후 재발견 | |

<a id="sources"></a>
## 참고 자료

실습의 구현·실행 이름과 기대 동작은 [practice.md](practice.md)를 우선 기준으로 삼았다.
설정 경로는 [Ubuntu 실습 가이드](../UBUNTU_GUIDE.md), 오류 메시지와 캐시·timeout 동작은
[현재 패키지 소스](../week04_pc_jetson_comm/week04_pc_jetson_comm/)와 대조했다.
배포판·CLI·WSL 차이는 각 관련 절에 연결한 공식 문서 및 Humble 소스로 확인했다.
