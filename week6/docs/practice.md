# [6주차] 게임패드 기반 말단부 제어와 FK/IK — 실습 안내서

> 게임패드 입력을 EEF 목표 자세로 변환하고, IK로 관절 목표를 생성하여 실제 로봇을
> 제어한 뒤 FK로 현재 자세를 확인한다.

## 0. 실습 전 안전 확인

실습을 시작하기 전에 다음 항목을 모두 확인한다.

- 로봇 작업 반경에서 사람, 케이블, 공구와 장애물을 치운다.
- `/dev/ttyACM0`을 사용하는 다른 로봇 프로그램을 종료한다.
- 게임패드의 축 번호가 다를 수 있으므로 처음에는 토크를 켜지 않고 `/joy`를 확인한다.
- 위치와 관절각의 단위는 각각 m와 radian임을 확인한다.
- 토크 해제 명령을 즉시 보낼 수 있는 별도 터미널을 준비한다.
- 토크가 활성화된 로봇을 손으로 억지로 밀지 않는다.
- 토크 해제 시 링크가 내려갈 수 있으므로 필요한 경우 로봇을 받친다.
- 실습 종료 시 토크 해제를 먼저 확인하고 Launch를 종료한다.

이번 실습은 관리자 권한을 사용하지 않는다. 필요한 패키지, Python 모듈 또는 장치
접근 권한이 없다면 임의로 설치하거나 권한을 변경하지 말고 조교에게 알린다.

---

## 1. 환경과 장비 확인

### 1.0 환경변수 설정
- `ROS_DOMAIN_ID`를 `.bashrc`에 설정하지 않으면 새 터미널에서 기본 Domain ID(= 0)를 사용한다. 그러면 동일한 네트워크에 있는 (다른 조)ROS 2 Node가 보이거나 명령이 다른 조의 Node에 전달될 수 있다. 또한 `ROS_DOMAIN_ID`가 다르게 설정된 터미널 끼리 통신이 이루어 지지 않을 수도 있다.

다음 명령어를 통해, .bashrc 파일을 열고,
```bash
gedit ~/.bashrc
```
파일 마지막에 다음 내용을 추가한다. `<조 번호>`는 실제 숫자로 바꾼다(예: 3조는 3).
``` bash
export ROS_DOMAIN_ID=<조 번호>
```
설정 저장 후, 기존 터미널 및 text-editor를 닫고 새 터미널을 열고 설정한 `ROS_DOMAIN_ID`가 제대로 출력되는지 확인한다.
```bash
echo $ROS_DOMAIN_ID
```
### 1.1 ROS 2와 Python 환경 확인

```bash
source ~/ros2_base/install/setup.bash

ros2 pkg prefix joy
ros2 run joy joy_enumerate_devices
python3 -c "import rclpy; print('rclpy OK')"
python3 -c "import numpy; print('NumPy OK')"
python3 -c "import yaml; print('PyYAML OK')"
python3 -c "import vassar_feetech_servo_sdk; print('Feetech SDK OK')"
```

각 명령이 패키지 경로, 연결된 게임패드 목록 또는 `OK`를 출력해야 한다. 기본 Launch는
`joy_enumerate_devices`가 표시하는 SDL 장치 ID `0`을 사용한다. 다른 ID를 사용해야
한다면 실행할 때 `device_id:=숫자`를 지정한다. `Package not found`나
`ModuleNotFoundError`가 출력되면 조교에게 알린다.

### 1.2 장치 파일과 접근 권한 확인

```bash
ls -l /dev/input/js0
ls -l /dev/ttyACM0
test -r /dev/input/js0 && echo "gamepad readable"
test -r /dev/ttyACM0 -a -w /dev/ttyACM0 && echo "serial readable/writable"
```

두 확인 문구가 출력되어야 한다. 장치가 없거나 읽기·쓰기 확인에 실패하면 케이블을
확인하고 조교에게 알린다.

---

## 2. Workspace와 패키지 생성

```bash
mkdir -p ~/week6
cd ~/week6
source ~/ros2_base/install/setup.bash

ros2 pkg create week06_ee_control \
  --build-type ament_python \
  --dependencies ament_index_python geometry_msgs launch launch_ros rclpy sensor_msgs std_msgs
```

---

## 3. 제공 파일 배치와 최종 구조 확인

구조가 다음과 같은지 확인한다.

```text
~/week6/
└── week06_ee_control/
    ├── config/
    │   └── joints.yaml
    ├── launch/
    │   └── joystick_arm_control.launch.py
    ├── resource/
    │   └── week06_ee_control
    ├── week06_ee_control/
    │   ├── __init__.py
    │   ├── arm_driver.py
    │   ├── ee_pose_listener.py
    │   ├── fk_solver.py
    │   ├── hardware_interface.py
    │   ├── ik_solver.py
    │   ├── joystick_to_pose.py
    │   └── kinematics.py
    ├── package.xml
    ├── setup.cfg
    └── setup.py
```

### 3.1 5주차 Joint Controller에서 달라진 사용법

6주차의 `arm_driver.py`는 5주차 `joint_controller.py`의 하위 관절 제어 역할을
이어받는다. 두 노드는 `/joint_states`, `/joint_targets`,
`/safety/torque_enable`이라는 같은 인터페이스를 사용하지만 목표를 받는 방법은
다르다.

```text
5주차: 사용자가 관절 목표를 직접 발행
       → joint_controller

6주차: 게임패드가 EEF 목표 생성
       → ik_solver가 전체 관절 목표 계산
       → arm_driver
```

실습 중에는 다음 차이를 적용한다.

- `arm_driver.py`는 제공 코드이며 이번 주차의 TODO 대상이 아니다.
- 5주차에서는 관절 하나만 포함한 부분 목표를 보낼 수 있었지만, 6주차
  `arm_driver`에는 5개 arm joint와 `gripper`가 모두 포함되어야 한다.
- `/joint_targets`는 사용자가 한 번 보내는 명령이 아니라 `ik_solver`가 연속적으로
  발행하는 명령이다.
- 새로운 `/joint_targets`가 300 ms 동안 들어오지 않으면 `arm_driver`는 진행 중
  이동을 멈추고 마지막 명령 자세를 유지한다. 이 동작은 토크 해제가 아니다.
- 6주차는 상태 발행 50 Hz, 하드웨어 제어 100 Hz와 더 높은 관절 속도를 사용하므로
  처음에는 게임패드를 작은 범위로 천천히 조작한다.
- 연속 목표가 들어오므로 5주차의 `Target accepted`, `Target reached` 로그는 출력하지
  않는다. `/joint_targets`, `/joint_states`, `/ee_pose`를 확인하여 동작을 판단한다.

`arm_driver`는 IK나 EEF 자세를 직접 계산하지 않는다. IK 계산은 `ik_solver`, 현재
EEF 자세 계산은 `fk_solver`, 실제 모터 제어는 `arm_driver`가 담당한다.

---

## 4. `joystick_to_pose.py` TODO 완성

이 노드는 게임패드 입력을 저장하고 25 Hz Timer에서 EEF 목표를 발행한다. Publisher의 Queue depth는 10으로 하여, 다음 객체를 완성한다.

- `/target_pose` Publisher
- `/gripper_open` Publisher
- `/joy` Subscriber

실행 흐름은 다음과 같다.
```text
/joy → _on_joy()가 최신 axes/buttons 저장
     → 25 Hz _tick()이 목표 자세 누적
     → /target_pose와 /gripper_open 발행
```

`/joy` Subscriber의 `"/joy"`와 Queue depth `10`은 변경하지 않는다.

---

## 5. `ik_solver.py` TODO 완성

이 노드는 현재 관절 상태와 EEF 목표를 저장하고 60 Hz Timer에서 관절 목표를 발행한다. Publisher의 Queue depth는 10으로 하여, 다음 객체를 완성한다.

- `/joint_states` Subscriber
- `/target_pose` Subscriber
- `/gripper_open` Subscriber
- `/joint_targets` Publisher

실행 흐름은 다음과 같다.
```text
/joint_states ──> 현재 arm joint와 IK 초기값 저장 ─┐
/target_pose  ──> 목표 XYZ와 Pitch 저장           ├─> IK → /joint_targets
/gripper_open ──> 그리퍼 목표 상태 저장            ┘
```

---

## 6. Launch TODO 완성

`joystick_arm_control.launch.py`는 게임패드 입력부터 EEF 출력까지 필요한 6개 노드를 한 번에 실행한다. `DeclareLaunchArgument` 두 개는 이미 제공되므로 수정하지 않고, `TODO` 부분을 완성한다.

### 6.1 `joy_node`의 조건과 파라미터 연결

`joy_node`에는 `condition`과 `parameters` 구조도 제공된다.

- `condition`에는 `IfCondition`과 `start_joy` LaunchConfiguration을 연결한다.
- `parameters`에는 `device_id` LaunchConfiguration을 전달한다.

두 설정의 의미는 다음과 같다.
```text
start_joy:=true  → Launch가 joy_node를 실행한다.
start_joy:=false → 외부에서 실행한 joy_node 또는 수동 /joy 입력을 사용한다.

device_id:=0     → joy_enumerate_devices의 SDL 장치 0번을 사용한다.
```

`condition`과 `parameters`는 `joystick_to_pose`를 비롯한 나머지 5개 Node에는 추가하지 않는다.

### 6.2 Launch 구성 확인

완성한 `LaunchDescription`의 목록에는 DeclareLaunchArgument 2개, Node 6개가 있어야 한다.

---

## 7. `setup.py`와 `package.xml` 수정

### 7.1 `setup.py`

파일 위쪽에 다음 import를 추가한다.

```python
from glob import glob
import os
```

`data_files`에 Config와 Launch 설치 항목을 추가한다.

```python
(os.path.join("share", package_name, "config"), glob("config/*.yaml")),
(os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
```

`install_requires`를 다음과 같이 수정한다.

```python
install_requires=["setuptools", "numpy", "PyYAML"],
```

`console_scripts`에 arm_driver, joystick_to_pose, ik_solver, fk_solver, ee_pose_listener 다섯 항목을 등록한다.

### 7.2 `package.xml`

`<package>` 내부에 다음 실행 의존성을 추가한다.

```xml
<exec_depend>joy</exec_depend>
<exec_depend>python3-numpy</exec_depend>
<exec_depend>python3-yaml</exec_depend>
```

---

## 8. 빌드와 실행 파일 확인

```bash
colcon build --symlink-install --packages-select week06_ee_control
source install/setup.bash

ros2 pkg executables week06_ee_control
```

빌드가 성공하고 다음 실행 파일 다섯 개가 표시되어야 한다.

```text
week06_ee_control arm_driver
week06_ee_control ee_pose_listener
week06_ee_control fk_solver
week06_ee_control ik_solver
week06_ee_control joystick_to_pose
```

`setup.py` 또는 Python 코드를 수정한 뒤에는 다시 빌드하고
`source ~/week6/install/setup.bash`를 실행한다.

---

## 9. 토크 없이 게임패드 입력 확인

전체 Launch를 실행하기 전에 게임패드의 실제 축과 버튼 배열을 확인한다.

터미널 1:

```bash
ros2 run joy joy_node
```

터미널 2:

```bash
ros2 topic echo /joy
```

확인이 끝나면 두 터미널에서 `Ctrl+C`를 눌러 단독 실행 노드를 종료한다. 통합 Launch가
`joy_node`를 다시 실행하므로 단독 노드가 남아 있으면 안 된다.

---

## 10. 전체 파이프라인 실행과 상태 확인

터미널 1:

```bash
ros2 launch week06_ee_control joystick_arm_control.launch.py
```

게임패드의 SDL 장치 ID가 `0`이 아니라면 다음과 같이 실행한다.

```bash
ros2 launch week06_ee_control joystick_arm_control.launch.py device_id:=1
```

정상 실행 시 `arm_driver`에서 시작 시 토크가 해제되었다는 로그가 출력되고,
`ee_pose_listener`에서 다음 형식의 로그가 반복 출력된다.

```text
frame=base_link | XYZ=(..., ..., ...) m | Q=(..., ..., ..., ...) | pitch=... rad
```

터미널 2:

```bash
ros2 node list
```

다음 노드가 표시되어야 한다.

```text
/joystick_pub_node
/joystick_to_pose
/ik_solver
/arm_driver
/fk_solver
/ee_pose_listener
```

`/joy`, `/target_pose`, `/gripper_open`, `/joint_targets`, `/joint_states`, `/ee_pose`,
`/safety/torque_enable` Topic이 표시되어야 한다. 이 단계에서도 토크는 꺼진 상태이다.

---

## 11. 토크 활성화와 EEF 제어

### 11.1 토크 활성화

로봇 주변이 비어 있고 토크 해제 터미널이 준비되었는지 다시 확인한다. 터미널 2에서
다음 명령을 실행한다.

```bash
ros2 topic pub --once /safety/torque_enable std_msgs/msg/Bool "{data: true}"
```

다음 로그가 출력되고 로봇이 현재 자세를 유지해야 한다.

```text
Servo torque enabled; current pose is the initial hold target
```

활성화 직후 로봇이 갑자기 크게 움직이면 즉시 토크 해제 명령을 보내고 관절 설정을
확인한다.

### 11.2 게임패드 제어

스틱을 작은 범위로 천천히 움직이며 다음 동작을 확인한다. (매핑은 정확하게 동일하지 않읋 수 있으나, 모든 축에 대한 조작은 가능해야함)

- 왼쪽 스틱 상하: EEF X 방향 이동
- 왼쪽 스틱 좌우: EEF Y 방향 이동
- 왼쪽 + 모양 버튼 : EEF Z 방향 이동
- 오른쪽 스틱 좌우: EEF Pitch 변경
- B 버튼: Gripper 열림·닫힘 전환

IK가 목표를 찾지 못하면 다음과 같은 경고가 출력되고 해당 목표는 발행되지 않는다.

```text
IK target rejected: position error=... m
```

이는 작업 공간 제한 안에 있어도 현재 수치 IK가 허용 오차 안의 해를 찾지 못했다는
뜻이다. 스틱을 반대 방향으로 천천히 움직여 도달 가능한 목표로 돌아온다.

---

## 12. Topic 흐름과 FK 결과 확인

필요한 Topic을 한 번에 하나씩 확인한다.

```bash
ros2 topic echo /target_pose
ros2 topic echo /gripper_open
ros2 topic echo /joint_targets
ros2 topic echo /joint_states
ros2 topic echo /ee_pose
```

정상 결과는 다음과 같다.

- 스틱 조작에 따라 `/target_pose`의 위치 또는 자세가 변한다.
- A 버튼을 누를 때마다 `/gripper_open`의 `data`가 바뀐다.
- IK가 성공하면 `/joint_targets`에 5개 arm joint와 `gripper`가 포함된다.
- `/joint_states`에는 실제 서보에서 읽은 같은 6개 관절이 포함된다.
- `/ee_pose`는 `/joint_states`에 FK를 적용한 현재 EEF 자세를 나타낸다.

`/target_pose`와 `/ee_pose`는 각각 목표 자세와 측정값 기반 현재 자세이므로 순간적으로
차이가 날 수 있다.

---

## 13. 입력 단절과 토크 해제 확인

### 13.1 입력 단절 동작

로봇이 안전한 자세에 있을 때 게임패드 USB를 분리하거나 `joy_node`만 중단하여 새
`/joy` 메시지가 들어오지 않게 한다. 단순히 스틱을 놓으면 중립 메시지가 계속 발행될
수 있으므로 타임아웃 시험이 되지 않는다.

정상 동작은 다음과 같다.

1. 0.50초 후 `joystick_to_pose`가 경고를 한 번 출력하고 새 `/target_pose` 발행을 멈춘다.
2. `ik_solver`는 0.25초보다 오래된 목표로 `/joint_targets`를 발행하지 않는다.
3. `arm_driver`는 목표가 300 ms 동안 들어오지 않으면 진행 중 이동을 멈추고 마지막
   명령 자세를 유지한다.

```text
Joy input timeout; target pose publication stopped.
Joint target timeout: holding the last commanded pose
```

자세 유지는 토크가 계속 활성화된 상태이다. 로봇을 손으로 움직이지 않는다.

### 13.2 토크 해제와 종료

터미널 2:

```bash
ros2 topic pub --once /safety/torque_enable std_msgs/msg/Bool "{data: false}"
```

다음 로그를 확인한다.

```text
Servo torque disabled
```

링크가 내려갈 수 있으므로 필요한 경우 로봇을 받친다. 토크가 풀린 것을 확인한 뒤 터미널 1의 Launch에서 `Ctrl+C`를 눌러 종료한다.

---

## 14. 문제 해결

| 증상 | 확인할 항목 |
|---|---|
| `Package 'joy' not found` | 1단계 환경 확인 결과와 ROS 2 setup 적용 여부를 조교와 확인한다. |
| Python 모듈을 찾지 못한다. | 1단계 import 확인 결과를 조교에게 전달한다. |
| `/dev/input/js0`가 없다. | 게임패드 연결과 장치 번호를 확인한다. |
| `/dev/ttyACM0` 접근에 실패한다. | 장치 연결, 읽기·쓰기 확인 결과, 다른 드라이버의 사용 여부를 확인한다. |
| Launch 파일을 찾지 못한다. | `setup.py`의 `data_files`, 재빌드, setup 적용을 확인한다. |
| Launch 실행 직후 `Node` 관련 오류가 발생한다. | Launch의 `package`, `executable`에 `### TODO`가 남아 있지 않은지 확인한다. |
| `start_joy:=false`인데 `joy_node`가 실행된다. | `joy_node`의 `condition`이 `start_joy` LaunchConfiguration과 연결됐는지 확인한다. |
| 지정한 게임패드가 선택되지 않는다. | `joy_node`의 `parameters`가 `device_id` LaunchConfiguration을 전달하는지 확인한다. |
| 실행 파일을 찾지 못한다. | `console_scripts`, 재빌드, setup 적용을 확인한다. |
| `/joy` 값이 변하지 않는다. | 단독 `joy_node`와 `ros2 topic echo /joy`로 장치를 확인한다. |
| 축 방향이나 버튼이 다르다. | 실제 `/joy` 배열을 보고 상단의 `AXIS_*`, `GRIPPER_BUTTON`을 수정한다. |
| `/target_pose`가 없다. | `joystick_to_pose.py`의 세 TODO와 `/joy` 입력을 확인한다. |
| `/joint_targets`가 없다. | `ik_solver.py`의 네 TODO, `/joint_states`, IK 거부 로그를 확인한다. |
| 토크가 켜지지 않는다. | `/joint_states` 수신 여부와 토크 요청 메시지를 확인한다. |
| 로봇이 목표를 실행하지 않는다. | 토크 상태, Soft Limit 거부 로그, 목표 타임아웃을 확인한다. |

권한 또는 패키지가 부족한 경우 학생 계정에서 설치·권한 변경 명령을 실행하지 않고
확인 결과를 조교에게 전달한다.

---

## 15. 실습 완료 체크리스트

- [ ] `joystick_to_pose.py`의 Publisher 2개와 Subscriber 1개를 완성했다.
- [ ] `ik_solver.py`의 Subscriber 3개와 Publisher 1개를 완성했다.
- [ ] Launch 파일의 Node 실행 항목 6개를 완성했다.
- [ ] `joy_node`에 `start_joy` 조건과 `device_id` 파라미터를 연결했다.
- [ ] 5주차 부분 관절 목표와 6주차 전체 관절 목표의 차이를 설명할 수 있다.
- [ ] 패키지를 빌드하고 실행 파일 다섯 개를 확인했다.
- [ ] 토크를 켜기 전에 `/joy` 축과 버튼 번호를 확인했다.
- [ ] Launch의 노드 6개와 전체 Topic 목록을 확인했다.
- [ ] 게임패드로 X, Y, Z, Pitch와 Gripper를 제어했다.
- [ ] `/joint_targets`, `/joint_states`, `/ee_pose`의 의미를 구분했다.
- [ ] 입력 단절 시 목표 발행 중단과 마지막 자세 유지를 확인했다.
- [ ] `/safety/torque_enable`에 `false`를 보내고 토크 해제를 확인했다.
- [ ] 토크 해제 후 Launch를 정상 종료했다.
