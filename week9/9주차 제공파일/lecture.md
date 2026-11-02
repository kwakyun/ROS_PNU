# [9주차] MuJoCo 로봇 시뮬레이션과 ROS 2 연동 — 수업 내용

## 0. 수업 개요

### 수업 목표

이번 수업을 마치면 다음 내용을 설명하고 수행할 수 있어야 한다.

- MuJoCo의 물리 계산과 단순한 자세 표시의 차이를 설명한다.
- 5주차의 관절 제어를 실제 로봇과 시뮬레이션으로 확장하는 구조를 설명한다.
- Joint와 Actuator, 현재 위치 `qpos`와 목표 입력 `ctrl`을 구분한다.
- `MjModel`, `MjData`, `mj_step()`의 역할을 설명한다.
- 핵심 코드 네 곳과 패키지 등록 설정을 완성하고 ROS Topic과 MuJoCo 배열을 연결한다.
- 실제 관절 자세를 시뮬레이션 화면에 반영한다.
- 같은 목표에 대한 실제·시뮬레이션 응답을 기록하고 차이를 해석한다.


## 1. MuJoCo란 무엇인가

### 1.1 로봇과 물체의 움직임을 계산하는 물리 엔진

MuJoCo는 로봇과 주변 물체의 움직임을 계산하는 물리 엔진이다.
이름은 Multi-Joint dynamics with Contact에서 왔으며, 여러 관절로 연결된 물체의 운동과 물체 사이의 접촉을 다룬다.
단순히 로봇의 모양을 그리는 것이 아니라, 현재 상태와 입력을 바탕으로 시간이 지난 뒤의 상태를 계산한다.
이때 모델에 정의한 질량·관절 구조·구동 특성·중력·마찰·접촉 조건 등이 계산에 영향을 준다.

예를 들어 이번 장면의 큐브를 공중에 놓았다고 가정한다.
물리 계산을 진행하면 큐브는 중력 때문에 떨어지고, 작업판에 닿으면 접촉력이 작용하여 지지된다.
옆으로 힘을 가하면 마찰과 접촉 조건에 따라 움직임이 달라진다.
이것은 원리를 설명하는 예시이며, 이번 실습에서 큐브 배치나 물리 설정을 바꾸는 과제를 추가하지 않는다.

기본 개념은 [MuJoCo 공식 개요](https://mujoco.readthedocs.io/en/stable/overview.html)를 참고한다.

### 1.2 자세를 보여 주는 것과 운동을 계산하는 것

화면에서 로봇이 움직인다고 해서 항상 물리 계산으로 움직인 것은 아니다.

| 방식 | 예시 | 의미 |
|---|---|---|
| 자세를 직접 설정한다. | 실제 관절각을 받아 가상 로봇에 복사한다. | 받은 자세를 표시하며, 그 자세까지 움직이는 과정을 예측하지 않는다. |
| 물리 계산을 진행한다. | 목표각을 주고 관절이 움직이는 과정을 계산한다. | 구동력·중력·마찰 등의 영향을 반영하여 다음 상태를 구한다. |

이번 실습의 Real-to-Sim 추종은 첫 번째 방식이고, 동일 목표 응답 비교의 시뮬레이션은 두 번째 방식이다.
두 방식을 구분해야 화면이 비슷하다는 이유만으로 물리 모델이 정확하다고 판단하지 않는다.

Viewer는 계산되거나 설정된 현재 상태를 화면에 보여 주는 도구이다.
Viewer 없이도 물리 계산을 실행할 수 있으며, 화면을 갱신하는 것만으로 물리 시간이 진행되지는 않는다.

---

## 2. 5주차에서 달라지는 제어 구조

5주차에는 `joint_controller`가 실제 서보를 제어하고 Plotter가 실제값과 요청값을 표시했다.
9주차에는 실제 장치 담당 `arm_io`와 시뮬레이션 담당 `mujoco_ros_bridge`를 나눈다.
`real_sim_comparator`는 두 상태를 기록하며 모터나 시뮬레이션을 직접 제어하지 않는다.

| 기능 | 5주차 | 9주차 |
|---|---|---|
| 실제 로봇 노드 | `joint_controller` | `arm_io` |
| 실제 측정값 | `/joint_states` | `/real/joint_states` |
| 시뮬레이션 상태 | 없음 | `/sim/joint_states` |
| 관절 목표 | `/joint_targets` | `/joint_targets`를 공통으로 사용한다. |
| 토크 제어 | `/safety/torque_enable` Topic | `/robot/set_torque` Service |
| 결과 표시 | 실제값·요청값 | 실제값·시뮬레이션값·비교 기준값 |

5주차의 토크 Topic을 발행해도 9주차 `arm_io`의 토크는 바뀌지 않는다.
`std_srvs/srv/SetBool` Service를 호출하고 `success: true` 응답을 확인한다.
Service 호출 성공은 지속적인 안전 감시를 뜻하지 않는다.

```text
PC: Windows의 WSL2 Ubuntu                    Jetson: 실제 장치

명령 터미널 ── /joint_targets ────────────────> arm_io ── FeetechBus ── 서보
                 │                              │
                 ├─> mujoco_ros_bridge          └─ /real/joint_states ──┐
                 │         └─ /sim/joint_states ────────────────────────┤
                 └──────────────────────────────────────────────────────┤
                                                       real_sim_comparator
                                                               └─ CSV·PNG·YAML
```

- Jetson의 `arm_io` 하나만 `/dev/ttyACM0`을 연다.
- PC의 Bridge와 비교 노드는 실제 시리얼 포트를 열지 않는다.
- 같은 조의 PC와 Jetson은 같은 Domain ID와 RMW를 사용한다.
- WSL 네트워크·방화벽이 준비되지 않았다면 Domain ID만 맞춰도 통신되지 않을 수 있다.

### 2.1 4주차 통신 설정을 사용하는 방법

통신 구조는 4주차와 같다. PC와 Jetson을 같은 네트워크에 연결하고 같은 조의 Domain ID를 사용하면,
Jetson에서 발행한 실제 상태를 PC가 구독하고 PC의 목표·Service 요청을 Jetson이 받는다.
이번에는 4주차 노드를 다시 실행하지 않고, 그 통신 환경 위에서 9주차 노드를 실행한다.

| 전달 방향 | 이번 주차에서 확인하는 내용 |
|---|---|
| Jetson → PC | `/real/joint_states`의 실제 6관절 측정값을 수신한다. |
| PC → Jetson → PC | `/robot/set_torque`에 OFF를 요청하고 성공 응답을 받는다. |
| PC → Jetson·PC | `/joint_targets` 하나를 실제 노드와 시뮬레이션 노드가 각각 받는다. |
| PC 내부 | `/sim/joint_states`와 추종·동기화 Service를 사용한다. |

`ROS_DOMAIN_ID`는 **4주차와 같은 `<각 조의 ID>`**를 모든 실행·명령 터미널에 적용한다.
`ROS_LOCALHOST_ONLY=0`, `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`도 양쪽에서 맞춘다.
환경 변수를 바꾸어도 이미 실행한 노드에는 반영되지 않으므로 노드를 재실행한다.
WSL의 CLI 조회 환경은 설정 변경 전 `ros2 daemon stop`, 변경 후 `ros2 daemon start`로 갱신한다.

학생은 PC의 WSL 터미널과 Jetson 로컬 터미널을 각각 사용한다. 4주차처럼 유선 연결과 각 장비의 IPv4·서브넷을 확인한 뒤 ROS 2 Topic·Service로 통신한다.
Ping은 기본 네트워크 도달 가능성 확인이며 ROS 2 데이터 수신까지 증명하지 않는다.
또한 PC의 시뮬레이션 상태만 보이는 것은 PC 내부 통신 확인이다.
**실제 상태 수신과 토크 OFF Service 응답을 모두 확인**한 뒤 실제 연동을 진행한다.
네트워크·mirrored networking·방화벽 준비는 `practice.md` 1.0절, 터미널별 환경 적용과 점검은 7절을 따른다.

### 2.2 PC의 시스템 Python과 MuJoCo venv

Windows PC에서도 프로그램 실행 위치는 WSL Ubuntu이다. MuJoCo Viewer 창은 WSLg를 통해 표시된다.
PC의 단독 MuJoCo 프로그램과 두 ROS 노드는 `~/week9/.venv`에 설치한 MuJoCo·NumPy·Matplotlib을 사용한다.
`~/week9/.venv`가 있으면 활성화하여 사용하고, 없는 경우에만 ROS Humble과 같은 시스템 Python 3.10으로 만든다. 생성 시 `--system-site-packages`를 사용하여 ROS 패키지도 읽는다.

`python3 mujoco_lab.py`는 활성화된 venv를 사용하지만, `ros2 run`의 실행 파일은 빌드 때 기록된 Python 경로를 사용할 수 있다.
따라서 venv 활성화만으로 모든 ROS 노드의 Python이 바뀐다고 가정하지 않는다.
이번 제공 Launch는 `python_executable` 인자(기본값: `~/week9/.venv/bin/python3`)를 두 PC 노드의 실행 명령 앞에 붙여 venv를 사용하도록 한다.
빌드는 시스템 colcon으로 수행하고 PC 노드는 제공 Launch로 실행한다. Jetson의 `arm_io`는 Jetson의 시스템 Python과 서보 SDK를 사용한다.
PC venv나 빌드 산출물을 Jetson으로 복사하지 않고 각 장비에서 소스를 빌드한다.

각 Python 파일의 역할은 `practice.md` 0절의 표를 참고한다.
`joints.yaml`은 프로그램 코드가 아니라 5주차와 같은 6관절 설정·시리얼 장치·속도 제한을 정의하는 설정 파일이다.

### 2.3 워크스페이스와 ROS 패키지 구조

PC와 Jetson 모두 `~/week9`를 워크스페이스로 사용하고, 그 안에 `week09_mujoco_ros` 패키지를 생성한다.
패키지 안의 같은 이름 폴더는 Python 모듈을 담는 폴더이다.

```text
~/week9/                                # 워크스페이스 루트, colcon 빌드 위치
├── week09_mujoco_ros/                   # ROS 패키지 루트
│   ├── setup.py
│   ├── setup.cfg
│   ├── package.xml
│   ├── resource/week09_mujoco_ros
│   ├── week09_mujoco_ros/               # __init__.py와 ROS 노드 Python 소스
│   ├── config/
│   ├── launch/
│   ├── models/                         # scene.xml과 assets/ 포함
│   ├── mujoco_lab.py                   # PC 단독 실습용
│   └── requirements.txt                # PC venv 설치용
├── .venv/                              # PC에만 생성
├── build/                              # 빌드 후 생성
├── install/                            # 빌드 후 생성
├── log/                                # 빌드 후 생성
└── results/                            # PC 비교 기록 후 생성
```

`ros2 pkg create`는 `~/week9`에서 실행하여 위 패키지 구조를 생성한다. 별도의 `src/` 폴더는 사용하지 않는다.
ROS 노드 소스는 `~/week9/week09_mujoco_ros/week09_mujoco_ros/`에, 패키지 설정·Launch·모델은 바깥쪽 패키지 루트에 둔다.
빌드는 `~/week9`에서 `--base-paths ./week09_mujoco_ros`로 패키지를 지정하며, 빌드 후에는 `~/week9/install/setup.bash`를 적용한다.
이는 패키지 탐색 시작 경로를 지정하는 [colcon의 `--base-paths` 옵션](https://colcon.readthedocs.io/en/released/reference/discovery-arguments.html)이다.
PC 단독 프로그램과 requirements 설치 명령은 `~/week9/week09_mujoco_ros`에서 실행한다. venv와 결과 저장 경로는 각각 `~/week9/.venv`, `~/week9/results`이다.
전체 파일 배치와 장비별 생성·빌드 명령은 `practice.md` 2·4·5절을 따른다.

---

## 3. 로봇 모델의 구성

### 3.1 모델 파일

URDF(Unified Robot Description Format)는 로봇의 링크·관절·형상 등을 설명하는 XML 기반 형식이다.
MJCF(MuJoCo Modeling Format)는 MuJoCo에서 로봇뿐 아니라 주변 물체·카메라·물리 계산 설정까지 정의하는 XML 기반 형식이다.
이번 실습은 URDF를 변환하지 않고, 제공된 MJCF의 `scene.xml`을 불러온다.

```text
models/
├── scene.xml          실행 진입점·조명·재질·움직이는 큐브 두 개
├── physicai_arm.xml   작업대·바구니·중력·시간 간격·Topcam
├── robot.xml          로봇 링크·관절·Actuator·그리퍼 기준점·Wristcam
├── physicai_arm.urdf  로봇 구조 참고용 URDF
└── assets/            XML이 참조하는 STL 형상·PNG 이미지
```

세 XML은 같은 폴더에 있다. `scene.xml`이 `physicai_arm.xml`을, `physicai_arm.xml`이 `robot.xml`을 `<include>`로 불러와 하나의 장면을 구성한다.
`physicai_arm.urdf`는 참고용이며 이번 프로그램이 직접 불러오지 않는다.

Viewer 제목은 `scene.xml`의 `<mujoco model="Week09 PhysicAI Arm">`에서 온다. 이전 제목 `moving_jaw_two_cube_contact`는 제공 장면의 기존 model 이름이며 수업 모드 이름이 아니다. `moving_jaw`라는 일부 링크·STL 이름은 실제 그리퍼의 움직이는 턱 부품을 가리키므로 그대로 유지한다.
몸체·모니터·탑카메라 지지대 형상은 `assets/PhysicAI-ARM-Lite-260303.stl`에 있고 `physicai_arm.xml`의 `workstation_visual`로 배치한다. 기존 group 4는 Viewer 기본 설정에서 숨겨져 몸체가 빠진 것처럼 보였다. 제공 모델은 기본 표시되는 group 2로 바꾸고 로봇과 몸체를 함께 볼 수 있도록 초기 시점을 조정했다. [MuJoCo geom group 설명](https://mujoco.readthedocs.io/en/stable/XMLreference.html#body-geom)
`top_view`는 카메라의 가상 시점이고 몸체 형상은 별도 mesh이다. `<camera>`를 추가하는 것만으로 카메라 외형이 생기는 것은 아니다.

STL·PNG는 장식용 파일만이 아니라 모델 로딩에 필요한 자산도 포함하므로 임의로 삭제하지 않는다.
바구니와 작업대는 제공 장면이며 이번 시간에 물체 집기·밀기 과제를 수행하지 않는다.
초록 `object_cube`와 파랑 `target_cube`는 각각 한 변 25 mm, 질량 11 g의 자유 물체이다.
각 큐브의 `size="0.0125 0.0125 0.0125"`는 반길이이므로 실제 한 변은 0.025 m이다.

### 3.2 Body·Geom·Joint·Actuator

로봇 모델은 하나의 그림 파일이 아니라, 물체와 그 연결 관계·형상·구동 방식을 함께 정의한 것이다.

| 요소 | 의미 | 이번 모델의 예 |
|---|---|---|
| Body | 위치와 방향을 가지며 로봇 링크나 물체를 구성하는 단위이다. | 팔 링크, `object_cube`, `target_cube` |
| Geom | 물체의 보이는 형상이나 접촉 계산에 사용하는 형상이다. | 로봇의 STL 형상, 큐브의 box 형상 |
| Joint | Body가 부모 Body에 대해 어떤 방향으로 움직일 수 있는지 정의한다. | 팔의 회전 관절, 큐브의 자유관절 |
| Actuator | 제어 입력에 따라 힘이나 토크를 만들어 관절 등을 구동한다. | 각 로봇 관절에 연결한 position Actuator |

예를 들어 큐브 Body에 box Geom을 붙여 형상을 정하고, `freejoint`를 두어 공간에서 이동·회전할 수 있게 한다.
큐브에는 Actuator가 없어도 중력·접촉·외력에 의해 움직일 수 있다.
반대로 Actuator가 없는 관절이라고 해서 반드시 고정된 것은 아니다.

보이는 형상과 충돌 계산용 형상은 다를 수 있다.
이번 작업대도 STL로 보이는 외형을 표현하고, 별도의 단순 형상으로 접촉을 계산하는 부분이 있다.
따라서 화면에서 보이는 외형만으로 충돌 계산의 정밀도를 판단하지 않는다.

### 3.3 Joint와 Actuator의 제어 범위

- **Joint**는 두 링크 간의 상대적인 운동을 허용하고 제어하는 기계적 연결부이다.
- **Actuator**는 Joint의 자유도를 구동하기 위해 힘, 토크, 또는 위치 제어 명령을 전달하는 입력 요소이다.
- 이번 모델은 6개의 회전 Joint에 같은 이름의 position Actuator를 하나씩 연결한다.

| 암 관절 5개 | 그리퍼 관절 1개 |
|---|---|
| `shoulder_pan`, `shoulder_lift`, `elbow_flex`, `wrist_flex`, `wrist_roll` | `gripper` |

예를 들어 `shoulder_pan` Actuator에 0.30 rad를 넣으면 물리 계산이 관절을 목표로 움직인다.
현재 위치를 즉시 0.30 rad로 덮어쓰는 것과는 다르다.

Joint의 `range`와 Actuator의 `ctrlrange`는 제한하는 대상이 다르다.

- Joint의 `range`는 관절 자체가 움직일 수 있는 각도 범위를 뜻한다.
- Actuator의 `ctrlrange`는 제어 입력의 최소·최대 범위를 뜻한다. 이번 position Actuator에서는 `data.ctrl`에 넣는 목표 각도의 범위이며 단위는 rad이다.

예를 들어 `shoulder_pan`의 `ctrlrange="-1.91986 1.91986"`는 약 −110°부터 +110°까지 목표 각도를 지정할 수 있다는 뜻이다.
0.30 rad는 이 범위 안이므로 명령할 수 있지만, 2.50 rad는 범위를 벗어난다.
단독 제어 프로그램 `mujoco_lab.py`는 목표를 적용하기 전에 이 범위를 검사하고, 범위 밖 요청은 오류 메시지와 함께 거부한다.

### 3.4 카메라와 장면 정렬의 범위

- `top_view`는 world에 고정된 Topcam이다. 위치는 `(0.29084, 0.03815, 0.5091310212)` m, 수직 시야각은 74.8°이다.
- Topcam에는 기존 테스트의 XY 단일 점 정렬값을 반영했다. 저장된 640×480 렌더링 기록은 빨간 기준점 `(296.025, 226.959)` px를 목표 `(296, 227)` px에 맞춘 결과이다.
- **조별 기기마다 미세한 오차가 있을 수 있으므로 추후 텀프로젝트 진행 시 모델링파일을 실제 topcam에서 관측되는 빨간 기준점의 pixel위치를 기준으로 모델링파일을 수정하기를 권장.** 
- `front_view`는 gripper 링크에 붙은 Wristcam이다. 링크 기준 위치는 `(0.00723152, -0.055, -0.061)` m, 수직 시야각은 45.6905°이다.

---

## 4. Model·Data와 물리 스텝

이 절은 제공 코드에서 사용하는 MuJoCo Python API를 읽기 위한 설명이다.
예시는 앞에서 만든 `model`·`data`와 조회한 인덱스를 다음 예시에서 이어서 사용한다.
새 실습 파일을 만들거나 제공된 제어 루프를 예시 코드로 교체하는 과제가 아니다.

### 4.1 모델 불러오기와 상태 생성

PC의 패키지 루트 `~/week9/week09_mujoco_ros`를 현재 작업 폴더로 두고 모델을 불러오는 기본 형태는 다음과 같다.

```python
import mujoco

model_path = "models/scene.xml"
model = mujoco.MjModel.from_xml_path(model_path)
data = mujoco.MjData(model)
```

- `MjModel.from_xml_path(경로)`는 XML과 연결된 자산을 읽고 계산에 사용할 모델 객체를 반환한다. 이번에는 `scene.xml`에서 시작하여 포함된 XML과 STL·PNG를 함께 읽는다.
- `MjData(model)`은 해당 모델의 초기 상태와 계산에 필요한 공간을 만든다. 모델을 먼저 만든 뒤 그 모델을 전달한다.
- 이 두 호출은 모델과 상태를 준비할 뿐, 물리 시간을 진행하거나 Viewer를 열지는 않는다.

`model`은 설계 정보이고 `data`는 실행 중 상태이다.
관절 이름·가동범위·시간 간격은 모델 정보이고, 현재 관절각·속도·시뮬레이션 시간은 상태이다.
초기 상태는 모델 정의를 따르므로 모든 배열이 0이라고 가정하지 않는다. 예를 들어 큐브의 초기 위치와 Quaternion도 `qpos`에 들어간다.

제공 코드의 `mujoco_lab.py`에서는 `load_model()`이 이 작업을 수행한다.
Bridge에서도 초기화할 때 모델과 상태를 생성한다. 초기 계산값을 갱신하는 `mj_forward()`는 4.4절에서 설명한다.

### 4.2 상태 배열과 제어 입력 읽고 쓰기

| 객체·배열 | 의미 | 이번 모델에서의 예 |
|---|---|---|
| `data.qpos` | 관절·자유 물체의 위치와 자세 | 로봇 각도는 rad, 큐브 위치는 m, 방향은 Quaternion이다. |
| `data.qvel` | 관절·자유 물체의 속도 | 로봇 각속도, 큐브 선속도·각속도이다. |
| `data.ctrl` | Actuator에 넣는 제어 입력 | 이번 position Actuator에서는 목표각이며 단위는 rad이다. |
| `data.time` | 누적된 시뮬레이션 시간 | 실제 PC 시계가 아니라 물리 계산으로 진행한 시간이며 단위는 s이다. |

각 배열의 길이는 모델의 다음 속성으로 확인한다.

```python
print(model.nq, model.nv, model.nu)
print(data.qpos.shape, data.qvel.shape, data.ctrl.shape)
```

이번 모델의 기대 결과는 `20 18 6`과 `(20,) (18,) (6,)`이다.
`nq`는 위치·자세 배열의 원소 수, `nv`는 속도 배열의 원소 수, `nu`는 이번 모델의 Actuator 입력 수이다.
관절 수 `njnt=8`과는 구분한다.
로봇 회전 관절 6개는 위치·속도 원소를 각각 6개 사용한다.
자유 큐브 하나는 XYZ 3개와 Quaternion 4개로 위치·자세 원소 7개, 선속도·각속도 원소 6개를 사용한다.
따라서 `nq=6+7×2=20`, `nv=6+6×2=18`이며 Actuator는 로봇용 6개만 존재한다.
ROS JointState에는 기존과 같이 로봇 6관절만 발행하고 큐브 자유 상태를 섞지 않는다.

`data.ctrl[:]`의 `[:]`는 기존 배열의 모든 원소를 가리킨다.
목표 배열을 여기에 대입하면 Actuator 입력 전체를 갱신한다. 이번에는 `model.nu`에 맞는 6개 목표값이 필요하며, 20개짜리 `qpos` 전체를 그대로 넣지 않는다.

현재 상태를 기록해 두려면 별도 복사본을 만든다.

```python
saved_qpos = data.qpos.copy()
```

`saved_qpos = data.qpos`만 사용하면 같은 배열을 가리키므로, 이후 시뮬레이션이 원본 배열을 갱신할 때 저장한 값도 바뀐다.
이 차이는 실험 시작 상태나 시간별 상태를 보관할 때 중요하다.

### 4.3 이름으로 Joint·Actuator와 배열 위치 찾기

XML의 관절 이름을 Python 배열의 인덱스로 바로 사용할 수는 없다.
`mj_name2id(model, 종류, 이름)`으로 객체 ID를 찾는다. `mjtObj`는 어떤 종류의 객체를 찾는지 지정한다.

```python
joint_id = mujoco.mj_name2id(
    model, mujoco.mjtObj.mjOBJ_JOINT, "shoulder_pan"
)
actuator_id = mujoco.mj_name2id(
    model, mujoco.mjtObj.mjOBJ_ACTUATOR, "shoulder_pan"
)
if joint_id < 0 or actuator_id < 0:
    raise ValueError("Joint 또는 Actuator 이름을 확인한다.")

qpos_index = int(model.jnt_qposadr[joint_id])
dof_index = int(model.jnt_dofadr[joint_id])
print(data.qpos[qpos_index], data.qvel[dof_index])
```

- `mjOBJ_JOINT`는 Joint를, `mjOBJ_ACTUATOR`는 Actuator를 찾도록 지정한다. 이번 모델은 서로 같은 이름을 사용하지만 별개의 객체이다.
- 이름을 찾지 못하면 `mj_name2id()`는 `-1`을 반환한다. 그대로 배열에 사용하면 Python에서 마지막 원소를 가리킬 수 있으므로 먼저 검사한다.
- `jnt_qposadr[joint_id]`는 해당 Joint 상태가 `qpos`에서 시작하는 위치이다.
- `jnt_dofadr[joint_id]`는 해당 Joint 속도가 `qvel`에서 시작하는 위치이다.
- Actuator 목표는 `data.ctrl[actuator_id]`에 넣는다. Joint ID를 `ctrl`의 인덱스로 사용하지 않는다.

제공 코드의 `inspect_model()`은 이 대응 관계를 출력하고, Bridge는 초기화할 때 이름으로 찾은 ID를 보관한다.
내부 인덱스를 외우기보다 이름으로 찾고 배열 위치를 확인하는 흐름을 이해한다.

### 4.4 목표 입력·물리 스텝·자세 갱신

#### 목표를 주고 움직임을 계산하는 경우

현재 각도가 0.10 rad인 관절에 0.30 rad 목표를 주었다고 가정한다.
이번 position Actuator는 목표와 현재 각도의 차이, 현재 속도 등을 반영하여 관절을 구동하는 토크를 만든다.
MuJoCo는 이 구동 토크와 중력·마찰·접촉 등을 함께 고려하여 속도와 위치를 갱신한다.
관절에는 관성과 구동력의 제한 등이 있으므로 목표를 주었다고 즉시 그 각도가 되지는 않는다.

```python
target = data.ctrl.copy()       # 다른 Actuator의 기존 목표를 유지한다.
target[actuator_id] = 0.30      # 앞에서 찾은 shoulder_pan의 목표이다.
data.ctrl[:] = target
mujoco.mj_step(model, data)
```

`mj_step(model, data)`은 준비된 입력으로 물리 계산을 수행하고 한 스텝만큼 상태와 시간을 진행한다.
한 번 호출했다고 목표각에 도달하는 것은 아니므로, 제공 코드에서는 반복문이나 Timer에서 계속 호출한다.
이 함수는 전달받은 `data`를 직접 갱신한다. `data = mujoco.mj_step(...)`처럼 반환값을 새 상태 객체로 받지 않는다.

#### 현재 자세를 직접 설정하는 경우

추종 모드에서는 움직이는 과정을 계산하는 대신, 실제로 읽은 관절각을 시뮬레이션의 현재 자세로 설정한다.
아래는 실제 측정각이 0.10 rad이라고 가정한 설명용 예시이다.

```python
data.qpos[qpos_index] = 0.10
data.qvel[dof_index] = 0.0
mujoco.mj_forward(model, data)
```

`mj_forward(model, data)`는 현재 상태를 기준으로 물체의 위치 변환·접촉·동역학 관련 계산값을 갱신하지만, 시간을 진행하는 적분은 수행하지 않는다.
`qpos`를 바꾼 뒤에는 그 상태에 맞는 관련 계산값도 갱신해야 한다.
이름 때문에 FK 전용 함수로 오해하지 않는다. 위치 계산도 포함하지만 그 밖의 물리 계산도 수행한다.

| 호출 | 시뮬레이션 시간 진행 | 이번 코드의 용도 |
|---|---|---|
| `mj_step(model, data)` | 한 스텝 진행한다. | 목표에 대한 독립적인 물리 응답을 계산한다. |
| `mj_forward(model, data)` | 진행하지 않는다. | 초기화·실제 자세 복사 뒤 관련 계산값을 갱신한다. |

Bridge의 `_apply_real_pose()`는 로봇의 위치를 복사하고 속도를 0으로 만들며, `ctrl`도 같은 관절각에 맞춘 뒤 `mj_forward()`를 호출한다.
위 예시의 `qpos` 직접 변경은 현재 자세 설정이지, 그 자세까지 움직이는 과정을 계산한 것이 아니다.
추종과 응답 비교의 차이는 6절에서 다시 연결한다.

목표를 넣기만 하고 `mj_step()`을 호출하지 않으면 물리 시간이 진행되지 않는다.
반대로 새 목표를 설정하지 않고 `mj_step()`을 호출하면 기존 입력으로 계산한다.
함수의 정확한 역할은 [MuJoCo 공식 API 설명](https://mujoco.readthedocs.io/en/stable/APIreference/APIfunctions.html#mj-forward)을 참고한다.
제어기 수식·게인 튜닝·접촉 계산 알고리즘의 상세 내용은 이번 학습 범위가 아니다.

### 4.5 Viewer API로 현재 상태 표시

Viewer API는 `import mujoco.viewer`로 불러온다.

| 호출 | 역할 |
|---|---|
| `mujoco.viewer.launch_passive(model, data)` | Viewer를 열고 제어에 사용할 핸들을 반환한다. 사용자 코드는 계속 실행한다. |
| `viewer.is_running()` | Viewer가 실행 중인지 확인하여 True 또는 False를 반환한다. |
| `viewer.sync()` | 모델·상태와 Viewer의 표시·입력 이벤트를 동기화한다. 물리 스텝을 대신하지 않는다. |
| `viewer.close()` | Viewer 종료를 요청한다. |

`passive` 방식에서는 사용자 코드가 물리 계산과 실행 주기를 담당한다.
따라서 창을 열기만 해서는 로봇이 자동으로 움직이지 않는다.
제공 코드에서는 물리 상태를 계산한 뒤 다음과 같은 조건으로 화면을 갱신한다.

```python
if viewer is not None and viewer.is_running():
    viewer.sync()
```

`viewer is not None`은 비GUI 실행에서 Viewer가 없는 경우를 구분하는 조건이다.
MuJoCo Viewer를 닫는 것과 ROS 노드를 종료하는 것은 별개이므로, 종료는 8절의 절차를 따른다.
실제 Viewer 생성·종료는 제공된 `viewer_context()`와 Bridge의 관리 코드를 사용한다.
Bridge의 `viewer.lock()`은 Viewer와 상태를 공유할 때 변경을 보호하는 장치이며, 스레드 동기화의 상세 구현은 이번 범위가 아니다.

사용 방법은 [MuJoCo 공식 Python Viewer 설명](https://mujoco.readthedocs.io/en/stable/python.html#passive-viewer)을 참고한다.

### 4.6 시뮬레이션 시간과 화면·ROS 주기의 차이

물체의 연속적인 움직임을 컴퓨터에서 계산할 때는 시간을 작은 간격으로 나누어 상태를 갱신한다.
이번 모델의 `timestep=0.002`는 물리 시간 2 ms를 뜻한다.
따라서 500스텝을 계산하면 시뮬레이션 시간은 1초 진행한다.
이 계산을 실제 시간 1초 안에 마치는지는 PC 성능과 계산량에 따라 달라진다.

```python
print(model.opt.timestep)  # 이번 모델은 0.002 s이다.
print(data.time)           # 지금까지 진행한 시뮬레이션 시간이다.
```

`model.opt.timestep`은 한 번의 물리 스텝이 진행하는 시간 간격이고, `data.time`은 누적된 시뮬레이션 시간이다.
`time.sleep()`은 실제 프로그램을 잠시 기다리게 할 뿐 `data.time`을 증가시키지 않는다.
제공 단독 제어 코드는 `mj_step()`으로 물리 시간을 진행한 뒤, 너무 빠르게 실행되지 않도록 남는 시간만 기다린다.

| 구분 | 이번 실습에서의 의미 |
|---|---|
| 물리 스텝 | 한 번에 시뮬레이션 시간 2 ms를 계산한다. |
| Bridge Timer | 약 5 ms마다 호출되며 경과 시간에 맞춰 물리 스텝을 여러 번 처리한다. |
| ROS 상태 발행 | 시뮬레이션 관절값을 기본 50 Hz로 전송한다. 모든 물리 스텝을 전송하는 것은 아니다. |
| Viewer 갱신 | 현재 상태를 화면에 반영한다. 물리 계산·ROS 발행과 같은 횟수일 필요는 없다. |

시간 간격을 작게 하면 같은 시뮬레이션 시간을 진행하기 위해 더 많은 스텝이 필요하다.
계산 정확도와 안정성은 모델·계산 방법·접촉 조건 등에도 영향을 받으므로, 간격만 줄인다고 모든 문제가 해결되지는 않는다.
이번 실습에서는 제공된 시간 간격을 유지하고 각 주기의 역할을 구분한다.

---

## 5. ROS–MuJoCo 연결

### 5.1 Topic과 Service

| 이름 | 타입 | 역할 |
|---|---|---|
| `/joint_targets` | `sensor_msgs/msg/JointState` | 실제·시뮬레이션 공통 목표 요청 |
| `/real/joint_states` | `sensor_msgs/msg/JointState` | 실제 서보 측정값, 기본 20 Hz |
| `/sim/joint_states` | `sensor_msgs/msg/JointState` | MuJoCo 관절값, 기본 50 Hz |
| `/robot/set_torque` | `std_srvs/srv/SetBool` | 실제 토크 ON/OFF |
| `/sim/set_follow_real` | `std_srvs/srv/SetBool` | 실제 자세의 연속 복사 ON/OFF |
| `/sim/sync_to_real` | `std_srvs/srv/Trigger` | 실제 자세를 한 번 복사 |

일부 관절만 목표 메시지에 포함하면 해당 관절의 목표만 변경하고 나머지는 이전 목표를 유지한다.
형식·이름·유한값·허용 범위가 잘못된 목표는 거부한다.
실제 토크가 OFF이면 실제 로봇은 목표를 적용하지 않는다.

### 5.2 Callback과 반복 처리

```text
/joint_targets 도착 → callback이 목표 검사·저장
                 ├─ arm_io: 30 Hz에서 속도 제한 보간 → 서보 쓰기
                 └─ Bridge: 저장된 목표 → ctrl → 여러 mj_step() → 상태 발행
```

Bridge의 Timer와 물리 스텝·상태 발행 주기의 차이는 4.6절을 참고한다.
PC가 느려지면 스텝 수에 상한이 있어 시뮬레이션이 실제 시간보다 느려질 수 있다.

---

## 6. 두 모드의 차이

### 6.1 Real-to-Sim 추종

실제 토크를 OFF로 두고 로봇을 받쳐 천천히 움직인다.
Bridge는 실제 로봇 6관절의 값을 해당 `qpos`와 `ctrl`에 복사하고 로봇 쪽 `qvel`만 0으로 만든다.
이 모드에서는 독립적인 물리 스텝을 진행하지 않는다.
따라서 추종 중에는 큐브의 물리 운동도 일시 정지한다. 추종을 끄면 다시 물리 계산을 진행한다.

```text
손으로 실제 자세 변경 → 실제 상태 수신 → MuJoCo 자세 복사 → 화면 표시
```

따라서 두 로봇이 비슷하게 보이는 것은 물리 모델이 실제를 정확히 예측했다는 증거가 아니다.
실제 값이 모델 범위를 벗어나면 범위 안으로 제한되어 표시된다.
실제 상태가 오래되면 추종 시작을 거부하며, 추종 중 수신이 끊기면 마지막 시뮬레이션 자세를 유지한다.
이 기능은 실제 로봇의 토크를 자동으로 해제하는 watchdog이 아니다.

### 6.2 동일 목표 응답 비교

추종을 OFF로 바꾼 뒤 실제 로봇을 현재 자세에서 토크 ON으로 유지한다. 제공 코드는 최신 관절값을 읽고 모든 서보의 현재 자세 목표를 먼저 기록한 뒤 토크를 켠다. 설치된 SDK의 일반 `write_position()`은 토크를 먼저 켜므로 초기 자세 유지에는 그대로 사용하지 않는다.
이후 자세 A로 준비하고 준비 회차 기록이 끝나면 시뮬레이션을 동기화한다. 자세 B는 각 관절 약 20~46도 이동하는 목표이며 기존 속도 제한은 유지한다. 도구는 B를 보내기 전에 실제·시뮬레이션이 A의 각 관절 ±0.15 rad 안인지 확인한다. 각도 범위와 이 확인은 실제 충돌 회피를 보장하지 않으므로 조교가 장비별 A·B와 이동 공간을 확인한다.
`sync_to_real`은 로봇 6관절의 위치를 복사하고 해당 관절 속도를 초기화한다. 큐브 상태는 덮어쓰지 않는다.
접촉·하중·마찰 등 모든 물리 상태까지 동일하게 만드는 기능은 아니다.

같은 `/joint_targets` 요청을 한 번 보내면 실제와 시뮬레이션이 각자 반응한다. 실습 2에서는 A에서 B로 6관절을 함께 변경하여 베이스·팔·손목·그리퍼의 움직임을 관찰한다. 자세는 `config/comparison_poses.yaml`에 정의하며, `comparison_goal --pose B --send`가 한 번 발행한다. `--send` 없이 실행하면 숫자 확인만 한다.
실제 제어기는 속도 제한 보간과 서보 내부 제어를 사용한다.
시뮬레이션은 position Actuator에 목표를 전달한다.
**최종 요청은 같지만 내부 제어 과정까지 같지는 않다.**

현재 MuJoCo 모델은 실제 서보보다 훨씬 빨리 목표에 도달해 화면에서는 순간이동처럼 보일 수 있다. B 목표를 받으면 `qpos`를 덮어쓰는 대신 `ctrl`에 목표를 넣고 `mj_step()`으로 운동을 계산한다. 반면 이동 전 `sync_to_real`은 시작 자세를 한 번 즉시 복사한다. 실습 1은 실제 자세를 계속 복사한다. 이 세 동작을 구분하고 응답 비교는 기록된 그래프의 초기 구간까지 확인한다.

또한 모델의 형상이 실물과 비슷해도 질량·마찰·관성·구동 특성까지 정확히 같다는 뜻은 아니다.
시뮬레이션의 설정값은 실물을 표현하기 위한 근사이고, 실제 장비에는 통신 지연과 측정 오차 등도 존재한다.
이처럼 시뮬레이션과 실제 사이에 생기는 차이는 이후 Sim-to-Real에서도 고려해야 하는 문제이다.

이 실습은 현재 구성의 전체 응답 차이를 관찰하는 실습이다.
정확한 모터 지연 측정이나 물리 파라미터 식별, 제어기 성능의 공정한 대결로 해석하지 않는다.

---

## 7. 그래프와 지표 해석

### 7.1 기록과 기준 시각

`comparison_goal`은 목표 발행 직전 PC 시각을 `header.stamp`에 넣는다. Comparator는 이를 0초로 두고 기본 8초를 기록한다.
최근 2초의 실제·시뮬레이션 수신 이력을 보존하여, 목표 callback이 늦게 처리되어도 목표 이전 상태를 0초 기준값으로 사용하고 이후 표본을 복구한다. timestamp가 0인 직접 발행은 callback 시각을 사용하며 초기 응답이 잘릴 수 있다는 경고를 남긴다.
상태 표본의 기준은 **PC에 메시지가 도착한 시간**이며 장치의 동작 시각을 정밀하게 동기화한 시간이 아니다. 목표 timestamp도 PC에서 생성해야 하며 Jetson의 측정 timestamp를 이 시간축에 그대로 섞지 않는다.
YAML의 `time_origin`과 `target_callback_delay_s`에 기준 방식과 목표 callback 지연을 저장한다.
서로 다른 발행 주기의 상태를 공통 50 Hz 시간축에 보간하여 비교한다.
50 Hz로 정리했다고 실제 로봇을 50 Hz로 측정한 것은 아니다.

시작 전 전체 6관절 상태가 최신이어야 한다.
기록 중 두 상태 중 하나라도 0.5초 이상 끊기거나 새 목표가 들어오면 회차를 무효 처리하고 저장하지 않는다.
이는 기록의 유효성 검사이며 실제 모터를 정지시키는 기능이 아니다.

### 7.2 그래프와 RMSE

그래프는 비교 기준선 `target`, 실제 측정값 `real`, 시뮬레이션값 `simulation`을 표시한다.
기준선은 목표 Topic에서 받은 요청이며 실제 노드의 수락 확인 메시지가 아니다.
이번 회차에서 명령하지 않은 관절의 기준선은 기록 시작 시 실제값으로 채운 참고선이다.
지표는 이번 목표에 포함한 관절에 대해서만 계산한다.
그래프마다 세로축 배율과 오프셋이 다를 수 있으므로 축의 숫자·단위를 함께 읽는다.

RMSE는 두 응답 곡선 사이의 각도 차이를 하나의 값으로 요약한다.
작을수록 이번 기록에서 두 곡선이 비슷하지만 모델이 모든 상황에서 정확하다는 뜻은 아니다.
단위는 rad이며 목표 추종 오차가 아니라 실제값과 시뮬레이션값 사이의 오차이다.

### 7.3 응답 지연과 정착 시간

- 응답 지연: 시작값에서 0.01 rad 이상 변한 최초 시점을 사용한다.
- 시작부터 목표와의 차이가 0.01 rad보다 작으면 코드에서는 지연을 0으로 처리한다. 움직임이 필요한 목표로 비교한다.
- `실제 지연 − 시뮬레이션 지연`이 양수이면 이번 측정에서 실제 응답이 더 늦게 관찰된 것이다.
- 움직임이 관찰되지 않으면 지연이 `null` 또는 `N/A`일 수 있다.
- 정착 시간은 목표 ±0.03 rad 안에 최소 0.25초 연속 머무르는 첫 구간의 시작 시점이다. 이후 다시 벗어나지 않는다는 뜻은 아니다.
- 8초 안에 조건을 만족하지 못하면 정착 시간도 `null`이다. 상세 분석은 선택 활동으로 둔다.

차이에는 통신·발행 주기·보간·PC 부하·실제 속도 제한·서보 제어·마찰·하중 등이 함께 반영된다.
어느 한 원인이 전부라고 단정하지 않는다.

### 7.4 결과 파일

| 파일 | 내용 |
|---|---|
| `trial_*.csv` | 시간과 각 관절의 target·real·sim |
| `trial_*.png` | 6관절 응답 그래프 |
| `trial_*_metrics.yaml` | 명령한 관절의 RMSE·지연·정착 시간과 계산 조건 |

이번 수업은 특정 RMSE 이하를 합격 기준으로 삼지 않는다.
유효한 기록을 만들고 차이를 설명하는 것을 완료 기준으로 삼는다.

---

## 8. 범위와 종료 원칙

- URDF 변환·접촉 튜닝·강화학습·물체 조작은 이번 필수 범위가 아니다.
- MuJoCo·NumPy·PyYAML·Matplotlib을 사용한다. torch·torchvision·YOLO는 필요하지 않는다.
- Viewer 창을 닫아도 Bridge는 계속 실행될 수 있다. 종료는 실행 터미널의 `Ctrl+C`로 수행한다.
- 통신 장애에서는 토크 해제 Service 자체가 전달되지 않을 수 있다. Jetson의 로컬 터미널에서 드라이버를 정상 종료하고 현장 안전 절차를 따른다.
- 종료 전에 로봇을 받치고 토크 OFF 성공을 확인한다. 정상 종료의 정리 코드는 강제 종료·전원 장애에서의 안전을 보장하지 않는다.
