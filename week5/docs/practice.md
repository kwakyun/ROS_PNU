# [5주차] 관절 단위 위치제어와 자세 유지 — 실습 안내서

> `lecture.md`를 먼저 읽고 아래 실습을 순서대로 수행한다. 명령의
> `<배포자료경로>`는 `5주차 제공파일`이 저장된 실제 경로로 바꾼다.

## 0. 실습 전 안전 확인

- 목표 관절값의 단위는 degree가 아니라 radian이다.
- 제조사 Bringup과 이전 주차의 로봇 제어 노드를 정상 종료한다.
- 토크 활성화 전에 토크 해제 명령을 보낼 터미널을 준비한다.
- 자세 유지 중인 로봇을 손으로 억지로 밀거나 잡지 않는다.
- 이상 동작이 발생하면 목표값을 추가로 보내지 않고 토크 해제 명령을 먼저 보낸다.

이번 실습의 최종 동작은 다음과 같다.

```text
Controller·Plotter 실행 → 현재 관절값 확인, 토크 OFF
토크 활성화             → 현재 자세에서 위치 유지 시작
정상 요청값 전송         → 지정 관절이 속도 제한에 따라 이동
범위 밖 요청값 전송      → 요청 거부, 이전 자세 유지
토크 해제                → 위치 제어 중단
Plotter 종료             → CSV·PNG 저장
```

---

## 1. 환경과 장비 확인

Jetson에서 다음 명령을 실행한다.

```bash
source ~/ros2_base/install/setup.bash

python3 -c "import rclpy; print('rclpy OK')"
python3 -c "import yaml; print('PyYAML OK')"
python3 -c "import matplotlib; print('matplotlib OK')"
python3 -c "import vassar_feetech_servo_sdk; print('Feetech SDK OK')"

ls -l /dev/ttyACM0
```

다음 결과를 확인한다.

- 네 Python import 명령이 모두 `OK`를 출력한다.
- `/dev/ttyACM0`이 존재한다.

안된다면 조교 문의

---

## 2. Workspace와 패키지 생성

`~/week5`를 colcon workspace로 사용한다.

```bash
mkdir -p ~/week5
cd ~/week5
source ~/ros2_base/install/setup.bash

ros2 pkg create week05_joint_control \
  --build-type ament_python \
  --dependencies ament_index_python rclpy sensor_msgs std_msgs
```

이미 `week05_joint_control` 디렉터리가 있다면 `ros2 pkg create`를 다시 실행하지 않는다.

---

## 3. 제공 파일 배치와 최종 구조 확인

명령의 `<배포자료경로>`를 실제 `5주차 제공파일`의 경로로 바꾼 뒤 제공 파일을
패키지에 복사한다.

```text
week05_joint_control/
├── config/
│   └── joints.yaml
├── resource/
│   └── week05_joint_control
├── week05_joint_control/
│   ├── __init__.py
│   ├── hardware_interface.py
│   ├── joint_controller.py
│   └── joint_plotter.py
├── package.xml
├── setup.cfg
└── setup.py
```

복사한 파일의 역할은 다음과 같다.

| 파일 | 역할 |
|---|---|
| `hardware_interface.py` | Feetech 서보의 위치 읽기·쓰기와 토크 해제를 담당한다. |
| `joint_controller.py` | ROS 2 Topic, 안전 검사와 관절 제어 루프를 담당한다. |
| `joint_plotter.py` | 현재값·요청값 그래프와 CSV·PNG 저장을 담당한다. |
| `joints.yaml` | 관절 이름, Servo ID, Soft Limit, 최대 속도와 제어 주기를 정의한다. |

파일을 배치한 뒤 package가 다음 구조인지 확인한다.

---

## 4. Controller TODO 완성

`joint_controller.py`의 TODO 네 가지를 완성한다.

### 4.1 `/joint_states` Publisher

- 메시지 타입: `JointState`
- Topic: `/joint_states`
- QoS depth: `10`
- 반환된 Publisher를 `self._publisher`에 저장한다.

### 4.2 `/joint_targets` Subscriber

- 메시지 타입: `JointState`
- Topic: `/joint_targets`
- callback: `self._on_target`
- QoS: 제공된 `QoSProfile(depth=1)`을 사용한다.

### 4.3 `/safety/torque_enable` Subscriber

- 메시지 타입: `Bool`
- Topic: `/safety/torque_enable`
- callback: `self._on_torque`
- QoS depth: `10`

### 4.4 Soft Limit 검사

`joints.yaml`에서 읽은 `lower`, `upper`를 사용해 다음 조건을 만족하지 않는 값을
거부한다.

```text
lower <= pos <= upper
```

범위를 벗어나면 기존 오류 로그를 출력하고 즉시 `return`해야 한다. 여러 관절이 들어
있는 메시지에서 하나라도 검사에 실패하면 메시지 전체를 거부한다.

20 Hz State Timer, 30 Hz Control Timer와 실제 보간 코드는 이미 제공되어 있다.
`lecture.md`의 「Callback과 Timer의 제어 흐름」과 「속도 제한 보간」을 참고한다.

---

## 5. `setup.py`와 `package.xml` 수정

`week05_joint_control/setup.py` 상단에 다음 import를 추가한다.

```python
from glob import glob
import os
```

`data_files`에 Config 설치 항목을 추가한다.

```python
(os.path.join("share", package_name, "config"), glob("config/*.yaml")),
```

`install_requires`에 PyYAML을 추가한다.

```python
install_requires=["setuptools", "PyYAML"],
```

`console_scripts`에 두 진입점을 등록한다.

```python
"joint_controller = week05_joint_control.joint_controller:main",
"joint_plotter = week05_joint_control.joint_plotter:main",
```

`week05_joint_control/package.xml`에 Python 실행 의존성을 추가한다.

```xml
<exec_depend>python3-matplotlib</exec_depend>
<exec_depend>python3-yaml</exec_depend>
```

---

## 6. 빌드와 실행 파일 확인

패키지 내부가 아니라 workspace 최상위에서 빌드한다.

```bash
cd ~/week5
source ~/ros2_base/install/setup.bash

colcon build --symlink-install --packages-select week05_joint_control
source install/setup.bash

ros2 pkg executables week05_joint_control
```

다음 두 실행 파일이 표시되어야 한다.

```text
week05_joint_control joint_controller
week05_joint_control joint_plotter
```

빌드가 Python 구문 오류로 실패하면 `joint_controller.py`의 네 TODO가 모두 완성되었는지
먼저 확인한다. 새 터미널을 열거나 코드를 다시 빌드하면 ROS 2 환경과
`install/setup.bash`를 다시 불러온다.

---

## 7. Controller와 Plotter 실행 및 통신 확인

### 7.1 Controller 실행

터미널 1에서 실행한다.

```bash
cd ~/week5
source ~/ros2_base/install/setup.bash
source install/setup.bash
ros2 run week05_joint_control joint_controller
```

다음 로그를 확인한다.

```text
Servo torque disabled on startup
Joint controller ready on /joint_states & /joint_targets
```

이 시점에는 토크가 꺼져 있으므로 목표값을 보내지 않는다.

### 7.2 Plotter 실행

터미널 2에서 반드시 workspace로 이동한 뒤 실행한다. 이 위치에서 실행해야 결과가
`~/week5/results/`에 저장된다.

`joint_plotter`는 Matplotlib GUI 창을 띄우므로 SSH 터미널에서는 실행하지 않는다.
Jetson의 데스크톱 화면에서 연 로컬 터미널에서 실행한다. SSH에서 실행하면 GUI
디스플레이가 없어 그래프 창이 표시되지 않을 수 있다.

```bash
cd ~/week5
source ~/ros2_base/install/setup.bash
source install/setup.bash
ros2 run week05_joint_control joint_plotter
```

6개 관절 그래프와 파란 현재값 선을 확인한다. 주황 요청값 선은 첫 요청을 보낸 뒤
나타난다.

- 파란 실선 `current`: 실제 측정 관절값
- 주황 점선 `requested`: `/joint_targets`로 받은 원본 요청값

### 7.3 노드와 Topic 확인

터미널 3에서 확인한다.

```bash
cd ~/week5
source ~/ros2_base/install/setup.bash
source install/setup.bash

ros2 node list
ros2 topic list
ros2 node info /joint_controller
ros2 topic echo --once /joint_states
```

다음 노드와 Topic이 보여야 한다.

```text
/joint_controller
/joint_plotter

/joint_states
/joint_targets
/safety/torque_enable
```

---

## 8. 토크 활성화와 정상 목표 제어

### 8.1 토크 활성화

로봇 주변의 안전을 다시 확인한 뒤 터미널 3에서 한 번 발행한다.

```bash
ros2 topic pub --once /safety/torque_enable \
  std_msgs/msg/Bool "{data: true}"
```

Controller에서 다음 로그를 확인한다.

```text
Servo torque enabled; current pose is initial target
```

로봇이 다른 위치로 갑자기 이동하지 않고 명령을 보낸 순간의 자세를 유지해야 한다.

### 8.2 단일 관절 요청

```bash
ros2 topic pub --once /joint_targets \
  sensor_msgs/msg/JointState \
  "{name: ['shoulder_pan'], position: [0.5]}"
```

다음을 확인한다.

- Controller에 `Target accepted` 로그가 출력된다.
- `shoulder_pan`이 관절별 최대 속도 제한에 따라 이동한다.
- 명령하지 않은 관절은 이전 목표를 유지한다.
- Plotter의 파란 현재값이 주황 요청값을 추종한다.
- 목표에 도달하면 `Target reached` 로그가 한 번 출력된다.

### 8.3 다중 관절 요청

```bash
ros2 topic pub --once /joint_targets \
  sensor_msgs/msg/JointState \
  "{name: ['shoulder_pan', 'elbow_flex'], position: [0.2, 0.4]}"
```

`name`과 `position`의 같은 배열 위치가 한 관절의 이름과 요청값을 나타낸다. 두 관절이
각자의 최대 속도 제한에 따라 이동하는지 확인한다.

---

## 9. Soft Limit 거부 확인

`shoulder_pan`의 허용범위 약 `-1.92 ~ 1.92 rad`를 벗어난 값을 전송한다.

```bash
ros2 topic pub --once /joint_targets \
  sensor_msgs/msg/JointState \
  "{name: ['shoulder_pan'], position: [3.5]}"
```

다음 결과가 모두 나타나야 한다.

- Controller에 `shoulder_pan=3.5000 rad 명령 거부` 로그가 출력된다.
- 로봇은 `3.5 rad`로 이동하지 않고 이전에 수락한 자세를 유지한다.
- Plotter의 주황 `requested` 선은 원본 요청인 `3.5 rad`를 표시한다.
- 파란 `current` 선은 거부된 요청을 추종하지 않는다.

주황선은 수락된 Controller 목표가 아니라 명령 터미널이 보낸 원본 요청값이므로 범위
밖 값도 표시된다. 주황선과 파란선이 분리되고 거부 로그가 출력되는 것이 정상이다.

---

## 10. 토크 해제와 결과 저장

### 10.1 토크 해제

터미널 3에서 토크 해제 요청을 보낸다.

```bash
ros2 topic pub --once /safety/torque_enable \
  std_msgs/msg/Bool "{data: false}"
```

Controller의 `Servo torque disabled` 로그와 위치 제어 중단을 확인한다. 링크가 중력으로
내려올 수 있으므로 로봇을 안전하게 지지한다.

### 10.2 정상 종료

다음 순서로 종료한다.

1. Plotter 터미널에서 `Ctrl+C`를 눌러 CSV와 PNG를 저장한다.
2. Controller 터미널에서 `Ctrl+C`를 누른다.
3. `Servo torque disabled on shutdown` 로그가 출력되는지 확인한다.
4. 다음 명령으로 결과 파일을 확인한다.

```bash
ls -l ~/week5/results
```

CSV에는 각 관절의 `*_current`와 `*_requested` 열이 있어야 한다. Controller는 정상
종료 시 토크를 다시 해제하고 시리얼 연결을 닫는다.

---

## 11. 문제 해결

| 증상 | 우선 확인할 부분 |
|---|---|
| `Package 'week05_joint_control' not found` | `cd ~/week5`에서 빌드했는지, 현재 터미널에서 `source install/setup.bash`를 실행했는지 확인한다. |
| Python 구문 오류로 빌드 실패 | `joint_controller.py`의 네 TODO와 괄호·쉼표를 확인한다. |
| `No module named 'matplotlib'` | `python3 -c "import matplotlib; print('matplotlib OK')"`로 다시 확인하고 조교에게 문의한다. |
| `No module named 'yaml'` | `python3 -c "import yaml; print('PyYAML OK')"`로 다시 확인하고 조교에게 문의한다. |
| Feetech SDK import 실패 | `python3 -c "import vassar_feetech_servo_sdk; print('Feetech SDK OK')"`로 다시 확인하고 조교에게 문의한다. |
| `/dev/ttyACM0`이 없음 | USB 케이블, 서보 전원과 장치 연결을 확인한다. |
| `Permission denied: /dev/ttyACM0` | `ls -l /dev/ttyACM0`과 `groups`로 장치 권한과 `dialout` 그룹을 확인하고 조교에게 문의한다. |
| 시리얼 포트를 열 수 없음 | 제조사 Bringup이나 다른 로봇 노드가 포트를 사용 중인지 확인한다. |
| 토크 활성화 요청 후 제어되지 않음 | `/joint_states`가 발행되는지, Controller 오류 로그와 서보 전원을 확인한다. |
| 요청값이 거부됨 | radian 단위, 관절 이름, `joints.yaml`의 `limit_rad`를 확인한다. |
| 결과 파일을 찾을 수 없음 | Plotter를 `~/week5`에서 실행했는지와 `Ctrl+C`로 정상 종료했는지 확인한다. |

---

## 12. 실습 완료 체크리스트

- [ ] 네 개의 Controller TODO를 완성하고 패키지 빌드에 성공했다.
- [ ] Controller 시작 시 실제 토크가 해제되는 것을 확인했다.
- [ ] Plotter에서 6개 관절의 현재값과 요청값을 확인했다.
- [ ] 토크 활성화 시 현재 자세에서 급격한 이동이 발생하지 않았다.
- [ ] 단일·다중 관절 요청이 속도 제한에 따라 실행되었다.
- [ ] Soft Limit 밖 요청이 거부되고 현재 자세가 유지되었다.
- [ ] 토크 해제와 정상 종료 로그를 확인했다.
- [ ] `~/week5/results/`에서 CSV와 PNG를 확인했다.
