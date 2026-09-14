# [3주차] ROS2 basic 2 — 실습 안내서

> 수업 내용(`lecture.md`)을 참고하여 아래 실습을 순서대로 수행함.

---

## [실습 1] Topic 발행 및 구독

실습 1은 제공된 Publisher와 Launch 파일을 확인하고 Listener를 완성하여 실제 관절
상태 Topic을 확인하는 과정임.

### 1-1. 환경과 장비 확인

```bash
source ~/ros2_base/install/setup.bash

python3 -c "import rclpy; print('rclpy OK')"
python3 -c "import yaml; print('PyYAML OK')"
python3 -c "import vassar_feetech_servo_sdk; print('Feetech SDK OK')"

ls -l /dev/ttyACM0
```

### 1-2. Workspace와 패키지 생성

```bash
mkdir -p ~/week3
cd ~/week3
source ~/ros2_base/install/setup.bash

ros2 pkg create week03_ros2_jetson \
  --build-type ament_python \
  --dependencies ament_index_python launch launch_ros rclpy sensor_msgs std_srvs
```

이미 `week03_ros2_jetson` 패키지를 생성했다면 `ros2 pkg create`는 다시 실행하지
않음.

### 1-3. 실습 제공 파일 이동

```text
~/week3/
└── week03_ros2_jetson/
    ├── config/
    │   └── joints.yaml
    ├── launch/
    │   ├── bringup.launch.py
    │   └── joint_monitor.launch.py
    └── week03_ros2_jetson/
        ├── hardware_interface.py
        ├── joint_state_publisher.py
        ├── joint_state_service_client.py
        └── joint_state_service_server.py
```

### 1-4. Publisher TODO와 `JointState` 확인

jointstate interface를 확인
```bash
ros2 interface show sensor_msgs/msg/JointState
```

`joint_state_publisher.py` TODO 완성하기
- publisher, timer를 활용하여 JointState interface로 "joint_states" topic을 발행
- 관절 이름과 위치를 `JointState.name`, `JointState.position`에 입력함
- 완성한 메시지를 `/joint_states`로 발행함

### 1-5. Listener TODO 완성

`week03_ros2_jetson/week03_ros2_jetson/joint_state_listener.py`의 TODO에
`/joint_states` 구독을 작성함.

```python
self._subscription = self.create_subscription(
    JointState,
    JOINT_STATES_TOPIC,
    self._on_joint_state,
    10,
)
```

### 1-6. 제공된 Joint Monitor Launch 확인

`week03_ros2_jetson/launch/joint_monitor.launch.py`를 열어 다음 두 실행 항목을 확인함.
- `joint_state_publisher`, `joint_state_listener`

### 1-7. `setup.py`와 `package.xml` 수정

`week03_ros2_jetson/setup.py` 위쪽에 다음 import를 추가함.
```python
from glob import glob
import os
```

`data_files`에 Config와 Launch 설치 경로를 추가함.
```python
(os.path.join("share", package_name, "config"), glob("config/*.yaml")),
(os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
```

`install_requires`를 다음과 같이 수정함.
```python
install_requires=["setuptools", "PyYAML"],
```

`console_scripts`에  joint_state_publisher, joint_state_listener 항목을 등록함.

`week03_ros2_jetson/package.xml`의 의존성 항목 근처에 다음 실행 의존성을 추가함.
```xml
<exec_depend>python3-yaml</exec_depend>
```

### 1-8. 빌드

```bash
cd ~/week3
source ~/ros2_base/install/setup.bash

colcon build --symlink-install --packages-select week03_ros2_jetson
source install/setup.bash

ros2 pkg executables week03_ros2_jetson
```

`joint_state_publisher`와 `joint_state_listener`가 표시되는지 확인함.

### 1-9. Topic 실행 및 확인

터미널 1:

```bash
cd ~/week3
source ~/ros2_base/install/setup.bash
source install/setup.bash

ros2 launch week03_ros2_jetson joint_monitor.launch.py
```

터미널 2:

```bash
source ~/ros2_base/install/setup.bash
source ~/week3/install/setup.bash

ros2 node list
ros2 topic type /joint_states
ros2 topic info /joint_states
ros2 topic echo --once /joint_states
ros2 topic hz /joint_states
```

다음을 확인함.

- Publisher와 Listener 노드가 실행됨
- `/joint_states` 타입이 `sensor_msgs/msg/JointState`임
- 6개 관절의 `name`과 `position`이 출력됨
- 발행 주기가 `joints.yaml`의 `publish_hz`와 유사함

확인이 끝나면 각 터미널에서 `Ctrl+C`를 눌러 종료함.

---

## [실습 2] Service 서버 구동 및 클라이언트 요청

### 2-1. Service TODO와 Launch 작성

- `joint_state_service_server.py`의 Service 생성 및 Response TODO 완성
- `lecture.md`의 Service Client 메서드 설명을 참고하여 `joint_state_service_client.py` TODO 완성
- `joint_monitor.launch.py`를 참고하여 `bringup.launch.py`에 Publisher와 Service Server 등록
- `setup.py`의 `console_scripts`에 Service Server와 Client 실행 진입점 등록

### 2-2. 재빌드

```bash
cd ~/week3
source ~/ros2_base/install/setup.bash

colcon build --symlink-install --packages-select week03_ros2_jetson
source install/setup.bash
```

### 2-3. Service 실행 및 검사

터미널 1:

```bash
source ~/ros2_base/install/setup.bash
source ~/week3/install/setup.bash
ros2 launch week03_ros2_jetson bringup.launch.py
```

터미널 2:

```bash
source ~/ros2_base/install/setup.bash
source ~/week3/install/setup.bash
ros2 run week03_ros2_jetson joint_state_service_client
```

터미널 3:

```bash
source ~/ros2_base/install/setup.bash
source ~/week3/install/setup.bash
ros2 service type /get_joint_state
ros2 service call /get_joint_state std_srvs/srv/Trigger "{}"
```

---

## 조교 검사

다음 내용을 조교에게 검사받는다.

- Service Server와 Client가 정상적으로 실행되는지
- Bringup 실행 후 Publisher와 Service Server 노드가 조회되는지
- `/get_joint_state`의 타입이 `std_srvs/srv/Trigger`로 조회되는지
- Python Client와 CLI에서 최신 6개 관절값을 받을 수 있는지