# [9주차] MuJoCo 로봇 시뮬레이션과 ROS 2 연동 — 실습 안내서

> `lecture.md`를 먼저 읽고 순서대로 수행한다.
> `<배포자료경로>`는 `9주차 제공파일`이 저장된 실제 경로로 바꾼다.
> **PC = Windows PC 안의 WSL2 Ubuntu 22.04**, **Jetson = 실제 로봇에 연결된 장비**이다.
> MuJoCo도 WSL에서 실행하며 화면은 WSLg를 통해 Windows에 표시된다.
> `Windows PowerShell`이라고 표시한 네트워크 준비 명령 외에는 PC 명령을 WSL 터미널에서 실행한다.
> `<Jetson_IP>`, `<PC_IP>`는 각 장비의 실제 IP 주소로 바꾼다. 조별 Domain ID는 4주차에 사용한 값을 입력한다.

## 0. 실습 전

최종 동작은 다음과 같다.

```text
MuJoCo 단독 제어 → 6관절 모델·목표·물리 스텝 확인
Jetson arm_io + PC Launch → 실제·시뮬레이션 상태 수신
실제 토크 OFF + follow ON → 실제 자세를 화면에 복사
follow OFF + 현재 자세 유지 → 자세 A 준비 → sync
자세 B 공통 목표 1회 → 8초 기록 → CSV·PNG·지표 확인
follow OFF + 실제 토크 OFF → 노드 정상 종료
```

### 제공 Python 파일 한눈에 보기

파일을 배치하기 전에 다음 역할을 확인한다. PC는 WSL을 뜻하며, Jetson과 담당 작업이 다르다.

| 파일 | 간단한 역할 | 사용·수정 범위 |
|---|---|---|
| `mujoco_lab.py` | ROS 없이 MuJoCo 모델을 확인하고 관절을 움직이는 단독 실습 프로그램이다. | PC에서 직접 실행하며 TODO 1·2를 완성한다. |
| `mujoco_ros_bridge.py` | ROS로 받은 목표·실제 자세를 MuJoCo에 반영하고 시뮬레이션 관절값을 발행한다. | PC에서 Launch로 실행하며 TODO 3·4를 완성한다. |
| `real_sim_comparator.py` | 실제·시뮬레이션 관절값을 기록하고 비교 그래프·CSV·지표 YAML을 저장한다. | PC에서 Launch로 실행하며 코드는 수정하지 않는다. |
| `comparison_goal.py` | 자세 A·B를 확인하고 PC 시각이 담긴 6관절 목표를 한 번 발행한다. | PC에서 실행하며 `--send`를 붙일 때만 목표를 보낸다. |
| `arm_io.py` | 실제 서보의 관절값을 읽고 목표·토크 명령을 처리하는 ROS 노드이다. | Jetson에서 실행하며 코드는 수정하지 않는다. |
| `hardware_interface.py` | 서보 SDK 통신과 radian–tick 변환을 담당하는 공통 모듈이다. | `arm_io.py`가 불러와 사용하며 직접 실행·수정하지 않는다. |
| `mujoco_compare.launch.py` | Bridge와 Comparator 두 노드를 함께 실행하는 Launch 파일이다. | PC에서 `ros2 launch`로 사용하며 코드는 수정하지 않는다. |
| `__init__.py` | Python 패키지 초기화용 파일이다. | 직접 실행하지 않으며 패키지 생성 시 만들어진 파일을 유지한다. |

여기서 Bridge는 `mujoco_ros_bridge`, Comparator는 `real_sim_comparator`를 줄여 부르는 이름이다.
파일을 모두 하나씩 실행하는 것이 아니다. 단독 실습에서는 `mujoco_lab.py`를 실행하고, 실제 연동에서는 Jetson의 `arm_io`와 PC의 Launch를 실행한다.
패키지 생성 후 별도로 수정하는 `setup.py`·`package.xml`은 위 제공 프로그램과 구분한다. 해당 등록 작업은 3절의 TODO 5~7에서 수행한다.

---

## 1. PC와 Jetson 환경 확인

4주차의 통신 구조를 그대로 사용한다. 이번 주차의 중심은 MuJoCo 연동이므로 통신 코드는 새로 작성하지 않는다.
다만 이전 설정이 남아 있다고 가정하지 말고, 아래 순서로 **네트워크 → Python 환경 → 빌드 → ROS 통신**을 확인한다.

### 1.0 PC–Jetson 네트워크 준비 — 4주차 복습

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

### 1.1 IP와 Ping 확인

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

### 1.2 PC — 기존 venv 확인, 없는 경우에만 생성

이번 실습의 환경은 `~/week9/.venv`이다. **이미 있으면 설치·생성 절차를 건너뛰고 C로 이동한다.**
7주차 YOLO 환경은 재사용하지 않으며 torch·torchvision·CUDA 빌드도 필요하지 않다.

#### A. 기존 환경 유무 확인

PC의 WSL 터미널에서 확인한다.

```bash
if [ -f "$HOME/week9/.venv/pyvenv.cfg" ]; then
  echo "기존 9주차 venv 있음: C의 활성화·확인으로 이동"
else
  echo "9주차 venv 없음: B에서 생성"
fi
```

#### B. ~/week9/.venv가 없는 경우에만 준비·생성

새 환경을 만들 때 venv 생성 기능도 아직 설치되어 있지 않다면 다음을 한 번 실행한다. 이미 설치되어 있으면 건너뛴다.

```bash
sudo apt update
sudo apt install python3.10-venv
```

`sudo`는 WSL Ubuntu 계정의 비밀번호를 사용한다. 권한이 없으면 위 두 설치 명령은 조교가 수행한다.
이후 venv 생성·pip 설치·빌드는 학생 계정으로 수행한다.
ROS 2 Humble 자체는 `/opt/ros/humble/setup.bash`가 준비되어 있어야 한다.

일반적인 생성 명령은 `python3.10 -m venv .venv`이지만, 이번에는 시스템 ROS Python 패키지도 읽어야 하므로 **`--system-site-packages`를 추가**한다.
ROS 바이너리와 같은 시스템 Python을 사용한다. [ROS 2 Python 환경 안내](https://github.com/ros2/ros2_documentation/blob/humble/source/How-To-Guides/Using-Python-Packages.rst)

아래 생성 명령은 `~/week9/.venv`가 없는 경우에만 실행한다.

```bash
mkdir -p ~/week9
cd ~/week9
source /opt/ros/humble/setup.bash
/usr/bin/python3.10 -m venv --system-site-packages .venv
```

#### C. 기존 또는 새 venv 활성화·확인

기존 환경을 쓰는 학생도 여기부터 실행한다. 정상인 환경을 삭제하거나 다시 생성하지 않는다.

```bash
cd ~/week9
source /opt/ros/humble/setup.bash
source ~/week9/.venv/bin/activate
touch ~/week9/.venv/COLCON_IGNORE
export PYTHONDONTWRITEBYTECODE=1

command -v python3
command -v colcon
cat ~/week9/.venv/pyvenv.cfg
python3 -m pip --version
python3 -c "import rclpy, sensor_msgs, std_srvs, ament_index_python, launch, launch_ros; print('ROS imports OK')"
echo "$DISPLAY"
```

Python과 pip는 `~/week9/.venv/` 아래 경로로 표시되어야 한다. colcon은 `/usr/bin/colcon`이어도 정상이다.
`pyvenv.cfg`의 `include-system-site-packages = true`, `ROS imports OK`, 비어 있지 않은 `DISPLAY`를 확인한다.
기존 venv에서 ROS import가 실패하면 먼저 ROS 환경 적용·Python 3.10·`include-system-site-packages` 값을 확인한다. 기존 환경의 설정이 다르면 조교와 원인을 확인한 뒤 수정한다.
GUI 창의 실제 표시 여부는 6절에서 확인한다.
`ensurepip is not available`이면 위 `python3.10-venv` 설치를 확인한다. `rclpy` import 실패 시 ROS 환경 적용 여부와 Python 3.10 사용 여부부터 확인한다.

### 1.3 Jetson — 실제 로봇 환경

Jetson의 학생 계정에서 실행한다. PC용 MuJoCo venv를 복사하거나 생성하지 않는다.

```bash
source ~/ros2_base/install/setup.bash
python3 -c "import rclpy, yaml, sensor_msgs, std_srvs; print('ROS/PyYAML OK')"
python3 -c "import vassar_feetech_servo_sdk; print('Feetech SDK OK')"
ls -l /dev/ttyACM0
test -r /dev/ttyACM0 && test -w /dev/ttyACM0 && echo "serial permission OK"
```

---

## 2. PC Workspace와 제공 파일 배치

### 2.1 ~/week9 안에 ROS 패키지를 생성하고 파일 배치

`~/week9`는 **워크스페이스**, `~/week9/week09_mujoco_ros`는 **ROS 패키지 루트**이다.
`setup.py`, `setup.cfg`, `package.xml`은 패키지 루트에 두고, ROS 노드 소스는 그 안의 `week09_mujoco_ros/`에 둔다.
따라서 소스 경로는 `~/week9/week09_mujoco_ros/week09_mujoco_ros/`이다. 별도의 `src/` 폴더는 만들지 않는다.
이미 이 구조로 준비되어 있다면 파일 배치 확인과 3절의 설정 작성으로 넘어간다.

처음 준비할 때는 PC의 WSL 터미널에서 **`~/week9`로 이동한 뒤** 기본 패키지를 생성한다.

```bash
mkdir -p ~/week9
cd ~/week9
source /opt/ros/humble/setup.bash
ros2 pkg create week09_mujoco_ros --build-type ament_python \
  --license Apache-2.0
```

이 명령으로 바깥쪽 패키지 폴더와 안쪽 Python 코드 폴더가 함께 생성된다. 생성된 설정 파일을 `~/week9`로 옮기지 않는다.
제공자료의 `source_code/` 안에 있는 파일을 다음 트리에 맞춰 배치한다. 파일 배치 도구는 자유롭게 선택한다.

```text
~/week9/                                # 워크스페이스 루트, 여기서 빌드
├── week09_mujoco_ros/                   # ROS 패키지 루트
│   ├── setup.py                        # 자동 생성 후 TODO 5·6 작성
│   ├── setup.cfg                       # 자동 생성 후 3.6절 확인·작성
│   ├── package.xml                     # 자동 생성 후 TODO 7 작성
│   ├── resource/
│   │   └── week09_mujoco_ros            # 자동 생성, 유지
│   ├── week09_mujoco_ros/               # Python 코드 폴더
│   │   ├── __init__.py
│   │   ├── arm_io.py
│   │   ├── hardware_interface.py
│   │   ├── mujoco_ros_bridge.py
│   │   ├── real_sim_comparator.py
│   │   └── comparison_goal.py
│   ├── config/
│   │   ├── joints.yaml
│   │   └── comparison_poses.yaml
│   ├── launch/
│   │   └── mujoco_compare.launch.py
│   ├── models/
│   │   ├── scene.xml
│   │   ├── physicai_arm.xml
│   │   ├── robot.xml
│   │   ├── physicai_arm.urdf
│   │   └── assets/                     # STL·PNG 전체
│   ├── mujoco_lab.py                   # ROS 없이 실행하는 단독 프로그램
│   └── requirements.txt
├── .venv/                              # PC에만 생성
├── build/                              # 빌드 후 자동 생성
├── install/                            # 빌드 후 자동 생성
├── log/                                # 빌드 후 자동 생성
└── results/                            # 비교 기록 후 자동 생성
```

터미널로 배치하려면 아래 `<배포자료경로>`를 WSL에서 접근 가능한 실제 경로로 바꾼다. Windows 파일은 `/mnt/c/...` 형태로 접근한다.
이미 TODO를 수정한 파일이 있다면 해당 완성본을 사용하고 원본으로 덮어쓰지 않는다.


### 2.2 PC Python 의존성 설치와 확인

활성화한 학생 venv에만 설치한다.

```bash
cd ~/week9/week09_mujoco_ros
source /opt/ros/humble/setup.bash
source ~/week9/.venv/bin/activate
python3 -m pip install -r requirements.txt
python3 - <<'PY'
import sys
import mujoco
import numpy
import matplotlib
import yaml
import rclpy
assert sys.prefix != sys.base_prefix, 'venv를 활성화한다.'
assert mujoco.__version__ == '3.10.0', 'MuJoCo 버전을 확인한다.'
assert 1 <= int(numpy.__version__.split('.')[0]) < 2, 'NumPy는 2 미만을 사용한다.'
print('Python:', sys.executable)
print('MuJoCo:', mujoco.__version__)
print('NumPy:', numpy.__version__)
print('Matplotlib:', matplotlib.__version__)
print('PyYAML:', yaml.__version__)
print('PC packages OK')
PY
```

`PC packages OK`와 MuJoCo 3.10.0, NumPy 1.x를 확인한다.
ImportError·OpenGL 라이브러리 오류·다운로드 실패는 조교에게 전달한다.
패키지가 설치되어도 WSLg GUI와 Jetson 통신이 자동으로 준비되는 것은 아니다.

### 2.3 코드 역할 확인

각 파일의 역할과 수정 범위는 0절의 표를 다시 확인한다. 전체 데이터 흐름은 lecture.md 2절의 그림을 참고한다.
모델 파일을 다른 주차에서 가져오지 않는다. `comparison_poses.yaml`도 `config/`에 배치하며 `config/*.yaml` 설치 등록에 함께 포함된다.

---

## 3. 핵심 코드와 패키지 등록 TODO 완성

코드 TODO 1~4와 패키지 등록 TODO 5~7을 완성한다.
코드 TODO 1~4는 대입 위치·API 이름·괄호를 제공하고, 값이나 인자를 넣을 자리에 `### TODO ###` 주석을 둔다.
각 주석 줄을 필요한 값이나 인자로 교체한다. 함수 인자는 순서대로 작성하고 각 인자 뒤에 쉼표를 넣는다. TODO 1의 대입값 뒤에는 쉼표를 넣지 않는다.
고정된 QoS depth `10`과 저장 변수는 이미 제공하므로 유지한다. 주석만 지우고 값을 비워 두는 것은 완성이 아니다.
미완성 상태도 구문 검사나 빌드는 통과할 수 있지만, 실행하면 빈 대입값이나 누락된 함수 인자 때문에 `ValueError` 또는 `TypeError`가 발생할 수 있다. 실행 전에 코드 빈칸을 모두 완성한다.
TODO 5~7은 제공 코드의 빈칸이 아니라, 패키지 생성 도구가 만든 파일을 직접 수정하는 작업이다.

### 3.1 Actuator 목표 배열 대입

`mujoco_lab.py`의 `run_segment()`에서 이번 구간의 `target` 배열을 `data.ctrl[:]`에 대입한다.
대입식 괄호 안의 `### TODO ###`를 목표 배열로 교체한다. 괄호는 여러 줄로 작성하기 위한 것이며 그대로 유지한다.
현재 위치 `data.qpos`를 덮어쓰지 않는다. 목표 설정 뒤 물리 계산으로 움직이는 것을 확인하는 과제이다.

### 3.2 물리 스텝 호출

같은 반복문에서 `mujoco.mj_step()`에 `model`, `data`를 전달한다.
두 `### TODO ###` 줄을 각각 모델 객체와 상태 객체 인자로 교체한다.
목표 대입 다음에 호출하며 Viewer 동기화·시간 대기는 이미 제공한다.

### 3.3 시뮬레이션 상태 Publisher

`mujoco_ros_bridge.py`의 초기화 부분에서 다음 조건으로 Publisher를 생성한다.
제공된 `self.create_publisher()` 호출의 두 빈칸에 메시지 타입과 Topic을 순서대로 넣는다.

- API: `self.create_publisher()`
- 타입: `JointState`
- Topic: `/sim/joint_states` 또는 같은 값을 가진 `SIM_STATE_TOPIC`
- QoS depth: `10`
- 저장 변수: `self._state_publisher`

### 3.4 공통 목표 Subscriber

같은 초기화 부분에서 다음 조건으로 Subscriber를 생성한다.
제공된 `self.create_subscription()` 호출의 세 빈칸에 메시지 타입·Topic·callback을 순서대로 넣는다.

- API: `self.create_subscription()`
- 타입: `JointState`
- Topic: `/joint_targets` 또는 같은 값을 가진 `TARGET_TOPIC`
- callback: `self._on_target`
- QoS depth: `10`
- 저장 변수: `self._target_subscription`

모델 로딩·목표 검사·배열 변환·물리 Timer·실제 토크·Launch·결과 계산은 이미 제공한다.
안전 코드나 모델 파라미터를 수정하지 않는다.

### 3.5 TODO 5 — setup.py에 Launch·설정·모델 등록

`~/week9/week09_mujoco_ros/setup.py`를 연다. `data_files`는 패키지의 Python 코드가 아닌 파일을 설치 위치에 배치하는 설정이다.
등록하지 않으면 원본 폴더에 파일이 있어도 `ros2 launch`나 설치된 모델 경로 조회에서 찾지 못할 수 있다.

파일 상단에 `import os`와 `from glob import glob`을 추가한다.
`setup()`의 기존 `data_files` 두 항목은 유지하고, TODO 위치에 아래 표의 네 파일 묶음을 추가한다.

```python
data_files=[
    ('share/ament_index/resource_index/packages',
     ['resource/' + package_name]),
    ('share/' + package_name, ['package.xml']),
    # TODO 5: 아래 표에 따라 (설치 폴더, 파일 목록) 네 항목을 추가한다.
],
```

| 원본 파일 묶음 | 설치 폴더 |
|---|---|
| `launch/*.launch.py` | `share/week09_mujoco_ros/launch` |
| `config/*.yaml` | `share/week09_mujoco_ros/config` |
| `models/*.xml`과 `models/*.urdf` | `share/week09_mujoco_ros/models` |
| `models/assets/*.stl`과 `models/assets/*.png` | `share/week09_mujoco_ros/models/assets` |

- 각 항목은 `(설치 폴더, 파일 목록)` 형태로 작성한다.
- 설치 폴더는 `os.path.join('share', package_name, ...)`으로 구성한다.
- 파일 목록은 `glob('경로 패턴')`으로 얻고, 두 확장자를 포함할 때는 두 목록을 `+`로 합친다.
- `models`의 XML과 `assets`를 모두 등록하여 모델 내부의 상대 경로를 유지한다.

### 3.6 TODO 6 — setup.py에 실행 파일 등록

같은 파일의 `entry_points` → `console_scripts`에 아래 네 실행 파일을 등록한다.
각 항목은 `'실행이름 = 패키지명.모듈명:main'` 형식의 문자열로 작성한다.

```python
entry_points={
    'console_scripts': [
        # TODO 6: 아래 네 모듈의 main 함수를 실행 파일로 등록한다.
    ],
},
```

| 실행 이름 | Python 모듈 |
|---|---|
| `arm_io` | `week09_mujoco_ros.arm_io` |
| `comparison_goal` | `week09_mujoco_ros.comparison_goal` |
| `mujoco_ros_bridge` | `week09_mujoco_ros.mujoco_ros_bridge` |
| `real_sim_comparator` | `week09_mujoco_ros.real_sim_comparator` |

`hardware_interface.py`는 다른 노드가 불러오는 모듈이므로 별도 실행 파일로 등록하지 않는다.
`mujoco_lab.py`는 workspace 최상위에서 직접 실행하므로 여기 등록하지 않는다.
생성된 `~/week9/week09_mujoco_ros/setup.cfg`를 열고 다음 내용으로 확인·작성한다. PC와 Jetson 모두 같은 내용을 사용한다.

```ini
[develop]
script_dir=$base/lib/week09_mujoco_ros

[install]
install_scripts=$base/lib/week09_mujoco_ros
```

`$base`는 설치 도구가 해석하는 값이므로 위 내용을 그대로 파일에 작성한다.

### 3.7 TODO 7 — package.xml에 실행 의존성 등록

`~/week9/week09_mujoco_ros/package.xml`을 열고 `<package>` 안에 다음 실행 의존성을 `<exec_depend>패키지명</exec_depend>` 형식으로 추가한다.

| 용도 | 등록할 패키지명 |
|---|---|
| ROS 노드·메시지·Service | `rclpy`, `sensor_msgs`, `std_srvs` |
| 패키지 자산 경로·Launch | `ament_index_python`, `launch`, `launch_ros` |
| 그래프·수치 계산·YAML | `python3-matplotlib`, `python3-numpy`, `python3-yaml` |

```xml
<!-- TODO 7: 위 표의 실행 의존성 9개를 exec_depend 태그로 추가한다. -->
```

생성된 `<export>`의 `<build_type>ament_python</build_type>`과 기존 테스트 의존성은 유지한다.
`package.xml`은 필요한 의존성을 선언하는 파일이지 설치 명령이 아니다.
MuJoCo를 포함한 PC Python 패키지는 2.2절의 `requirements.txt`로 venv에 설치하며, `colcon build`가 대신 설치해 주지 않는다.
빌드 도구는 시스템 Python을, PC 노드의 실제 실행은 MuJoCo venv를 사용한다. 자세한 실행 방식은 다음 절을 따른다.

---

## 4. PC 빌드와 실행 파일 확인

### 4.1 빌드와 노드 실행에 사용하는 Python 구분

`python3 mujoco_lab.py`는 현재 터미널의 Python을 사용한다.
반면 `ros2 run`이 찾은 실행 파일에는 빌드 시 기록된 Python 경로(shebang)가 있어, **venv를 활성화하는 것만으로 실행 Python이 바뀌지는 않는다.**
그래서 단독 프로그램에서는 MuJoCo import가 되는데 ROS 노드에서는 `ModuleNotFoundError`가 날 수 있다.

이번 제공 Launch는 두 PC 노드의 실행 명령 앞에 `~/week9/.venv/bin/python3`를 붙인다.
`python_executable` 인자의 기본값이 이 경로이며 Bridge와 Comparator에 모두 적용된다.
실행 구조는 다음과 같다.

```text
시스템 Python + colcon → 패키지와 ROS 실행 파일 설치
ros2 launch → ~/week9/.venv/bin/python3 + 설치된 Bridge 실행 파일
            → ~/week9/.venv/bin/python3 + 설치된 Comparator 실행 파일
Jetson ros2 run arm_io → Jetson의 시스템 Python + 서보 SDK
```

Launch의 `prefix`로 실행 명령 앞에 Python을 지정한다. [ROS 2 Launch 실행 명령 설명](https://github.com/ros2/launch/blob/humble/launch/launch/descriptions/executable.py)
학생이 shebang·시스템 Python 경로를 수정하거나 MuJoCo를 시스템에 설치할 필요는 없다.

### 4.2 시스템 colcon으로 빌드

패키지 폴더의 상위인 **워크스페이스 루트 `~/week9`에서 빌드**한다. 아래 명령은 시스템 Python과 apt로 설치한 colcon을 명시한다.
`--base-paths ./week09_mujoco_ros`로 탐색할 패키지 경로를 지정한다. `setup.py`와 `package.xml`은 이 폴더 안에 있다.
빌드 산출물 `build/`, `install/`, `log/`는 `~/week9` 아래에 생성된다. `.venv/COLCON_IGNORE`도 유지한다.

```bash
cd ~/week9
source /opt/ros/humble/setup.bash
/usr/bin/python3 /usr/bin/colcon build --symlink-install \
  --base-paths ./week09_mujoco_ros \
  --packages-select week09_mujoco_ros
source ~/week9/install/setup.bash
ros2 pkg executables week09_mujoco_ros
```

`Summary: 1 package finished`를 확인한 다음 아래 네 실행 파일을 확인한다.
빌드 실패 시 다음 단계로 넘어가지 말고 4.4절을 먼저 확인한다.

```text
week09_mujoco_ros arm_io
week09_mujoco_ros comparison_goal
week09_mujoco_ros mujoco_ros_bridge
week09_mujoco_ros real_sim_comparator
```

### 4.3 설치 자산과 venv 확인

다음 명령으로 Launch·설정·모델 자산의 설치와 PC 노드가 사용할 Python을 확인한다.

```bash
ros2 pkg prefix --share week09_mujoco_ros
ls ~/week9/install/week09_mujoco_ros/share/week09_mujoco_ros/{launch,config,models,models/assets}
~/week9/.venv/bin/python3 -c "import sys, mujoco, numpy, matplotlib, yaml, rclpy; print(sys.executable); print('PC node imports OK')"
ros2 launch week09_mujoco_ros mujoco_compare.launch.py --show-args
```

Launch 파일, `joints.yaml`·`comparison_poses.yaml`, XML·URDF, STL·PNG가 각 폴더에 있어야 한다.
빌드 성공만으로 TODO 완성 여부가 확인되는 것은 아니다. 등록 TODO를 비워 두어도 빌드는 성공할 수 있으므로 실행 파일·자산 목록과 뒤의 실제 실행까지 확인한다.
`python_executable`의 기본 경로가 자신의 `~/week9/.venv/bin/python3`인지 확인한다.
PC에서는 `arm_io`를 실행하지 않는다. Bridge와 Comparator는 7절처럼 제공 Launch로 실행한다.

### 4.4 기존 빌드가 실패했거나 다른 Python으로 빌드한 경우

`build`, `install`, `log`는 정상 빌드에서도 생기는 폴더이다. 존재 자체가 오류는 아니다.
다른 장비에서 가져온 산출물, 이전 경로의 캐시, 일반 설치와 symlink 설치의 혼용이 있으면 정리하고 다시 빌드한다.
기존 실습 노드를 종료하고 **새 WSL 터미널**에서 다음을 실행한다. 이 정리는 최초 오류 복구 때만 필요하다.

```bash
cd ~/week9
pwd
ls
```

현재 위치가 자신의 `/home/<계정>/week9`이고, 그 아래 `week09_mujoco_ros/` 안에 `setup.py`, `package.xml`, 안쪽 Python 코드 폴더 `week09_mujoco_ros/`가 있는지 확인한 뒤 실행한다.
아래 삭제 대상은 이 workspace의 재생성 가능한 빌드 산출물 세 폴더이며, 소스·`.venv`·`results`는 유지된다.

```bash
rm -rf build install log
source /opt/ros/humble/setup.bash
/usr/bin/python3 /usr/bin/colcon build --symlink-install \
  --base-paths ./week09_mujoco_ros \
  --packages-select week09_mujoco_ros
source ~/week9/install/setup.bash
ros2 pkg executables week09_mujoco_ros
```

`/usr/bin/colcon`이 없다면 시스템 빌드 도구를 `sudo apt install python3-colcon-common-extensions`로 설치한다. 기존 venv는 다시 생성하지 않는다.
`Package ... not found`라면 경로와 `package.xml`을, 빌드는 성공했는데 실행 파일이 없다면 TODO 6을 확인한다.
`No module named mujoco`는 빌드 성공 여부와 별개이므로 2.2절의 venv 설치와 7.3절의 Launch 실행을 확인한다.

---

## 5. Jetson에서 패키지 생성·파일 배치·설정·빌드

Jetson도 PC와 같은 **워크스페이스 → ROS 패키지 → Python 코드 폴더 구조**를 사용한다.
`setup.py`, `setup.cfg`, `package.xml`은 `~/week9/week09_mujoco_ros`에, ROS 노드 소스는 `~/week9/week09_mujoco_ros/week09_mujoco_ros`에 둔다.
아래 명령은 Jetson 화면에서 연 로컬 터미널에서 수행한다. PC용 venv는 사용하지 않는다.

### 5.1 ~/week9 안에 패키지 생성

이미 `~/week9/week09_mujoco_ros/setup.py`와 `~/week9/week09_mujoco_ros/package.xml`이 있다면 생성 블록을 건너뛴다.
처음 준비할 때는 `~/week9`로 이동하여 기본 패키지를 생성한다. 기존 평평한 구조는 2.1절의 백업·재배치 안내를 따른다.

```bash
mkdir -p ~/week9
cd ~/week9
source ~/ros2_base/install/setup.bash
ros2 pkg create week09_mujoco_ros --build-type ament_python \
  --license Apache-2.0
```

생성된 `~/week9/week09_mujoco_ros` 안의 기본 파일은 그 위치에 유지하고 다음 트리에 맞춰 제공 파일을 채운다.
이미 기본 패키지가 생성되어 있다면 생성 명령은 반복하지 않는다.

### 5.2 제공 파일을 트리에 맞춰 배치

전달 도구는 자유롭게 선택하여 다음 위치에 파일을 배치한다. PC에서 TODO를 완성한 Python 파일은 그 완성본을 사용한다.
`models`는 `assets`까지 포함해 배치한다. Jetson에는 PC `.venv`, `mujoco_lab.py`, `requirements.txt`, PC 빌드 산출물을 가져올 필요가 없다.

```text
~/week9/                                # 워크스페이스 루트, 여기서 빌드
├── week09_mujoco_ros/                   # ROS 패키지 루트
│   ├── setup.py
│   ├── setup.cfg
│   ├── package.xml
│   ├── resource/
│   │   └── week09_mujoco_ros
│   ├── week09_mujoco_ros/               # Python 코드 폴더
│   │   ├── __init__.py
│   │   ├── arm_io.py
│   │   ├── hardware_interface.py
│   │   ├── mujoco_ros_bridge.py
│   │   ├── real_sim_comparator.py
│   │   └── comparison_goal.py
│   ├── config/
│   │   ├── joints.yaml
│   │   └── comparison_poses.yaml
│   ├── launch/
│   │   └── mujoco_compare.launch.py
│   └── models/
│       ├── scene.xml
│       ├── physicai_arm.xml
│       ├── robot.xml
│       ├── physicai_arm.urdf
│       └── assets/
├── build/                              # 빌드 후 자동 생성
├── install/                            # 빌드 후 자동 생성
└── log/                                # 빌드 후 자동 생성
```

### 5.3 생성된 setup.py·setup.cfg·package.xml 작성

Jetson에서 생성된 다음 세 파일을 완성한다. PC와 같은 등록 내용을 사용한다.

| 파일 | 작성할 내용 |
|---|---|
| `~/week9/week09_mujoco_ros/setup.py` | 3.5절의 Launch·설정·모델·자산 등록과 3.6절의 실행 파일 4개 등록을 작성한다. |
| `~/week9/week09_mujoco_ros/setup.cfg` | 3.6절의 `[develop]`, `[install]`과 실행 파일 설치 경로를 확인·작성한다. |
| `~/week9/week09_mujoco_ros/package.xml` | 3.7절의 실행 의존성 9개를 추가하고 `ament_python` build type을 유지한다. |

패키지 이름은 계속 `week09_mujoco_ros`이다. 워크스페이스 폴더가 `week9`라고 해서 `package_name`, XML의 `<name>`, resource 파일 이름을 `week9`로 바꾸지 않는다.
Jetson에서는 `arm_io`만 실행하므로 MuJoCo나 PC requirements는 설치하지 않는다.

### 5.4 ~/week9에서 빌드

기존 노드를 종료하고 새 Jetson 터미널에서 소스 위치를 확인한다.

```bash
cd ~/week9
pwd
ls week09_mujoco_ros/{setup.py,setup.cfg,package.xml,config/joints.yaml}
```

이전 평평한 구조의 빌드 산출물이나 복사된 캐시가 있다면 `pwd`가 자신의 `/home/<Jetson계정>/week9`인지 확인한 뒤 정리한다.
처음 빌드하며 세 폴더가 없다면 아래 정리는 생략해도 된다. 소스와 설정 파일은 유지된다.

```bash
rm -rf build install log
```

이어서 같은 워크스페이스 루트 `~/week9`에서 빌드한다. `--base-paths ./week09_mujoco_ros`는 그 아래의 ROS 패키지 폴더를 탐색하도록 지정한다.

```bash
source ~/ros2_base/install/setup.bash
colcon build --symlink-install \
  --base-paths ./week09_mujoco_ros \
  --packages-select week09_mujoco_ros
source ~/week9/install/setup.bash
ros2 pkg executables week09_mujoco_ros
```

`Summary: 1 package finished`와 실행 파일 4개 등록을 확인한다. Jetson에서는 `arm_io`만 실행한다.
PC와 Jetson은 각각 자기 장비에서 빌드한 `install`을 사용한다. 설치 폴더의 `install/week09_mujoco_ros`는 빌드 도구가 만든 결과이므로 소스 폴더 중첩과 다르다.
`arm_io`가 `yaml`이나 SDK를 찾지 못하면 1.2절처럼 Jetson 실행 Python의 import를 확인한다.

---

## 6. MuJoCo 단독 제어

### 6.1 모델 구조 확인

PC 터미널에서 실행한다.

```bash
cd ~/week9/week09_mujoco_ros
source ~/week9/.venv/bin/activate
python3 mujoco_lab.py inspect
```

`njnt=8`, `nq=20`, `nv=18`, `nu=6`, `timestep=0.0020 s`를 확인한다.
로봇 회전 관절 6개와 큐브 자유관절 `object_cube_free`, `target_cube_free` 2개를 구분한다.
자유관절은 로봇 각도 하나가 아니라 XYZ·Quaternion·속도 배열로 출력된다.
파일 참조 오류가 나면 models와 assets 전체가 복사되었는지 확인한다.

### 6.2 정상 목표

```bash
python3 mujoco_lab.py run --joint shoulder_pan --target 0.30 --duration 5
```

WSLg Viewer가 열리고 qpos 로그가 바뀌는 것을 확인한다.
화면에는 한 변 25 mm의 초록·파랑 큐브 두 개가 함께 보인다. 두 큐브는 고정 배경이 아니라 중력·접촉의 영향을 받는 자유 물체이다.
실행 로그의 `robot_qpos`는 전체 20개 상태가 아니라 로봇 6관절만 표시한다.
0.30 rad는 Actuator 목표이며 물리 상태가 즉시 그 값으로 바뀌는 것은 아니다.
화면이 뜨지 않으면 조교에게 알린다. 임시 비GUI 진단은 다음 명령으로 구분한다.

```bash
python3 mujoco_lab.py run --joint shoulder_pan --target 0.30 --duration 1 --no-viewer
```

비GUI 성공만으로 Viewer 확인까지 완료한 것으로 간주하지 않는다.

### 6.3 범위 밖 목표

```bash
python3 mujoco_lab.py run --joint shoulder_pan --target 3.0 --duration 2
```

허용 범위 밖이라는 오류와 비정상 종료 코드가 기대 결과이다. 이 명령은 PC 시뮬레이션 전용이다.
실제 로봇에 3.0 rad를 보내는 명령으로 바꾸지 않는다.

### 6.4 실습 2의 다관절 자세를 PC에서 미리보기

ROS 연동 노드를 띄우기 전에 같은 PC 터미널에서 실행한다. 이 프로그램은 ROS 목표를 보내지 않으며 실제 로봇은 움직이지 않는다.

```bash
python3 mujoco_lab.py sequence --segment-duration 3
```

`config/comparison_poses.yaml`의 A → B → A를 화면에서 확인한다. 시작은 A로 설정하며 베이스·팔·손목·그리퍼가 함께 변한다.
창 제목은 `Week09 PhysicAI Arm`이다. 몸체·모니터·탑카메라 지지대도 표시된다. 몸체가 안 보이면 최신 `physicai_arm.xml`의 `workstation_visual`이 `group="2"`인지, Viewer에서 group 2 표시를 껐는지 확인한다.

---

## 7. ROS 노드 실행과 PC–Jetson 통신

### 7.1 조별 통신 설정

4주차에서 사용한 **`<각 조의 ID>`**를 그대로 사용한다. 공통 예시 숫자를 복사해서 사용하지 않는다.
아래 실행 블록의 `export ROS_DOMAIN_ID="<각 조의 ID>"`는 **복사하기 전에 따옴표 안을 배정받은 숫자로 교체**한다.
꺾쇠괄호와 설명 문구를 그대로 입력하지 않는다. 같은 조의 PC와 Jetson **모든 실행·명령 터미널**에 같은 값을 사용한다.

| 설정 | 이번 실습에서의 의미 |
|---|---|
| `ROS_DOMAIN_ID` | 같은 조의 ROS 노드가 서로 발견되도록 맞추는 값이다. 다른 조와 겹치지 않게 한다. |
| `ROS_LOCALHOST_ONLY=0` | 자기 장비 안에서만 통신하도록 제한하지 않는다. |
| `RMW_IMPLEMENTATION=rmw_fastrtps_cpp` | PC와 Jetson에서 같은 Fast DDS 구현을 사용한다. |

터미널의 `export`는 그 터미널에서 **이후 실행하는 프로세스**에 적용된다.
이미 실행 중인 노드의 Domain ID는 바뀌지 않는다. 설정을 바꾸었다면 노드도 종료 후 재실행한다.
새 터미널마다 ROS 기본 환경 → 해당 장비의 workspace 환경 → 조별 통신 설정을 다시 적용한다.
PC에서 venv를 사용할 때도 ROS 기본 환경을 먼저 적용한다.

WSL의 ROS CLI daemon은 노드·Topic 목록 조회를 돕는 백그라운드 프로세스이다.
설정을 변경할 때는 **변경 전 `timeout 10s ros2 daemon stop` → 새 설정 적용 → `timeout 10s ros2 daemon start`** 순서로 갱신한다.
아래 PC 터미널 1 블록에 이 순서를 포함했다. [ROS 2 daemon 구현](https://github.com/ros2/ros2cli/blob/humble/ros2cli/ros2cli/daemon/__init__.py)
daemon 시작은 네트워크 연결을 만드는 작업이 아니므로 1.0절도 준비되어 있어야 한다.
`timeout 10s`는 명령이 10초 이상 대기할 때 종료하도록 한다. stop이 시간 초과하면 같은 명령을 계속 기다리지 말고 새 Domain 설정 후 start를 시도한다. start도 실패하면 `ros2 node list --no-daemon`과 실제 Topic·Service로 통신을 구분하고 조교에게 로그를 전달한다. 시간 초과 자체를 통신 성공으로 간주하지 않는다.

실습에는 다음 세 터미널을 사용한다.

| 터미널 | 실행 위치 | 용도 |
|---|---|---|
| Jetson 터미널 1 | Jetson 로컬 터미널 | `arm_io`를 계속 실행한다. |
| PC 터미널 1 | WSL Ubuntu | 실제 상태 수신 확인 후 Bridge와 Comparator를 계속 실행한다. |
| PC 터미널 2 | WSL Ubuntu | Topic 조회·Service 호출·목표 발행을 수행한다. |

앞선 단독 MuJoCo Viewer를 종료한 뒤 진행한다. 실행 중인 Jetson·PC 터미널 1을 닫지 않는다.

### 7.2 Jetson 터미널 1 — 실제 로봇

Jetson 화면에서 로컬 터미널을 열어 아래 명령을 실행한다.

```bash
cd ~/week9
source ~/ros2_base/install/setup.bash
source ~/week9/install/setup.bash
export ROS_DOMAIN_ID="<각 조의 ID>"
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
printenv ROS_DOMAIN_ID ROS_LOCALHOST_ONLY RMW_IMPLEMENTATION
ros2 run week09_mujoco_ros arm_io
```

`Publishing measured positions on /real/joint_states`, `Torque service: /robot/set_torque`,
`Servo torque is disabled on startup` 로그를 확인한다.
읽기 실패가 반복되면 토크를 켜지 않고 장치 연결을 확인한다.

### 7.3 PC 터미널 1 — Bridge와 Comparator

WSL에서 새 터미널을 열어 실행한다. Domain ID를 방금 Jetson에서 사용한 것과 같은 조별 ID로 바꾼다.

```bash
cd ~/week9
source /opt/ros/humble/setup.bash
source ~/week9/install/setup.bash
source ~/week9/.venv/bin/activate
timeout 10s ros2 daemon stop
export ROS_DOMAIN_ID="<각 조의 ID>"
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
timeout 10s ros2 daemon start
printenv ROS_DOMAIN_ID ROS_LOCALHOST_ONLY RMW_IMPLEMENTATION
ros2 node list
ros2 topic echo --once /real/joint_states sensor_msgs/msg/JointState
```

이때 PC Launch는 아직 실행하지 않았다. `/arm_io`가 보이고 `name`·`position`에 6개 관절값이 한 번 출력되어야 한다.
이는 **Jetson → PC 실제 상태 수신** 확인이다. 계속 대기하면 `Ctrl+C`로 조회만 종료하고 7.5절을 확인한다.
단지 Topic 이름만 보이는 것과 실제 메시지가 도착하는 것은 구분한다.

수신에 성공했다면 같은 PC 터미널 1에서 Launch를 실행한다.

```bash
ros2 launch week09_mujoco_ros mujoco_compare.launch.py
```

제공 Launch는 두 PC 노드에 `~/week9/.venv/bin/python3`를 명시한다. `ros2` 명령 자체가 시스템 Python을 사용해도 정상이다.
다른 위치의 venv를 사용한다면 `ros2 launch ... python_executable:=/실제/venv/bin/python3`처럼 절대 경로를 지정한다.
PC 노드를 `ros2 run week09_mujoco_ros mujoco_ros_bridge`로 직접 실행하면 이 Launch 설정을 거치지 않으므로 실습에서는 위 Launch를 사용한다.

Viewer가 열리고 `MuJoCo loaded: nq=20, nv=18, nu=6`와 비교 노드의 `Waiting for ...` 로그를 확인한다.
Publisher·Subscriber 생성 중 인자 누락에 따른 `TypeError`가 나면 PC의 TODO 3·4와 인자 사이 쉼표를 확인한다.
진단용 `show_viewer:=false` 옵션은 GUI 실습을 대체하지 않는다.

### 7.4 PC 터미널 2 — 상태와 Service 확인

새 터미널이므로 환경을 다시 적용한다. 이후 Service와 목표 명령은 이 터미널에서 실행한다.

```bash
cd ~/week9
source /opt/ros/humble/setup.bash
source ~/week9/install/setup.bash
source ~/week9/.venv/bin/activate
export ROS_DOMAIN_ID="<각 조의 ID>"
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
timeout 10s ros2 daemon start
printenv ROS_DOMAIN_ID ROS_LOCALHOST_ONLY RMW_IMPLEMENTATION
ros2 node list
ros2 topic list -t
ros2 topic echo --once /real/joint_states sensor_msgs/msg/JointState
ros2 topic echo --once /sim/joint_states sensor_msgs/msg/JointState
ros2 service list -t
```

다음 세 노드와 상태 Topic·Service를 확인한다. 기본 parameter Service 등 다른 항목이 함께 보이는 것은 정상이다.

```text
노드
  /arm_io
  /mujoco_ros_bridge
  /real_sim_comparator
상태 Topic (둘 다 sensor_msgs/msg/JointState)
  /real/joint_states
  /sim/joint_states
Service
  /robot/set_torque       [std_srvs/srv/SetBool]
  /sim/set_follow_real    [std_srvs/srv/SetBool]
  /sim/sync_to_real       [std_srvs/srv/Trigger]
```

두 상태의 `name`·`position`에 6개 관절값이 있는지 확인한다. 상태 조회가 계속 대기하면 `Ctrl+C`로 **조회만** 취소한다.
`/sim/joint_states`는 PC 내부 통신이므로 이것만 보인다고 Jetson과 연결된 것은 아니다.

실제 로봇을 받친 상태에서 다음 **토크 OFF** 요청을 보낸다. 통신 확인을 위해 토크를 켜지 않는다.

```bash
ros2 service call /robot/set_torque std_srvs/srv/SetBool "{data: false}"
```

`success: true` 응답은 **PC → Jetson 요청과 Jetson → PC 응답**이 모두 전달되었다는 확인이다.
실제 상태 수신과 이 OFF 응답까지 성공한 뒤 8절로 진행한다.
Service가 보이지 않거나 `waiting for service`가 계속되면 `Ctrl+C`로 취소하고 7.5절을 확인한다.
`success: false`는 연결은 되었지만 요청 처리에 실패한 것이므로 Jetson 로그와 응답의 `message`를 확인한다.

### 7.5 연결되지 않을 때 확인할 순서

1. **장비와 실행 상태:** Jetson 터미널 1의 `arm_io`가 종료되지 않았는지 확인한다. 시리얼 읽기 오류가 반복되면 네트워크보다 로봇 연결·포트 점유부터 해결한다.
2. **조별 설정:** 각 터미널에서 `printenv ROS_DOMAIN_ID ROS_LOCALHOST_ONLY RMW_IMPLEMENTATION`을 실행해 같은 조별 ID, `0`, `rmw_fastrtps_cpp` 순서로 나오는지 비교한다. 잘못된 설정으로 시작한 노드는 종료 후 다시 실행한다.
3. **WSL daemon:** PC 터미널 1·2의 ID가 같은지 확인한다. 올바른 설정에서 `timeout 10s ros2 daemon stop`, `timeout 10s ros2 daemon start` 후 `ros2 node list`를 다시 조회한다. 필요하면 `ros2 node list --no-daemon`과 비교한다.
4. **기본 네트워크:** 1.0절의 유선 IP·서브넷·Ping을 다시 확인한다. IP 설정이 맞는데 ROS가 안 되면 4주차의 mirrored networking·Windows/Hyper-V 방화벽 설정과 UDP/multicast 전달을 확인한다.
5. **상태와 Service를 구분:** Topic 이름은 보여도 메시지가 없을 수 있다. `/real/joint_states` 실제 수신과 `/robot/set_torque` OFF 성공을 각각 확인한다. Service는 요청·응답 양방향이 모두 필요하다.

Jetson 내부에서 실제 상태가 발행되는지 구분하려면 **추가 Jetson 터미널**에 7.2절의 환경 설정까지만 적용하고 아래 조회를 실행한다.
`arm_io`를 한 개 더 실행하지 않는다.

```bash
ros2 topic echo --once /real/joint_states sensor_msgs/msg/JointState
```

Jetson에서는 수신되는데 PC에서만 안 되면 네트워크·DDS 설정을 우선 확인한다.
양쪽에서 ROS 환경을 적용했는데도 서로 발견되지 않으면 다음 multicast 진단을 사용할 수 있다.

| 확인 방향 | 먼저 실행해 대기할 수신 터미널 | 그다음 송신 터미널 |
|---|---|---|
| Jetson → WSL | 추가 WSL 터미널: `ros2 multicast receive` | 추가 Jetson 터미널: `ros2 multicast send` |
| WSL → Jetson | 추가 Jetson 터미널: `ros2 multicast receive` | 추가 WSL 터미널: `ros2 multicast send` |

수신 측에서 `Hello World!`가 보이는지 확인하고 `Ctrl+C`로 종료한다.
이 진단은 multicast 전달 확인이며 조별 Domain ID·DDS 전체 통신 검증을 대신하지 않는다. 여러 NIC가 있으면 CLI 진단이 원하는 유선 경로를 사용하지 않을 수 있다. Ping·multicast 진단 실패만으로 ROS 통신 실패를 단정하지 않고 실제 상태 수신과 OFF Service 응답을 함께 확인한다.
문제를 조교에게 전달할 때는 양쪽 IP, 위 환경 변수 3개, 마지막 오류 로그, 실패한 단계(목록 조회·실제 상태 수신·OFF 응답)를 함께 전달한다.

---

## 8. 실습 1 — 실제 자세를 MuJoCo에 복사

실제 로봇을 받친 상태에서 PC 터미널 2에 입력한다.

```bash
ros2 service call /robot/set_torque std_srvs/srv/SetBool "{data: false}"
ros2 service call /sim/set_follow_real std_srvs/srv/SetBool "{data: true}"
```

두 Service의 `success: true`를 확인한다. 실제 로봇을 천천히 움직이고 Viewer의 자세 변화를 관찰한다.
이때는 실제 자세를 `qpos`·`ctrl`에 복사하며 독립적인 물리 응답을 비교하지 않는다.
물리 스텝을 멈추는 추종 모드에서는 큐브 운동도 일시 정지한다. 추종을 끄면 큐브의 물리 운동을 다시 진행한다.
모델 범위 밖의 실제값은 범위 안으로 제한되어 표시된다.
추종 중 공통 목표를 보내지 않는다. 시뮬레이션은 이를 거부하며, 실제 토크 상태에 따라 위험할 수 있다.

관찰 후 추종을 끈다.

```bash
ros2 service call /sim/set_follow_real std_srvs/srv/SetBool "{data: false}"
```

`success: true`와 추종 종료 메시지를 확인한다.

---

## 9. 실습 2 — 동일 목표 응답 비교

### 9.1 여러 관절의 자세 A·B 확인

실습 2는 **자세 A에서 자세 B로 6관절 목표를 한 번에 변경**한다. 한 관절만 조금 움직이는 대신 베이스·팔·손목·그리퍼의 변화를 함께 관찰한다.
설정은 `config/comparison_poses.yaml`에 있으며 PC 단독 `sequence` 미리보기도 같은 파일을 읽는다.

| 관절 | 준비 자세 A [rad] | 비교 목표 B [rad] | 이동량 크기 |
|---|---:|---:|---:|
| shoulder_pan | 0.00 | 0.65 | 약 37° |
| shoulder_lift | -0.50 | -0.85 | 약 20° |
| elbow_flex | 0.80 | 1.15 | 약 20° |
| wrist_flex | 0.40 | 0.05 | 약 20° |
| wrist_roll | 0.00 | 0.80 | 약 46° |
| gripper | 0.20 | 0.65 | 약 26° |

| 자세 A 미리보기 | 자세 B 미리보기 |
|---|---|
| ![자세 A](images/pose_a.png) | ![자세 B](images/pose_b.png) |

각도 범위와 기존 관절별 속도 제한은 유지한다. 목표 요청을 함께 받는다는 뜻이며 모든 관절이나 실제·시뮬레이션이 같은 시각에 도착한다는 뜻은 아니다.
시뮬레이션 미리보기는 6.4절에서 먼저 확인한다. 이 자세는 수업용 예시이며, 실제 장비의 영점·설치물·케이블·기구 간섭까지 보장하는 경로가 아니다. 조교는 실제 장비에서 A·B와 그 사이 이동 공간을 확인한다.

PC 터미널 2에서 숫자를 확인한다. **`--send`가 없으면 목표를 발행하지 않는다.**

```bash
ros2 run week09_mujoco_ros comparison_goal --pose B
```

### 9.2 실제 로봇을 자세 A로 준비

추종이 OFF이고 두 상태가 계속 들어오는지 확인한다. 실제 로봇을 편하고 간섭 없는 자세로 받친 뒤 현재 자세 유지 토크를 켠다. 모든 관절을 억지로 0으로 만들지 않는다.

```bash
ros2 service call /sim/set_follow_real std_srvs/srv/SetBool "{data: false}"
ros2 service call /robot/set_torque std_srvs/srv/SetBool "{data: true}"
```

`success: true`와 현재 자세 유지 메시지를 확인한다. 제공 코드는 최신 실측값을 읽어 **모든 서보의 현재 자세 목표를 먼저 기록한 뒤 토크를 켠다.** 목표 기록이나 모드 확인이 실패하면 토크 ON 성공으로 처리하지 않는다.
갑작스러운 이동이 있으면 OFF 절차를 먼저 수행한다.

정상적으로 자세가 유지되면 손과 물체를 작업 반경에서 치운다. 다음 명령은 **실제 로봇도 자세 A로 움직이는 준비 명령**이다.

```bash
ros2 run week09_mujoco_ros comparison_goal --pose A --send
```

제공 도구는 최신 실제·시뮬레이션 6관절 상태와 구독 노드 3개를 확인하고, 추종 OFF 성공 후 PC timestamp가 담긴 목표를 한 번 보낸다. 토크를 자동으로 켜거나 끄지는 않는다.
자세 A 준비도 Comparator에는 하나의 목표이므로 8초 기록이 생성된다. **A의 `Trial saved`까지 기다리고**, 로봇이 자세를 유지하는지 확인한다. 준비 회차와 다음 B 비교 회차의 파일 시각을 구분한다.

### 9.3 동기화 후 자세 B를 한 번 발행

실제 로봇이 A에서 안정되면 PC 터미널 2에서 MuJoCo 시작 자세를 맞춘다.

```bash
ros2 service call /sim/sync_to_real std_srvs/srv/Trigger "{}"
ros2 topic info /joint_targets --no-daemon
```

동기화의 `success: true`와 Subscription count `3`을 확인한다. 구독자는 `arm_io`, Bridge, Comparator이다.
다른 조의 노드나 이전 Controller가 보이면 종료·Domain 설정을 확인한다.
동기화는 로봇 6관절의 위치·속도만 맞추며 큐브 상태와 모든 물리 조건까지 동일하게 만들지는 않는다.

작업 반경이 비어 있고 실제 로봇이 A를 유지하는 상태에서 비교 목표를 한 번 보낸다.

```bash
ros2 run week09_mujoco_ros comparison_goal --pose B --send
```

B 명령은 실제·시뮬레이션의 시작값이 모두 A의 각 관절 ±0.15 rad 안인지 확인한다. 다르면 목표를 보내지 않고 A 준비·동기화를 다시 하도록 안내한다.
두 제어 노드의 목표 수락 로그와 `Trial started ... recording 8.0 s`를 확인한다.
**8초 동안 새 목표를 보내지 않고**, PC 터미널 1의 B 회차 `Trial saved`까지 기다린다. 여섯 관절의 움직임과 두 응답 차이를 관찰한다. 추종 모드는 OFF를 유지한다.

**시뮬레이션이 순간이동처럼 빠르게 보일 때:** 실제 로봇은 `joints.yaml`의 관절별 속도 제한으로 목표에 접근하고, MuJoCo는 최종 목표를 position Actuator에 바로 전달한 뒤 `mj_step()`으로 움직인다. 현재 모델에서는 MuJoCo의 응답이 훨씬 빠르게 보일 수 있다. 같은 목표 각도를 받지만 이동 속도·경로·도착 시각까지 같아지는 실습은 아니다. 결과 그래프의 초기 구간에서 시뮬레이션의 이동과 진동을 확인한다.

앞서 실행한 `sync_to_real`은 **이동 전 시작 자세를 한 번 즉시 복사**하는 명령이다. 이후 B 목표 이동은 자세를 복사하지 않고 물리 계산을 진행한다. 실습 1의 실시간 추종과 이 두 동작을 구분한다.

`comparison_goal`은 발행 직전 PC 시각을 `header.stamp`에 넣는다. Comparator는 최근 2초의 수신 이력에서 **목표 발행 이전 상태를 0초 기준값**으로 가져와, 목표 callback이 늦게 처리되어도 시뮬레이션의 초기 응답을 보존한다.
직접 `ros2 topic pub`로 timestamp가 0인 목표를 보내면 callback 수신 시각으로 기록하며 경고한다. 필수 비교 회차는 위 도구로 수행한다.

### 9.4 결과와 무효 회차

PC 터미널 2에서 확인한다.

```bash
ls -lh ~/week9/results
```

이번 시각의 `trial_*.csv`, `trial_*.png`, `trial_*_metrics.yaml` 세 파일을 확인한다.
PNG는 WSL의 파일 탐색 위치나 PC 이미지 뷰어에서 열어 확인한다.
YAML은 B 비교 회차의 실제 파일 이름을 사용한다. `active_joints`에 6관절과 `time_origin: pc_target_header_stamp`가 있는지 확인한다.

```bash
cat "$HOME/week9/results/<이번회차파일명>_metrics.yaml"
```

`Trial invalid`가 나오면 해당 회차는 저장하지 않는다. 과거 파일을 이번 결과로 착각하지 않는다.

- 상태가 0.5초 이상 끊겼다면 통신과 두 상태 Publisher를 확인한다.
- 기록 중 새 목표를 보냈다면 실제 로봇에는 새 목표가 적용될 수 있다. Comparator의 무효 처리는 정지 명령이 아니다.
- 로봇이 정지하고 상태 수신이 정상인지 확인한 뒤 시작 자세를 다시 맞추고 다른 목표를 한 번만 보내 재실험한다.
- 상태가 없거나 오래되면 기록을 시작하지 않는다. 부분 관절 메시지만으로는 전체 상태 준비가 완료되지 않는다.

### 9.5 결과 해석 기록

| 항목 | 기록할 내용 |
|---|---|
| 명령한 관절과 목표 | 6관절의 A·B 값과 이동량을 기록한다. |
| 실제·시뮬레이션 시작값 | 두 시작각이 비슷한지 확인한다. |
| 실제–시뮬레이션 RMSE | YAML의 `real_vs_sim_rmse_rad`를 기록한다. |
| 지연 차이 | `real_minus_sim_response_delay_ms`의 값과 부호를 기록한다. |
| 곡선 차이 | 어느 쪽이 빨리 움직이는지, 진동·잔차가 있는지 기록한다. |
| 가능한 원인 두 가지 | 속도 제한·서보 내부 제어·통신·발행 주기·마찰·PC 부하 등에서 설명한다. |

시간 0초는 PC에서 목표를 발행한 timestamp이고 상태 시간은 PC 수신 기준이다. YAML의 `time_origin: pc_target_header_stamp`와 `target_callback_delay_s`를 확인한다. 장치 동작 시각을 정밀 동기화한 것은 아니므로 순수한 모터 지연으로 해석하지 않는다.
RMSE는 실제값과 시뮬레이션값의 차이이며 목표 추종 오차와 다르다.
관절마다 세로축 배율이 다르다. `1e-6`이나 `+4e-1` 같은 축의 배율·오프셋 표시가 있으면
작은 각도 차이를 확대해 보여 주는 것이므로 선의 높이만으로 다른 관절의 오차 크기를 비교하지 않는다.
지표는 명령한 관절에 대해 계산한다. 명령하지 않은 관절의 target 선은 시작 실제값을 사용한 참고선이다.
`null` 또는 `N/A`는 8초 안에 해당 움직임·정착 조건이 관찰되지 않았음을 뜻할 수 있다.
특정 RMSE 이하가 되어야 완료되는 실습이 아니다.

---

## 10. 안전 종료

로봇을 받치고 PC 터미널 2에서 실행한다.

```bash
ros2 service call /sim/set_follow_real std_srvs/srv/SetBool "{data: false}"
ros2 service call /robot/set_torque std_srvs/srv/SetBool "{data: false}"
```

성공 응답을 확인한 뒤 PC Launch와 Jetson `arm_io` 터미널에서 각각 `Ctrl+C`를 누른다.
Jetson은 정상 종료 시에도 토크 해제와 시리얼 연결 정리를 시도한다.
강제 종료·전원 장애에서 정리 코드 실행을 보장하지 않는다.
통신 장애로 OFF Service가 전달되지 않으면 로봇을 받친 상태에서 Jetson 로컬 노드를 정상 종료한다.
현장 비상 절차를 따르며 목표를 추가로 보내 문제를 해결하려 하지 않는다.

Viewer를 닫는 것만으로 Bridge가 종료되지 않을 수 있다.
8초 기록 중 Comparator를 종료하면 진행 중 결과는 저장되지 않으므로 정상 회차 저장 후 종료한다.

---

## 11. 문제 해결

| 증상 | 확인할 내용 |
|---|---|
| venv 생성 실패·`ensurepip is not available` | 1.1절의 `sudo apt install python3.10-venv`를 적용하고 `/usr/bin/python3.10`으로 생성한다. |
| venv에서 `rclpy`·colcon import 실패 | ROS Humble 기본 환경을 먼저 적용하고 `pyvenv.cfg`의 `include-system-site-packages = true`와 Python 3.10을 확인한다. |
| PC 빌드 실패 | 4.2절의 시스템 Python·colcon과 `--base-paths`를 사용한다. 이전 빌드 캐시가 원인이면 4.4절에서 경로 확인 후 산출물을 정리한다. |
| Jetson 빌드 실패 | 5절의 소스 배치·Jetson ROS 기본 환경을 확인한다. PC에서 가져온 산출물은 `~/week9` 위치 확인 후 정리하고 Jetson에서 다시 빌드한다. |
| MuJoCo import 실패 | 2.2절에서 PC `.venv`에 requirements를 설치하고 `~/week9/.venv/bin/python3`로 import를 확인한다. |
| 단독 실행은 되는데 ROS 노드만 import 실패 | 수정된 제공 Launch를 배치·재빌드했는지, 두 노드의 `python_executable`이 PC venv를 가리키는지 확인한다. 4.1·7.3절 참고. |
| Launch에서 Python 실행 파일을 찾지 못함 | 기본 경로 `~/week9/.venv/bin/python3`가 존재하는지 확인한다. 다른 venv는 `python_executable`에 실제 절대 경로를 지정한다. |
| 목표 B가 발행되지 않음 | A 준비·기록 종료·동기화, 최신 6관절 상태, 구독 노드 3개를 확인한다. 목표값 확인만 할 때는 `--send` 없이 실행한다. |
| 창 제목이 예전 이름이거나 몸체가 안 보임 | 최신 scene.xml·physicai_arm.xml과 모델 재설치 여부를 확인한다. 몸체는 workstation_mesh이며 group 2가 표시되어야 한다. |
| 기록 시작부터 시뮬레이션이 목표 근처임 | comparison_goal로 PC timestamp를 넣고 `time_origin`을 확인한다. 두 상태 수신 후 2초 이상 기다린다. |
| Viewer가 열리지 않음 | WSLg·DISPLAY·OpenGL을 확인한다. 비GUI 성공을 GUI 완료로 처리하지 않는다. |
| XML·Mesh 오류 | models와 assets의 경로·대소문자·누락을 확인한다. |
| TODO 줄에서 ValueError·TypeError·SyntaxError | `### TODO ###`를 값이나 인자로 교체했는지, 인자의 순서·쉼표·괄호가 맞는지 확인한다. |
| 실행 파일이 없거나 Launch·모델을 찾지 못함 | TODO 5·6의 data_files·console_scripts 등록, 파일 배치, 재빌드와 install 환경 적용을 확인한다. |
| 장치 없음·권한 오류 | USB·장치명·다른 드라이버 점유를 확인하고 권한은 조교에게 요청한다. |
| IP·Ping은 정상인데 실제 상태가 PC에 안 보임 | 7.5절에서 Jetson 내부 상태 발행 → 조별 설정 → daemon → UDP/multicast·방화벽 순서로 구분한다. |
| Domain ID 변경 후 목록이 이상함 | 설정 변경 전 daemon을 stop하고 변경 후 start한다. 모든 터미널의 조별 ID를 맞추고 기존 노드도 재실행한다. |
| Topic은 보이지만 관절값이 안 나옴 | 이름 발견과 데이터 수신은 다르다. 7.5절의 Jetson 로컬 echo와 PC echo를 비교하고 Publisher 실행·네트워크를 확인한다. |
| Service 대기·응답 없음 | 7.4절의 토크 OFF 호출로 양방향 통신을 확인한다. `success: false` 응답이면 Jetson 로그·응답 message를 확인한다. |
| 추종·동기화가 실패함 | 최신 전체 6관절 실제 상태 수신을 확인한다. |
| 비교 시 MuJoCo가 실제 자세를 복사함 | follow 모드를 false로 바꾼다. |
| B 목표에서 MuJoCo가 순간이동처럼 보임 | 9.3절의 시작 자세 동기화와 목표 이동을 구분한다. MuJoCo는 물리 계산으로 빠르게 반응하며 실제 서보의 속도 제한 보간은 사용하지 않는다. 그래프 초기 구간을 확인한다. |
| 실제 로봇만 안 움직임 | 토크 ON 성공과 목표 수락 로그를 확인한다. |
| 결과 파일이 없음 | 최신 두 상태·Trial started·8초 기록·Trial invalid 로그를 확인한다. |
| 지연·정착 시간이 null | 충분한 목표 변화와 기록 중 움직임·정착 조건을 확인한다. |

---

## 12. 완료 체크리스트

- [ ] 코드 TODO 1~4를 완성하고 `ctrl`과 `mj_step()`의 역할을 설명한다.
- [ ] 등록 TODO 5~7을 완성하고 실행 파일 4개·설치 자산·실행 의존성을 확인한다.
- [ ] PC venv import와 Launch의 `python_executable` 경로를 확인한다.
- [ ] 모든 터미널에 같은 조별 Domain ID를 적용하고 WSL daemon을 갱신한다.
- [ ] Jetson 실제 상태를 PC에서 수신하고 토크 OFF Service의 성공 응답을 확인한다.
- [ ] 로봇 6관절·자유 큐브 2개·Actuator 6개를 구분하고 단일 관절 이동을 확인한다.
- [ ] 범위 밖 목표가 거부되는 것을 확인한다.
- [ ] 5주차와 달라진 상태 Topic과 토크 Service를 구분한다.
- [ ] 실제 토크 OFF에서 Real-to-Sim 추종을 확인한다.
- [ ] PC에서 A–B–A 미리보기를 확인하고, 실제 A 준비·동기화 후 B의 6관절 공통 목표 비교를 1회 수행한다.
- [ ] 이번 회차의 CSV·PNG·metrics YAML 세 파일을 확인한다.
- [ ] 지연·RMSE의 의미와 응답 차이의 원인 두 가지를 설명한다.
- [ ] 실제 토크 해제 성공을 확인하고 노드를 정상 종료한다.

---

