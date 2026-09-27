# 5주차 과제 완성본: 관절 위치제어와 자세 유지

[실습 안내서](docs/practice.md)의 Controller TODO 네 곳, 설치 설정과 두 실행 파일을 완성했다.
`source_code/`에는 제공 파일별 완성 코드를, `week05_joint_control/`에는 그대로 옮겨 빌드할 패키지를 둔다.
강의·실습 문서와 PPTX 및 제공 ZIP은 원본을 유지했다.

컴퓨터별 폴더 배치와 터미널별 실행 순서는 [실습 작업 지시서](WORK_INSTRUCTIONS.md)를 참고한다.

**로컬 소프트웨어 검증은 완료했으며, 실제 로봇 실습 결과는 아직 없다.**
실물 토크·추종·자세 유지 확인은 실습 장비에서 수행해야 한다.
검증 상세와 요구사항 대응은 [검증 기록](VALIDATION.md)을 참고한다.

## 1. Ubuntu/Jetson에 놓을 경로

이번 주차는 `practice.md`에 지정된 **`~/week5`를 workspace로 사용**한다.
아래처럼 완성 패키지를 통째로 복사하면 별도 `ros2 pkg create`는 필요 없다.

```text
~/week5/                              ← 빌드 및 Plotter 실행 위치
├── week05_joint_control/             ← 복사할 패키지 폴더
│   ├── config/
│   │   └── joints.yaml
│   ├── resource/
│   │   └── week05_joint_control
│   ├── week05_joint_control/
│   │   ├── __init__.py
│   │   ├── hardware_interface.py
│   │   ├── joint_controller.py
│   │   └── joint_plotter.py
│   ├── package.xml
│   ├── setup.cfg
│   └── setup.py
├── build/                            ← 현장에서 colcon으로 생성
├── install/                          ← 현장에서 colcon으로 생성
├── log/                              ← 현장에서 colcon으로 생성
└── results/                          ← Plotter 정상 종료 시 CSV·PNG 저장
```

`~`는 해당 실습 장비에 로그인한 사용자의 홈이다.
현재 저장소를 실습 장비의 `~/ROS`에 옮겼다면 다음과 같이 복사한다.
다른 경로라면 `~/ROS`만 실제 경로로 바꾼다.

```bash
mkdir -p ~/week5
cp -a ~/ROS/week5/week05_joint_control ~/week5/
```

기존 실습 코드가 있다면 변경 내용을 백업한 뒤 갱신한다.
동일 이름의 패키지를 workspace에 두 번 배치하지 않는다.
Windows에서 만든 빌드 결과, `.test-deps`, `.test-build`는 복사하지 않는다.

## 2. 실습 장비 준비

Jetson에 ROS 2와 실습용 SDK가 준비된 환경을 전제로 한다.
아래 명령은 시리얼 연결 없이 import만 확인한다.

```bash
source ~/ros2_base/install/setup.bash
python3 -c "import rclpy; print('rclpy OK')"
python3 -c "import yaml; print('PyYAML OK')"
python3 -c "import matplotlib; print('matplotlib OK')"
python3 -c "from scservo_sdk import PortHandler, sms_sts; print('Feetech SDK OK')"
python3 -m pip show vassar-feetech-servo-sdk
ls -l /dev/ttyACM0
groups
```

완성본은 `vassar-feetech-servo-sdk==1.5.0`에 포함된 `scservo_sdk` API로 검증했다.
의존성 누락·다른 SDK 버전·시리얼 권한 문제는 실습 안내서대로 조교와 환경을 확인한다.
장비에서 설치가 필요한 경우 ROS를 실행하는 같은 Python 환경에 설치한다.

```bash
sudo apt install python3-yaml python3-matplotlib python3-pip python3-colcon-common-extensions
python3 -m pip install --user 'vassar-feetech-servo-sdk==1.5.0'
```

`rclpy`를 설치한 ROS underlay 경로가 다르면 실제 경로를 사용한다.
시리얼 권한에 `dialout` 추가가 필요하다면 장비 담당자와 확인한 후 적용하고 재로그인한다.
제조사 Bringup과 3·4주차 노드를 종료하여 Controller만 포트를 사용하게 한다.

`config/joints.yaml`은 제공값을 유지했다. 장치·서보 ID·실제 영점이 맞는지 대조한다.
서보는 STS/STS3215, 4096 ticks/rev, 위치 모드 0을 전제로 한다.
모드가 다르면 완성 코드는 오류로 중단하며 임의로 EEPROM 모드를 바꾸지 않는다.

## 3. 빌드

```bash
cd ~/week5
source ~/ros2_base/install/setup.bash
colcon list
colcon build --symlink-install --packages-select week05_joint_control
source install/setup.bash
ros2 pkg executables week05_joint_control
```

예상 실행 파일:

```text
week05_joint_control joint_controller
week05_joint_control joint_plotter
```

## 4. 모든 터미널에서 같은 환경 사용

다음 공통 준비를 Controller·Plotter·명령용 터미널 각각에 적용한다.
실습실에서 다른 Domain을 지정했다면 모든 터미널을 같은 지정값으로 맞춘다.

```bash
cd ~/week5
source ~/ros2_base/install/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=30
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

4주차 실험으로 Domain 31을 사용한 터미널이 남아 있지 않은지 확인한다.
여러 조가 같은 네트워크·Domain을 공유하면 다른 조의 목표·토크 Topic도 수신할 수 있으므로
장비별 Domain 설정은 실습 담당자의 배정을 따른다.

## 5. 실행 및 과제 확인

### 먼저: 명령 터미널에 토크 OFF 명령 준비

토크를 켜기 전에 다음 명령을 바로 사용할 수 있는 터미널을 준비한다.
토크 OFF 뒤 링크가 내려올 수 있으므로 실습 안내서의 지지·주변 정리 절차를 따른다.

```bash
ros2 topic pub --once /safety/torque_enable std_msgs/msg/Bool "{data: false}"
```

### 터미널 1: Controller

```bash
ros2 run week05_joint_control joint_controller
```

시작할 때 실제 토크 OFF 요청을 전송한다. 다음 로그와 상태 발행을 확인한다.

```text
Joint controller ready on /joint_states & /joint_targets
Servo torque disabled on startup
```

### 터미널 2: Plotter

**Jetson 데스크톱의 로컬 터미널**에서 실행한다. SSH 터미널에는 GUI 화면이 없을 수 있다.
공통 준비에서 `cd ~/week5`를 했는지 확인한다.

```bash
ros2 run week05_joint_control joint_plotter
```

6개 그래프의 파란 `current` 선을 확인한다.
주황 `requested`는 첫 요청 전에는 표시되지 않으며 CSV에는 `nan`으로 기록한다.

### 터미널 3: 통신 확인

```bash
ros2 node list
ros2 topic list
ros2 node info /joint_controller
ros2 topic echo --once /joint_states
```

`/joint_states`, `/joint_targets`, `/safety/torque_enable`이 있어야 한다.
Publisher 목표 주기는 20 Hz다. 실제 측정이 지속되는지 확인한 후 다음을 진행한다.

### 토크 ON과 정상 요청

로봇 주변이 비어 있고 OFF 명령을 보낼 준비가 된 상태에서 실행한다.

```bash
ros2 topic pub --once /safety/torque_enable std_msgs/msg/Bool "{data: true}"
```

`Servo torque enabled; current pose is initial target`을 확인한다.
현재 자세 유지가 확인된 뒤 단일 관절 요청을 보낸다.

```bash
ros2 topic pub --once /joint_targets sensor_msgs/msg/JointState \
  "{name: ['shoulder_pan'], position: [0.5]}"
```

단위는 **rad**다. 목표 수락 로그와 파란 측정값의 추종을 확인한다.
다중 관절 요청은 다음과 같다.

```bash
ros2 topic pub --once /joint_targets sensor_msgs/msg/JointState \
  "{name: ['shoulder_pan', 'elbow_flex'], position: [0.2, 0.4]}"
```

요청하지 않은 관절은 이전 목표를 유지한다.
30 Hz Control Timer는 매 주기 `max_vel_rad_s / control_hz` 이하로 명령값을 바꾼다.
제공 코드의 `Target reached` 로그는 **보간 명령이 목표에 도달**했다는 뜻이다.
실제 관절의 도달 여부는 파란 측정값으로 별도 확인한다.

### Soft Limit 거부

앞선 정상 목표에 도달해 자세를 유지한 뒤 실행한다.

```bash
ros2 topic pub --once /joint_targets sensor_msgs/msg/JointState \
  "{name: ['shoulder_pan'], position: [3.5]}"
```

`shoulder_pan=3.5000 rad 명령 거부` 로그가 나오고 이전 목표가 유지되어야 한다.
주황선은 **원본 요청 3.5**로 올라가며, 파란선은 이를 따라가지 않는 것이 정상이다.
Plotter는 Controller의 수락 여부를 판단하지 않는다.
이동 중 거부했다면 새 목표는 저장되지 않고 이전에 수락한 목표를 향한 보간이 계속된다.

## 6. 토크 해제·저장·종료

```bash
ros2 topic pub --once /safety/torque_enable std_msgs/msg/Bool "{data: false}"
```

`Servo torque disabled`와 위치 제어 중단을 확인한다.
그다음 Plotter에서 `Ctrl+C`, Controller에서 `Ctrl+C` 순서로 종료한다.
Controller의 정상 종료 시 `Servo torque disabled on shutdown` 로그를 확인한다.

```bash
ls -lh ~/week5/results/
```

생성 파일:

```text
joint_log_날짜_시간_마이크로초.csv
joint_plot_날짜_시간_마이크로초.png
```

CSV는 전체 수집 구간의 `time_s`와 관절별 `*_current`, `*_requested`를 포함한다.
PNG는 화면과 같은 마지막 30초 구간을 저장한다.
파일명에 마이크로초를 추가해 같은 초에 재실행해도 덮어쓰지 않게 했다.

## 7. 제공 코드에서 추가로 보완한 부분

네 TODO 외에 실제 실행에 영향을 주는 다음을 보완했다.

- 범위 검사 `not lower <= pos <= upper`로 경계값은 허용하고 NaN·무한대는 거부한다.
- 중복 관절 이름은 메시지 전체를 거부한다. OFF 요청을 받은 뒤 새 목표도 수락하지 않는다.
- 토크 ON 직전에 현재 자세를 다시 읽는다.
- SDK 1.5.0의 고수준 `write_position()`은 토크 ON을 먼저 수행하므로,
  저수준 API로 **토크 OFF 확인 → 현재 자세 목표 기록 → 목표 레지스터 읽기 검증 → 토크 ON** 순서를 사용한다.
- SDK 연결 시 자동 phase 변경, 쓰기 시 자동 모드 변경을 사용하지 않는다.
  위치 모드 0이 아니면 실습 장비 설정을 확인하도록 오류를 낸다.
- 상태 읽기 또는 명령 쓰기 실패 시 동작 요청을 취소하고 Control Timer에서 OFF를 시도한다.
  해제 응답이 확인되지 않으면 다음 주기에 재시도하며 재활성화 요청을 거부한다.
  복구 후 자동으로 움직이지 않으며 새로운 ON 요청이 필요하다.
- 일부 서보의 토크 해제 실패가 다른 서보의 OFF 시도를 막지 않게 했다.
- 초기화 실패·Plotter 저장 실패 시에도 자원 정리가 진행되도록 종료 처리를 보완했다.

이 처리는 성공 응답을 확인하는 소프트웨어 처리이며 물리적인 안전 보장을 뜻하지 않는다.
특히 10 Hz Heartbeat는 watchdog이 아니고, 통신 단절 시 OFF 명령의 전달도 보장할 수 없다.
토크 해제 미확인 오류가 나면 추가 목표를 보내지 말고 현장 장비의 정지 절차를 따른다.

## 8. 검증과 현장 완료 항목

로컬에서 **33개 테스트**, Python 배포물 빌드, 가상 데이터 CSV·PNG 저장을 확인했다.
SDK 1.5.0의 실제 패킷 구현을 가상 시리얼로 검증했으며 로봇에 연결하지 않았다.

현장에서 추가 확인할 항목:

- [ ] Jetson `colcon build` 성공 및 실행 파일 두 개 확인
- [ ] 시작·종료와 명시적 OFF 요청 때 실제 토크 해제
- [ ] 토크 ON 시 현재 자세 유지, 급격한 이동 없음
- [ ] 단일·다중 목표 추종 및 6개 그래프 표시
- [ ] 범위 밖 목표 거부, 이전 수락 목표 유지
- [ ] `~/week5/results/`에서 실물 측정 CSV·PNG 확인

검증용 가상 결과는 `.test-build`에 분리했고 실제 제출용 `results`로 만들지 않았다.
