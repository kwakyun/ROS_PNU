# 5주차 실습 작업 지시서 — 컴퓨터·폴더·터미널별 진행

이 지시서는 [실습 안내서](docs/practice.md), [강의 문서](docs/lecture.md), [강의 슬라이드](docs/week5_ROS2_joint_control.pptx)를 기준으로 작성했다. 현재 저장소에 준비된 **완성 패키지를 Jetson에 복사하여 실습하는 방법**이다. 원본 자료의 패키지 생성·TODO 작성 단계는 이미 준비된 코드로 대체하고, 실제 장비 확인·빌드·실행·측정은 아래 순서대로 직접 수행한다.

## 1. 어느 컴퓨터에서 무엇을 하나?

**Controller, Plotter, 명령 전송은 모두 로봇이 USB로 연결된 Jetson에서 수행한다.** 현재 Windows PC는 자료 준비·파일 전달·결과 보관에 사용한다. 이번 실습에는 PC와 Jetson에 노드를 나누어 실행할 필요가 없다.

| 컴퓨터 | 작업 | 사용하는 폴더 | 필요한 환경 |
|---|---|---|---|
| 준비용 Windows PC | 자료 읽기, 완성 패키지 전달 | `C:\WorkSpace\ROS\week5` | 파일 탐색기, 선택적으로 PowerShell·SSH/SCP |
| 실습용 Jetson / Ubuntu | 패키지 빌드, 로봇 제어, 그래프, 명령 전송 | `~/week5` | 수업용 ROS 2 환경, SDK, 로봇 USB, 데스크톱 화면 |
| 준비용 Windows PC | 실물 실험 CSV·PNG 보관 | `C:\WorkSpace\ROS\week5\field_results\실험시각` | 파일 탐색기 또는 SCP |

준비용 PC가 Ubuntu여도 역할은 같다. 준비용 PC의 자료 폴더에서 패키지를 Jetson으로 전달하면 된다. 이 문서의 Windows PowerShell 명령만 해당 PC의 파일 복사 방법으로 바꾼다.

Jetson에서 `~`는 **Jetson 로그인 계정의 홈**이다. 예를 들어 로그인 계정이 `student`라면 `~/week5`는 `/home/student/week5`다. Windows 경로나 준비용 Ubuntu PC의 홈과 혼동하지 않는다.

## 2. 폴더를 이렇게 배치한다

### Windows PC: 복사할 원본

```text
C:\WorkSpace\ROS\week5\
├── docs\                          # 강의·실습 원본 자료
├── source_code\                   # 파일별 완성 코드 참고용
└── week05_joint_control\           # 이 폴더 전체를 Jetson으로 복사
    ├── config\joints.yaml
    ├── resource\week05_joint_control
    ├── week05_joint_control\      # Python 모듈이 있는 내부 폴더
    ├── package.xml
    ├── setup.cfg
    └── setup.py
```

**`package.xml`과 `setup.py`가 들어 있는 바깥쪽 `week05_joint_control` 폴더를 복사한다.** 같은 이름의 내부 Python 폴더만 복사하면 ROS 패키지로 빌드할 수 없다. `resource`의 빈 마커 파일도 필요하다.

### Jetson: 실습 중 최종 구조

```text
~/week5/                            # workspace: 여기에서 빌드·실행
├── week05_joint_control/           # PC에서 전달한 패키지
│   ├── config/joints.yaml
│   ├── resource/week05_joint_control
│   ├── week05_joint_control/
│   │   ├── __init__.py
│   │   ├── hardware_interface.py
│   │   ├── joint_controller.py
│   │   └── joint_plotter.py
│   ├── package.xml
│   ├── setup.cfg
│   └── setup.py
├── build/                          # Jetson에서 빌드하면 생성
├── install/                        # Jetson에서 빌드하면 생성
├── log/                            # Jetson에서 빌드하면 생성
└── results/                        # Plotter 정상 종료 시 생성
```

이번 자료는 `~/week5` 바로 아래에 패키지를 두도록 안내한다. **별도의 `src` 폴더나 `~/ros2_ws`를 만들 필요가 없다.** 패키지만 홈에 단독으로 놓는 대신 위 구조를 사용하면 자료의 빌드·실행·결과 저장 경로가 일치한다.

## 3. PC → Jetson으로 패키지 전달

아래 A와 B 중 한 가지 방법만 사용한다. 이미 Jetson에 실습 코드가 있다면 수정본을 다른 이름으로 백업한 뒤 전달한다. Windows에서 생성한 `build`, `install`, `.test-deps`, `.test-build`는 복사하지 않는다.

### 방법 A: USB 메모리와 파일 탐색기

1. **Windows PC**에서 `C:\WorkSpace\ROS\week5\week05_joint_control` 전체를 USB 메모리에 복사한다.
2. **Jetson 파일 관리자**에서 홈에 `week5` 폴더를 만든다.
3. USB의 `week05_joint_control` 폴더를 Jetson의 `week5` 안에 복사한다.
4. `~/week5/week05_joint_control/package.xml`이 보이는지 확인한다.

### 방법 B: 네트워크 SSH/SCP

Jetson의 로그인 계정·IP를 알고 SSH 접속이 준비되어 있을 때 사용한다. 아래 두 변수는 실제 값으로 바꾼다.

**실행 컴퓨터: Windows PC / 프로그램: PowerShell / 현재 폴더: 어디든 가능**

```powershell
$JetsonUser = "실제_Jetson_계정"
$JetsonIP = "실제_Jetson_IP"
ssh "${JetsonUser}@${JetsonIP}" "mkdir -p ~/week5"
scp -r "C:\WorkSpace\ROS\week5\week05_joint_control" "${JetsonUser}@${JetsonIP}:~/week5/"
```

SSH 명령 안의 `~/week5`는 Jetson 폴더다. SSH가 준비되지 않았다면 방법 A로 진행한다. GitHub에 최신 파일이 올라갔다고 가정하지 않고 현재 PC의 완성 패키지를 전달한다.

## 4. Jetson 환경과 장비 확인

**실행 컴퓨터: Jetson / 터미널: 데스크톱에서 연 터미널 / 현재 폴더: `~/week5`**

제조사 Bringup과 이전 주차 로봇 제어 노드를 정상 종료한다. 로봇의 USB를 Jetson에 연결하고 수업에서 안내한 전원·배선 상태를 확인한다. 이후 다음을 실행한다.

```bash
cd ~/week5
pwd
ls week05_joint_control/package.xml week05_joint_control/setup.py
source ~/ros2_base/install/setup.bash

python3 -c "import rclpy; print('rclpy OK')"
python3 -c "import yaml; print('PyYAML OK')"
python3 -c "import matplotlib; print('matplotlib OK')"
python3 -c "import vassar_feetech_servo_sdk; print('Feetech SDK OK')"
python3 -c "from scservo_sdk import PortHandler, sms_sts; print('Low-level SDK OK')"
ls -l /dev/ttyACM0
```

정상 판정: `pwd`는 Jetson 홈 아래 `week5`, 두 패키지 파일이 존재하고, import가 모두 성공하며 `/dev/ttyACM0`이 존재한다. 마지막 SDK import는 현재 완성 코드에 맞춰 추가한 확인이다.

`~/ros2_base/install/setup.bash`는 원본 실습 환경 경로다. 수업 장비가 실제로 `/opt/ros/humble/setup.bash`를 사용하는 경우에만 이후 모든 터미널의 underlay 경로를 그 경로로 바꾼다. 파일이 없다고 빈 `setup.bash`를 만들지 말고 설치 환경을 조교에게 확인한다. 모듈·포트 확인에 실패하면 해결 후 다음 단계로 진행한다.

## 5. Jetson에서 빌드

**실행 컴퓨터: Jetson / 현재 폴더: 반드시 `~/week5`**

```bash
cd ~/week5
source ~/ros2_base/install/setup.bash
colcon list
colcon build --symlink-install --packages-select week05_joint_control
source install/setup.bash
ros2 pkg executables week05_joint_control
```

`colcon list`에서 패키지를 찾고, 빌드 성공 후 다음 두 실행 파일이 보여야 한다.

```text
week05_joint_control joint_controller
week05_joint_control joint_plotter
```

완성 패키지를 복사했으므로 `ros2 pkg create`를 다시 실행하지 않는다. 원본 ZIP의 미완성 코드로 덮어쓰지도 않는다. 직접 TODO를 작성하는 연습을 할 때만 [원본 실습 안내서](docs/practice.md)의 2~5절을 따라 패키지 생성·코드 작성·설치 설정을 수행한다.

코드를 수정했다면 실행 중인 노드를 정상 종료한 뒤 이 위치에서 다시 빌드하고, 사용할 모든 터미널에서 환경을 다시 불러온다.

## 6. Jetson에 터미널 세 개 준비

| 터미널 | 여는 컴퓨터·위치 | 역할 | 실행 후 상태 |
|---|---|---|---|
| 1 | Jetson 데스크톱, `~/week5` | Controller: 시리얼 연결·로봇 제어 | 계속 실행 |
| 2 | Jetson 데스크톱, `~/week5` | Plotter: 그래프·기록 | 계속 실행 |
| 3 | Jetson 데스크톱, `~/week5` | 상태 확인·토크·목표 명령 | 명령마다 사용 |

**각 터미널에서 아래 세 줄을 각각 실행한다.** 터미널 1에서 실행했다고 터미널 2·3에도 적용되는 것은 아니다.

```bash
cd ~/week5
source ~/ros2_base/install/setup.bash
source install/setup.bash
```

세 터미널의 `ROS_DOMAIN_ID`, `ROS_LOCALHOST_ONLY`, `RMW_IMPLEMENTATION` 설정도 일치해야 한다. 기존 4주차 설정이 남아 있다면 다음 명령으로 비교하고 수업에서 지정한 설정으로 맞춘다.

```bash
printenv ROS_DOMAIN_ID ROS_LOCALHOST_ONLY RMW_IMPLEMENTATION
```

원본 5주차 안내서는 특정 Domain ID를 지정하지 않는다. 저장소 README의 `30`은 예시이며, 조교가 배정한 값이 있다면 그것을 세 터미널에 동일하게 적용한다. 다른 조의 로봇과 같은 Topic을 공유하지 않도록 수업 설정을 따른다.

터미널 1·3은 필요하면 SSH로 접속해 사용할 수 있지만, 명령은 여전히 Jetson에서 실행되는 것이다. **터미널 2의 Plotter는 원본 안내에 따라 Jetson 데스크톱의 로컬 터미널에서 실행한다.**

토크를 켜기 전에 터미널 3에서 사용할 다음 OFF 명령을 준비해 둔다. 아직 Controller가 없을 때 먼저 발행하면 구독자를 기다릴 수 있으므로, 여기서는 명령을 확인하고 실제 발행은 Controller 실행 후 수행한다.

```bash
ros2 topic pub --once /safety/torque_enable \
  std_msgs/msg/Bool "{data: false}"
```

## 7. Controller → Plotter → 통신 확인

### 7-1. Jetson 터미널 1: Controller 실행

```bash
ros2 run week05_joint_control joint_controller
```

`Joint controller ready on /joint_states & /joint_targets`와 `Servo torque disabled on startup` 로그를 확인한다. 시작 시 토크가 꺼져 있어야 한다. 아직 목표값을 보내지 않는다. 이 터미널은 종료하지 않고 로그 확인용으로 둔다.

### 7-2. Jetson 터미널 2: Plotter 실행

```bash
cd ~/week5
ros2 run week05_joint_control joint_plotter
```

그래프 창에 6개 관절과 파란 현재값 선이 나타나야 한다. 주황 요청값 선은 첫 목표 요청 이후 나타난다. Plotter의 현재 폴더가 결과 저장 위치를 결정하므로 반드시 위 `cd`를 실행한다.

### 7-3. Jetson 터미널 3: 상태 확인

```bash
ros2 node list
ros2 topic list
ros2 node info /joint_controller
ros2 topic echo --once /joint_states
```

다음 노드·Topic을 확인한다. ROS 기본 Topic이 추가로 보여도 정상이다.

```text
노드:  /joint_controller, /joint_plotter
Topic: /joint_states, /joint_targets, /safety/torque_enable
```

`/joint_states`에 관절 이름과 현재 위치가 출력되어야 한다. 통신이나 측정값이 확인되지 않으면 토크 ON 단계로 넘어가지 않는다.

## 8. Jetson 터미널 3: 실제 로봇 실험

아래 명령은 **하나씩 실행하고 결과를 확인한 다음** 다음 명령을 보낸다. 위치 단위는 모두 radian이다. 관절 가동범위 안의 사람·물체를 확인한다. 토크가 켜진 로봇을 손으로 억지로 밀지 않는다.

### 8-1. 토크 ON: 현재 자세 유지

```bash
ros2 topic pub --once /safety/torque_enable \
  std_msgs/msg/Bool "{data: true}"
```

터미널 1의 `Servo torque enabled; current pose is initial target` 로그를 확인한다. 로봇이 갑자기 다른 자세로 이동하지 않고 현재 자세를 유지해야 한다.

### 8-2. 단일 관절 이동

```bash
ros2 topic pub --once /joint_targets \
  sensor_msgs/msg/JointState \
  "{name: ['shoulder_pan'], position: [0.5]}"
```

`Target accepted` 로그와 `shoulder_pan`의 부드러운 이동을 확인한다. 다른 관절은 이전 목표를 유지한다. 파란 현재값이 주황 요청값을 따라가는지 보고, 이동이 안정된 후 다음 단계로 간다.

`Target reached`는 코드상 보간 명령이 목표에 도달했다는 뜻이다. 실제 관절의 도달 여부는 파란 측정값과 실물로 함께 확인한다.

### 8-3. 다중 관절 이동

```bash
ros2 topic pub --once /joint_targets \
  sensor_msgs/msg/JointState \
  "{name: ['shoulder_pan', 'elbow_flex'], position: [0.2, 0.4]}"
```

`shoulder_pan`은 `0.2 rad`, `elbow_flex`는 `0.4 rad`로 이동해야 한다. `name`과 `position` 배열의 같은 위치끼리 한 쌍이다. 두 관절의 실제 이동이 안정될 때까지 기다린다.

### 8-4. Soft Limit 거부

```bash
ros2 topic pub --once /joint_targets \
  sensor_msgs/msg/JointState \
  "{name: ['shoulder_pan'], position: [3.5]}"
```

아래 세 가지가 함께 확인되어야 한다.

- 터미널 1: `shoulder_pan=3.5000 rad 명령 거부` 로그.
- 실물·파란선: 거부된 `3.5 rad`로 이동하지 않고 직전 수락 목표 유지.
- 주황선: 원본 요청인 `3.5 rad` 표시.

주황선은 **수락된 목표가 아닌 전송한 요청값**이다. 따라서 거부 실험에서는 파란선과 달라지는 것이 정상이다. 이전 이동 도중 거부 명령을 보내면 이전에 수락한 이동이 계속될 수 있으므로 8-3의 안정 상태를 먼저 확인한다.

## 9. 토크 OFF → 기록 저장 → Controller 종료

### 9-1. Jetson 터미널 3: 토크 OFF

```bash
ros2 topic pub --once /safety/torque_enable \
  std_msgs/msg/Bool "{data: false}"
```

터미널 1의 `Servo torque disabled` 로그와 위치 제어 중단을 확인한다. 해제 시 링크가 중력으로 내려올 수 있으므로 수업에서 안내한 방법으로 안전하게 지지한다.

이상 동작이 발생해도 목표 명령을 추가로 보내지 않고 이 OFF 명령을 우선 사용한다. 통신·프로세스 장애로 OFF가 전달되지 않으면 장비의 비상 정지 절차를 따른다. ROS Topic 명령은 하드웨어 비상 정지를 대신하지 않는다.

### 9-2. Jetson 터미널 2: Plotter 정상 종료

`Ctrl+C`를 누르고 CSV·PNG 저장 메시지와 종료를 기다린다. 강제 종료하지 않는다.

### 9-3. Jetson 터미널 1: Controller 정상 종료

`Ctrl+C`를 누르고 `Servo torque disabled on shutdown` 로그를 확인한다.

### 9-4. Jetson 터미널 3: 결과 확인

```bash
ls -lh ~/week5/results
```

현재 완성 코드에서는 아래 형태의 파일이 생성된다. 실제 이름에는 실행 날짜·시각·마이크로초가 들어간다.

```text
joint_log_YYYYMMDD_HHMMSS_microseconds.csv
joint_plot_YYYYMMDD_HHMMSS_microseconds.png
```

CSV는 `time_s`와 6개 관절의 `*_current`, `*_requested`로 총 13개 열을 가진다. 첫 요청 이전 requested 값이 비어 있거나 NaN인 것은 정상이다. CSV에는 수집한 전체 기록, PNG에는 마지막 약 30초 그래프가 저장된다. 앞부분 실험 화면도 필요하면 단계별로 별도 화면 캡처를 남긴다.

## 10. Jetson → PC로 실물 결과 회수

USB를 사용한다면 Jetson의 `~/week5/results`를 USB로 복사한 뒤 Windows의 `C:\WorkSpace\ROS\week5\field_results\실험시각` 안에 보관한다.

SCP를 사용한다면 **Windows PC의 PowerShell**에서 실행한다. 새 PowerShell이면 계정·IP 변수도 다시 설정한다.

```powershell
$JetsonUser = "실제_Jetson_계정"
$JetsonIP = "실제_Jetson_IP"
$ResultDir = "C:\WorkSpace\ROS\week5\field_results\$(Get-Date -Format yyyyMMdd-HHmmss)"
New-Item -ItemType Directory -Force -Path $ResultDir | Out-Null
scp -r "${JetsonUser}@${JetsonIP}:~/week5/results" "$ResultDir"
```

Windows에서 복사된 CSV와 PNG를 실제로 열어 확인한다. 여러 실험 파일이 있으면 제출할 실행 시각의 CSV·PNG 쌍을 골라 둔다. 저장소의 `.test-build` 결과는 소프트웨어 검증용 가상 데이터이며 실물 제출 결과로 사용하지 않는다.

## 11. 문제가 생겼을 때 확인할 컴퓨터·폴더

| 증상 | 확인할 위치 | 조치 |
|---|---|---|
| `cd ~/week5` 실패 | Jetson 홈 | Windows에만 폴더를 만든 것은 아닌지 확인하고 3절대로 전달한다. |
| `colcon list`에 패키지가 없음 | Jetson `~/week5` | 바깥 패키지 폴더와 `package.xml`을 확인한다. 내부 Python 폴더만 복사했다면 다시 전달한다. |
| `Package ... not found` | 명령을 실행한 Jetson 터미널 | 5절 빌드 성공 여부, 해당 터미널의 `source install/setup.bash`를 확인한다. |
| import 또는 underlay 오류 | Jetson | 4절 명령으로 실패 항목을 구분하고 조교에게 설치 환경을 확인한다. |
| `/dev/ttyACM0` 없음 | Jetson USB 연결 | 로봇이 준비용 PC가 아닌 Jetson에 연결됐는지, 전원·케이블을 확인한다. |
| 포트 권한 오류 | Jetson | `ls -l /dev/ttyACM0`, `groups`로 권한·dialout 그룹을 확인하고 조교에게 문의한다. |
| 포트 열기 실패 | Jetson의 다른 실행 노드 | 제조사 Bringup·이전 실습 Controller를 정상 종료한다. |
| 그래프 창이 없음 | Jetson 터미널 2 | SSH가 아닌 Jetson 데스크톱 로컬 터미널인지 확인한다. |
| 노드·Topic이 안 보임 | Jetson 터미널 1~3 | 노드 실행 로그, 각 터미널의 ROS 환경·Domain ID·RMW 설정 일치를 확인한다. |
| `pub --once`가 계속 대기 | Jetson 터미널 3 | `Ctrl+C`로 취소하고 Controller 실행·구독자·환경을 확인한다. 전송 완료로 간주하지 않는다. |
| 토크 활성화 실패·SDK 오류 | Jetson 터미널 1 | 추가 목표 전송을 멈추고 상태·전원·오류 로그를 확인한다. 서보 모드·보정값을 임의로 변경하지 않고 조교에게 문의한다. |
| 거부 후 주황선만 크게 바뀜 | Jetson Plotter | 거부 로그와 이전 자세 유지를 확인한다. 원본 요청을 표시한 정상 동작일 수 있다. |
| CSV·PNG 없음 | Jetson 터미널 2의 실행 폴더 | `~/week5`에서 Plotter를 실행했는지, `Ctrl+C` 정상 종료·저장 로그가 있었는지 확인한다. |
| PC에서 결과가 안 보임 | Windows 결과 폴더 | 결과는 먼저 Jetson에 생성된다. 10절의 회수를 수행한다. |

## 12. 현장 완료 체크리스트와 근거

- [ ] Jetson의 `~/week5/week05_joint_control`에 전체 패키지를 배치했다.
- [ ] Jetson에서 빌드했고 두 실행 파일을 확인했다.
- [ ] Controller 시작 시 토크 OFF와 현재 관절 측정값을 확인했다.
- [ ] Jetson 로컬 Plotter에서 6개 관절을 확인했다.
- [ ] 토크 ON 시 급격한 이동 없이 현재 자세를 유지했다.
- [ ] 단일·다중 관절 요청에 대해 실물과 파란 측정값의 추종을 확인했다.
- [ ] 범위 밖 요청 거부·이전 목표 유지·주황 요청값 표시를 확인했다.
- [ ] 토크 OFF 및 두 노드의 정상 종료를 확인했다.
- [ ] 실물 측정 CSV·PNG를 열어 확인하고 PC에 회수했다.

| 사용한 자료 | 이 지시서에 반영한 내용 |
|---|---|
| `docs/practice.md` 0~6절 | 안전 순서, Jetson 환경, workspace·패키지 구조, 빌드와 실행 파일 확인 |
| `docs/practice.md` 7~12절 | 세 터미널 역할, Plotter 로컬 실행, 실제 명령·판정·저장·완료 기준 |
| `docs/lecture.md` | Controller와 Plotter 역할, 측정·요청·목표 구분, 보간·자세 유지·안전 개념 |
| `docs/week5_ROS2_joint_control.pptx` 15~23번 슬라이드 | 제어 흐름, 시작 시 토크 OFF, 목표 검증, 부분 관절 명령, 보간과 유지, 실습 점검 |
| 현재 완성 패키지 및 `README.md` | 패키지 전체 복사로 설치 준비 대체, 저수준 SDK 확인, 로그 해석과 결과 파일 특성 |

PC 파일 전송·결과 회수 절차와 역할별 표는 원본 실습을 수행하기 위한 보충 안내다. 소프트웨어 검증 기록은 [VALIDATION.md](VALIDATION.md)에 있으며, 위 현장 항목은 실제 장비에서 관찰한 뒤 체크한다.
