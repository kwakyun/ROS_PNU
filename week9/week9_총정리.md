# [9주차] MuJoCo 로봇 시뮬레이션과 ROS 2 연동 — 총정리

> 출처: `week9_MuJoCo_ROS2.pptx`(강의 슬라이드), `lecture.md`(수업 내용), `practice.md`(실습 안내서), `source_code/`(제공 코드 + TODO 완성본 `week09_mujoco_ros/`)

---

## 0. 한눈에 보기

| 항목 | 내용 |
|---|---|
| 주제 | MuJoCo 물리 시뮬레이션 + ROS 2 Bridge + 실제 로봇(Real)과 시뮬레이션(Sim) 응답 비교 |
| 장비 | PC(Windows WSL2 Ubuntu, ROS 2 Humble, MuJoCo venv) ↔ 유선 Ethernet ↔ Jetson(`arm_io`) ↔ USB Serial `/dev/ttyACM0` ↔ 6축 로봇팔(Feetech STS3215) |
| 실습 1 | MuJoCo 단독 제어 + **Real-to-Sim 추종**(실제 자세를 가상 로봇에 복사) |
| 실습 2 | **동일 목표 응답 비교**(자세 A→B 목표를 실제·Sim에 동시에 주고 8초 기록) |
| 코드 TODO | 1·2 `mujoco_lab.py`(ctrl 대입, mj_step), 3·4 `mujoco_ros_bridge.py`(Publisher, Subscriber), 5·6·7 `setup.py`/`package.xml` 등록 |
| 결과물 | `~/week9/results/trial_*.csv`, `trial_*.png`, `trial_*_metrics.yaml` |

### 수업 목표 (lecture 0절)
- MuJoCo의 **물리 계산**과 단순한 **자세 표시**의 차이를 설명한다.
- Joint와 Actuator, 현재 위치 `qpos`와 목표 입력 `ctrl`을 구분한다.
- `MjModel`, `MjData`, `mj_step()`의 역할을 설명한다.
- ROS Topic과 MuJoCo 배열을 연결하고, 실제 자세를 시뮬레이션에 반영한다.
- 같은 목표에 대한 실제·시뮬레이션 응답을 기록하고 차이를 해석한다.

---

## 1. 왜 시뮬레이션인가 (PPT 4~6)

**Action Data Scarcity — 로봇 행동 데이터는 부족하다**
- LLM은 웹 문서·책·코드·이미지·영상 등 인터넷 규모 데이터(수십만 년 분량)로 학습할 수 있다.
- 로봇 데이터는 현실 상호작용의 제약 때문에 수 년 단위의 제한된 경험만 모을 수 있다.
- action을 어떤 형태(language? video?)로 표현할지도 체계적이지 않고, 인터넷에 자연스럽게 쌓이지도 않는다.
- 실제 로봇으로 시행착오를 반복하면 시간이 오래 걸리고, 물체 파손·장비 손상·안전사고 위험이 있으며 인력·실험 환경 비용이 크다.

**시뮬레이션 활용** — 가상 실험은 실제 장비 실험을 준비하는 과정
- 로봇 모델과 관절 동작 사전 확인
- 목표 자세와 이동 과정 반복 실험
- 제어 결과 기록·비교
- 실제 로봇 실험 전 안전성 점검

---

## 2. MuJoCo 기본 개념

### 2.1 MuJoCo란
- **Mu**lti-**Jo**int dynamics with **Co**ntact — 여러 관절로 연결된 물체의 운동과 접촉을 계산하는 물리 엔진.
- 2021년 DeepMind가 인수해 무료로 공개. 강체·관절·중력·접촉 계산, XML 모델, Python API, Viewer 제공.
- 단순히 모양을 그리는 것이 아니라, **현재 상태 + 입력 → 시간이 지난 뒤의 상태**를 계산한다. 질량·관절 구조·구동 특성·중력·마찰·접촉 조건이 계산에 영향을 준다.

### 2.2 자세를 보여 주는 것 vs 운동을 계산하는 것 ★

| 방식 | 예시 | 의미 | 이번 실습 |
|---|---|---|---|
| 자세를 직접 설정 | 실제 관절각을 받아 가상 로봇에 복사 | 받은 자세를 표시만 함. 이동 과정을 예측하지 않음 | **Real-to-Sim 추종** (실습 1) |
| 물리 계산 진행 | 목표각을 주고 관절이 움직이는 과정을 계산 | 구동력·중력·마찰을 반영해 다음 상태를 구함 | **동일 목표 응답 비교** (실습 2) |

- 화면이 비슷하다고 물리 모델이 정확하다고 판단하면 안 된다.
- **Viewer는 표시 도구일 뿐**이다. Viewer 없이도 물리 계산이 가능하고, 화면 갱신만으로는 물리 시간이 진행되지 않는다.

### 2.3 MuJoCo 구성요소 (PPT 8)

| 구성 | 내용 |
|---|---|
| 모델 파일 | MJCF 또는 URDF로 로봇과 환경 작성 → MuJoCo Compiler가 검사 후 실행 가능한 모델로 변환 |
| `mjModel` | **변하지 않는 모델 정보**: Body·Joint·Geom·Actuator 구조, 질량·관성·관절 범위·중력·Solver 설정 |
| `mjData` | **계속 변하는 상태**: 시간, `qpos`, `qvel`, `ctrl`, 접촉 정보, 힘·센서 결과. Step마다 갱신 |

### 2.4 `mj_step()` 한 번에 일어나는 일 (PPT 9)
1. **현재 상태와 제어 입력 확인** — 관절 위치·속도, Actuator 입력 읽기
2. **자세 계산** — 관절 상태로 각 Body·Geom의 위치·방향 계산
3. **충돌·접촉 탐색** — 겹치거나 맞닿은 Geom을 찾아 Contact 생성
4. **힘·구속조건 계산** — 중력·마찰·Actuator·관절 제한·접촉력
5. **가속도 계산** — 작용하는 힘으로 다음 순간의 가속도 결정
6. **수치 적분** — 가속도로 속도·위치 갱신, 시뮬레이션 시간 증가

---

## 3. 로봇 모델 (URDF · MJCF)

### 3.1 URDF vs MJCF (PPT 10~11)

| | URDF | MJCF |
|---|---|---|
| 정의 | ROS에서 로봇의 구조·연결 관계를 표현하는 XML | MuJoCo가 물리 시뮬레이션에 직접 사용하는 XML |
| 표현 | Link 형상·질량, Joint, 관절축·가동범위, 시각화·충돌 Mesh | 강체·관절, 화면·충돌 형상, **Actuator**, 중력·시간·Solver 등 환경 설정 |
| 용도 | 구조 확인, ROS 도구 연동, 물리 설정은 별도 보완 | 로봇 + 주변 물체 + 카메라 + 물리 설정까지 |
| 이번 실습 | `physicai_arm.urdf`는 **참고용**(직접 불러오지 않음) | `scene.xml`을 불러옴(URDF 변환 안 함) |

### 3.2 모델 파일 구조

```text
models/
├── scene.xml          실행 진입점·조명·재질·움직이는 큐브 두 개 (model="Week09 PhysicAI Arm")
├── physicai_arm.xml   작업대·바구니·중력·timestep·Topcam
├── robot.xml          로봇 링크·관절·Actuator·그리퍼 기준점·Wristcam
├── physicai_arm.urdf  참고용 URDF
└── assets/            STL 형상 15개 + PNG 1개 (모델 로딩에 필요, 삭제 금지)
```
- 포함 관계: `scene.xml` → `<include>` `physicai_arm.xml` → `<include>` `robot.xml`
- 몸체·모니터·탑카메라 지지대는 `PhysicAI-ARM-Lite-260303.stl`, `workstation_visual`(group 2 → 기본 표시)
- 큐브: 초록 `object_cube`, 파랑 `target_cube` — 한 변 25 mm(`size="0.0125..."`는 **반길이**), 질량 11 g, 자유 물체(`freejoint`)

### 3.3 Body · Geom · Joint · Actuator

| 요소 | 의미 | 예 |
|---|---|---|
| Body | 위치·방향을 가지는 링크/물체 단위 | 팔 링크, 큐브 |
| Geom | 보이는 형상 또는 접촉 계산용 형상 | STL, box |
| Joint | Body가 부모에 대해 움직이는 방식 | 팔 회전 관절, 큐브 자유관절 |
| Actuator | 제어 입력에 따라 힘·토크를 만들어 관절 구동 | 각 관절의 position Actuator |

- 큐브는 Actuator가 없어도 중력·접촉·외력으로 움직인다. Actuator가 없다고 고정된 것이 아니다.
- 보이는 형상(STL)과 충돌 형상(단순 도형)은 다를 수 있다.

### 3.4 관절 6개와 범위

| 암 관절 5개 | 그리퍼 1개 |
|---|---|
| `shoulder_pan`, `shoulder_lift`, `elbow_flex`, `wrist_flex`, `wrist_roll` | `gripper` |

- 6개 회전 Joint에 **같은 이름**의 position Actuator가 하나씩 연결된다(이름은 같아도 별개의 객체).
- Joint `range` = 관절 자체의 가동 범위 / Actuator `ctrlrange` = `data.ctrl`에 넣는 **목표각 범위**(rad).
- 예: `shoulder_pan ctrlrange="-1.91986 1.91986"` ≈ ±110°. 0.30 rad는 가능, 2.50·3.0 rad는 거부.
- Actuator에 0.30 rad를 넣는 것은 **목표 설정**이지 현재 위치를 0.30으로 덮어쓰는 것이 아니다.

### 3.5 카메라
- `top_view`: world 고정 Topcam, 위치 (0.29084, 0.03815, 0.5091) m, fovy 74.8°. 빨간 기준점 (296, 227) px 기준으로 정렬됨. 조별 기기 오차가 있으니 텀프로젝트 때 실제 topcam 기준점 pixel로 모델 보정 권장.
- `front_view`: gripper 링크에 붙은 Wristcam, fovy 45.69°.

---

## 4. MuJoCo Python API

### 4.1 모델·상태 생성
```python
import mujoco
model = mujoco.MjModel.from_xml_path("models/scene.xml")  # XML+STL+PNG 읽기
data = mujoco.MjData(model)                               # 초기 상태·계산 공간
```
- `model` = 설계 정보(관절 이름·범위·timestep), `data` = 실행 중 상태(관절각·속도·시간).
- 두 호출은 물리 시간을 진행하거나 Viewer를 열지 않는다.

### 4.2 상태 배열

| 배열 | 의미 | 이번 모델 |
|---|---|---|
| `data.qpos` | 관절·자유 물체의 위치·자세 | 로봇 rad, 큐브 m + Quaternion |
| `data.qvel` | 속도 | 각속도, 큐브 선·각속도 |
| `data.ctrl` | Actuator 입력 | position Actuator → 목표각(rad) |
| `data.time` | 누적 시뮬레이션 시간 | 실제 PC 시계가 아님 |

**`nq=20, nv=18, nu=6, njnt=8`** — 계산:
- 로봇 회전관절 6개 → qpos 6, qvel 6
- 자유 큐브 1개 → qpos 7(XYZ 3 + Quaternion 4), qvel 6(선속도 3 + 각속도 3)
- `nq = 6 + 7×2 = 20`, `nv = 6 + 6×2 = 18`, `nu = 6`(로봇 Actuator만), `njnt = 6 + 2 = 8`
- ROS JointState에는 로봇 6관절만 발행한다(큐브 상태 섞지 않음).

```python
data.ctrl[:] = target          # [:] = 기존 배열 전체 원소 갱신 (길이 nu=6)
saved = data.qpos.copy()       # 복사본. saved = data.qpos 는 같은 배열을 가리켜 값이 같이 바뀜
```

### 4.3 이름으로 ID·인덱스 찾기
```python
jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "shoulder_pan")
aid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "shoulder_pan")
if jid < 0 or aid < 0: raise ValueError(...)   # 못 찾으면 -1 → 그대로 쓰면 마지막 원소를 가리킴!
qpos_i = int(model.jnt_qposadr[jid])   # qpos 시작 위치
dof_i  = int(model.jnt_dofadr[jid])    # qvel 시작 위치
data.ctrl[aid] = 0.30                  # ctrl은 Actuator ID로 접근 (Joint ID 아님)
```

### 4.4 `mj_step` vs `mj_forward` ★

```python
# (a) 목표를 주고 운동 계산 — 응답 비교 모드
target = data.ctrl.copy(); target[aid] = 0.30
data.ctrl[:] = target
mujoco.mj_step(model, data)        # 한 스텝(2 ms) 진행, data를 직접 갱신 (반환값 X)

# (b) 현재 자세 직접 설정 — 추종 모드
data.qpos[qpos_i] = 0.10
data.qvel[dof_i] = 0.0
mujoco.mj_forward(model, data)     # 시간 진행 없이 관련 계산값만 갱신
```

| 호출 | 시간 진행 | 용도 |
|---|---|---|
| `mj_step(model, data)` | 한 스텝 진행 | 목표에 대한 독립적인 물리 응답 계산 |
| `mj_forward(model, data)` | 진행 안 함 | 초기화·실제 자세 복사 뒤 위치·접촉·동역학 값 갱신 (FK 전용 아님) |

- 목표만 넣고 `mj_step()`을 안 부르면 시간이 진행되지 않는다. 한 번 부른다고 목표에 도달하지 않으므로 반복 호출한다.
- 새 목표 없이 `mj_step()`을 부르면 기존 입력으로 계산한다.

### 4.5 Viewer (passive)

| 호출 | 역할 |
|---|---|
| `mujoco.viewer.launch_passive(model, data)` | Viewer 열고 핸들 반환, 사용자 코드는 계속 실행 |
| `viewer.is_running()` | 실행 중 여부 |
| `viewer.sync()` | 상태를 화면에 반영(물리 스텝 대신 X) |
| `viewer.close()` | 종료 요청 |
| `viewer.lock()` | Viewer와 상태 공유 시 변경 보호 |

passive 방식에서는 사용자 코드가 물리 계산·주기를 담당하므로 창만 열어서는 로봇이 움직이지 않는다. Viewer를 닫아도 Bridge 노드는 계속 실행될 수 있다.

### 4.6 시간과 주기

| 구분 | 값 / 의미 |
|---|---|
| 물리 스텝 `model.opt.timestep` | **0.002 s (2 ms)** → 500스텝 = 시뮬레이션 1초 |
| Bridge Timer | 약 5 ms마다, 경과 시간만큼 여러 스텝 처리(최대 25스텝, 경과 최대 0.05 s) |
| `/sim/joint_states` 발행 | 50 Hz |
| `/real/joint_states` 발행 | 20 Hz (`publish_hz`) |
| `arm_io` 제어 루프 | 30 Hz (`control_hz`), heartbeat 10 Hz |
| Viewer 갱신 | 최대 60 Hz |

`time.sleep()`은 `data.time`을 증가시키지 않는다. PC가 느리면 스텝 상한 때문에 시뮬레이션이 실제 시간보다 느려질 수 있다.

---

## 5. 시스템 구조 — 5주차 대비 변경

| 기능 | 5주차 | 9주차 |
|---|---|---|
| 실제 로봇 노드 | `joint_controller` | `arm_io` |
| 실제 측정값 | `/joint_states` | `/real/joint_states` |
| 시뮬레이션 상태 | 없음 | `/sim/joint_states` |
| 관절 목표 | `/joint_targets` | `/joint_targets` (실제·Sim **공통**) |
| 토크 제어 | `/safety/torque_enable` Topic | `/robot/set_torque` **Service** (`SetBool`) |
| 결과 표시 | 실제값·요청값 | 실제·시뮬레이션·비교 기준값 |

```text
PC (WSL2 Ubuntu)                                Jetson
명령 터미널 ── /joint_targets ───────────────> arm_io ── FeetechBus ── 서보
                 ├─> mujoco_ros_bridge          └─ /real/joint_states ──┐
                 │        └─ /sim/joint_states ─────────────────────────┤
                 └──────────────────────────────────────────────────────┤
                                                      real_sim_comparator
                                                              └─ CSV·PNG·YAML
```
- `/dev/ttyACM0`은 Jetson의 `arm_io` 하나만 연다. PC 노드는 시리얼 포트를 열지 않는다.
- MuJoCo는 ROS Topic을 직접 처리하지 않으므로 **Bridge 노드**가 ROS 메시지 ↔ MuJoCo Python API를 연결한다(PPT 12).

### 5.1 Topic · Service (PPT 14: 연속 데이터는 Topic, 한 번의 모드 변경은 Service)

| 이름 | 타입 | 역할 |
|---|---|---|
| `/joint_targets` | `sensor_msgs/msg/JointState` | 실제·Sim 공통 목표 |
| `/real/joint_states` | `sensor_msgs/msg/JointState` | 실제 서보 측정값, 20 Hz |
| `/sim/joint_states` | `sensor_msgs/msg/JointState` | MuJoCo 관절값, 50 Hz |
| `/robot/set_torque` | `std_srvs/srv/SetBool` | 실제 토크 ON/OFF |
| `/sim/set_follow_real` | `std_srvs/srv/SetBool` | 실제 자세 연속 복사 ON/OFF |
| `/sim/sync_to_real` | `std_srvs/srv/Trigger` | 실제 자세 1회 복사 |

- 일부 관절만 보내면 해당 관절만 바뀌고 나머지는 이전 목표 유지.
- 형식·이름·중복·유한값·범위가 잘못된 목표는 거부.
- 토크 OFF이면 실제 로봇은 목표를 무시. 추종 ON이면 Bridge는 목표를 거부.

### 5.2 Callback과 반복 처리
```text
/joint_targets 도착 → callback이 목표 검사·저장
                 ├─ arm_io: 30 Hz에서 속도 제한 보간 → 서보 쓰기
                 └─ Bridge: 저장된 목표 → ctrl → 여러 mj_step() → 상태 발행
```

---

## 6. 두 모드: Real-to-Sim 추종 vs 동일 목표 응답 비교 (PPT 15~16)

| | Real-to-Sim 추종 (실습 1) | 시작 자세 동기화 | 동일 목표 응답 비교 (실습 2) |
|---|---|---|---|
| 호출 | `/sim/set_follow_real true` | `/sim/sync_to_real` | `comparison_goal --pose B --send` |
| 동작 | 실제 6관절을 `qpos`·`ctrl`에 **계속 복사**, `qvel`=0, `mj_forward` | 실제 자세를 **한 번** 즉시 복사 | 목표를 `ctrl`에 넣고 `mj_step()`으로 **운동 계산** |
| 물리 스텝 | 정지(큐브도 정지) | — | 진행 |
| 실제 토크 | OFF (손으로 천천히 움직임) | ON (A 유지) | ON |
| 의미 | 화면이 같아도 모델 정확성의 증거 아님 | 큐브·접촉·마찰까지 맞추지는 않음 | 최종 요청은 같지만 내부 제어 과정은 다름 |

- 추종 중 실제 상태가 0.5 s 이상 끊기면 마지막 자세 유지(추종 시작은 거부). 모델 범위 밖 실제값은 범위 안으로 clamp. **watchdog이 아니다**(토크 자동 해제 안 함).
- 실제 로봇: `joints.yaml`의 관절별 **속도 제한 보간** + 서보 내부 제어 / MuJoCo: position Actuator에 최종 목표를 바로 전달 → **Sim이 순간이동처럼 훨씬 빨리 도달**할 수 있다.

**응답이 달라지는 이유 (PPT 16)**
- **시스템 동역학**: 질량·관성·마찰·감쇠
- **구동기 특성**: 모터 출력 한계, 제어 Gain
- **모델 불일치**: 시뮬레이션은 근사 → 모델링 안 된 특성
- **시간적 특성**: 제어 주기·통신 지연·센서 샘플링

→ 이후 **Sim-to-Real**에서도 고려할 문제. 이번 실습은 전체 응답 차이의 관찰이지 정밀 모터 지연 측정이나 파라미터 식별이 아니다.

---

## 7. 소스코드 정리

### 7.1 파일 역할

| 파일 | 실행 위치 | 역할 |
|---|---|---|
| `mujoco_lab.py` | PC(venv, 직접 실행) | ROS 없는 MuJoCo 단독 실습: `inspect` / `run` / `sequence` — **TODO 1·2** |
| `mujoco_ros_bridge.py` | PC(Launch) | 목표·실제 자세 → MuJoCo, `/sim/joint_states` 발행 — **TODO 3·4** |
| `real_sim_comparator.py` | PC(Launch) | 실제·Sim 기록, CSV·PNG·YAML 저장 |
| `comparison_goal.py` | PC | 자세 A·B 확인, `--send` 시 PC timestamp 담은 목표 1회 발행 |
| `arm_io.py` | Jetson | 서보 읽기/쓰기, 토크 Service |
| `hardware_interface.py` | Jetson(모듈) | Feetech SDK 통신, rad↔tick 변환 |
| `mujoco_compare.launch.py` | PC | Bridge + Comparator 실행, `prefix`로 venv Python 지정 |
| `config/joints.yaml` | 공통 | 관절 ID·부호·영점·범위·속도 제한·주기 |
| `config/comparison_poses.yaml` | 공통 | 자세 A·B |

### 7.2 `mujoco_lab.py` — TODO 1·2

```python
def run_segment(model, data, target, duration, label, viewer):
    end_time = data.time + duration
    while data.time < end_time:
        ...
        # TODO 1: 목표 배열을 Actuator 입력에 대입 (qpos를 덮어쓰지 않는다!)
        data.ctrl[:] = (
            target
        )
        # TODO 2: 물리 상태를 한 스텝(2 ms) 진행
        mujoco.mj_step(
            model,
            data,
        )
        ... viewer.sync(), 남는 시간만큼 sleep
```
- `check_target()`: Actuator `ctrlrange` 밖 목표 거부 → 비정상 종료 코드
- `inspect_model()`: njnt·nq·nv·nu·timestep, 관절/Actuator 대응 출력
- `sequence`: `comparison_poses.yaml`의 A → B → A 미리보기

### 7.3 `mujoco_ros_bridge.py` — TODO 3·4

```python
# 상수
TARGET_TOPIC = "/joint_targets"
REAL_STATE_TOPIC = "/real/joint_states"
SIM_STATE_TOPIC = "/sim/joint_states"
REAL_STATE_TIMEOUT = 0.5
STATE_PUBLISH_HZ = 50.0

# TODO 3: 시뮬레이션 상태 Publisher
self._state_publisher = self.create_publisher(
    JointState,
    SIM_STATE_TOPIC,
    10,
)
# TODO 4: 공통 목표 Subscriber
self._target_subscription = self.create_subscription(
    JointState,
    TARGET_TOPIC,
    self._on_target,
    10,
)
```
| 메서드 | 기능 |
|---|---|
| `_on_target` | 추종 중이면 거부, name/position 길이·중복·이름·유한값·`ctrlrange` 검사 후 `self._target`에 저장 |
| `_on_real_state` | 최신 실제 상태 저장, 추종 중이면 `_apply_real_pose()` |
| `_apply_real_pose` | 실제값 clamp → `qpos`·`ctrl` 복사, 로봇 `qvel`=0, `mj_forward` (큐브는 안 건드림) |
| `_step_physics` | 추종 중이면 정지·유지, 아니면 경과 시간/timestep만큼(≤25) `ctrl=target` + `mj_step` |
| `_publish_state` | 6관절 `qpos`→position, `qvel`→velocity, `qfrc_actuator`→effort |
| `_set_follow_real` / `_sync_to_real` | Service 처리(실제 상태가 완전하고 최신이어야 성공) |

### 7.4 `real_sim_comparator.py`
| 상수 | 값 |
|---|---|
| `RECORD_SECONDS` | 8.0 s |
| `SAMPLE_HZ` | 50 Hz (공통 시간축 보간) |
| `HISTORY_SECONDS` | 2.0 s (목표 이전 상태 보존) |
| `STATE_TIMEOUT` | 0.5 s (끊기면 무효) |
| `RESPONSE_THRESHOLD` | 0.01 rad (응답 지연 기준) |
| `SETTLING_TOLERANCE` / `HOLD` | ±0.03 rad / 0.25 s |
| `OUTPUT_DIR` | `~/week9/results` |

### 7.5 `comparison_goal.py`
- `START_TOLERANCE = 0.15` rad: B 발행 전 실제·Sim이 A의 각 관절 ±0.15 rad 안인지 확인
- 구독자 3개(`arm_io`, `mujoco_ros_bridge`, `real_sim_comparator`)와 최신 6관절 상태 확인
- 발행 직전 PC 시각을 `header.stamp`에 넣음 → Comparator의 0초 기준
- `--send` 없으면 숫자만 출력

### 7.6 `arm_io.py` + `hardware_interface.py` (Jetson)
- 시작 시 토크 OFF(`Servo torque is disabled on startup`).
- `_on_target`: 토크 OFF면 무시, 범위는 `joints.yaml`의 `limit_rad`로 검사.
- `_control_step`(30 Hz): 한 주기 최대 이동량 `max_vel_rad_s × (1/30)`만큼 목표에 접근(속도 제한 보간), 도달 후 heartbeat 10 Hz로 재전송.
- `enable_torque_at_current_pose`: 최신 실측값 읽기 → 모드·토크 OFF 확인 → **모든 서보에 현재 자세 목표를 먼저 기록(`WritePosEx`)** → 토크 ON(주소 40). SDK `write_position()`은 토크를 먼저 켜서 튈 수 있으므로 사용하지 않음. 실패 시 토크 OFF.
- rad ↔ tick 변환 (STS3215, 4096 tick/rev, center 2048):
  ```python
  tick = round(2048 + (rad - zero_offset) * sign * 4096 / (2π))
  rad  = (tick - 2048) * 2π / 4096 * sign + zero_offset
  ```

### 7.7 `joints.yaml` 요약

| 관절 | ID | limit_rad | max_vel_rad_s |
|---|---|---|---|
| shoulder_pan | 1 | ±1.91986 | 0.35 |
| shoulder_lift | 2 | ±1.74533 | 0.35 |
| elbow_flex | 3 | ±1.69 | 0.35 |
| wrist_flex | 4 | ±1.65806 | 0.45 |
| wrist_roll | 5 | −2.74385 ~ 2.84121 | 0.55 |
| gripper | 6 | −0.174533 ~ 1.74533 | 0.60 |

`device: /dev/ttyACM0`, `baudrate: 1000000`, `publish_hz: 20`, `control_hz: 30`, `heartbeat_hz: 10`

---

## 8. 패키지 등록 — TODO 5·6·7

### 패키지 구조
```text
~/week9/                          # 워크스페이스 (여기서 빌드, src/ 없음)
├── week09_mujoco_ros/            # ROS 패키지 루트
│   ├── setup.py / setup.cfg / package.xml
│   ├── resource/week09_mujoco_ros
│   ├── week09_mujoco_ros/        # 노드 Python 소스
│   ├── config/  launch/  models/(assets/)
│   ├── mujoco_lab.py  requirements.txt   # PC 전용
├── .venv/ (PC만)  build/ install/ log/  results/
```

### TODO 5·6 — `setup.py`
```python
import os
from glob import glob
...
data_files=[
    ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
    ('share/' + package_name, ['package.xml']),
    # TODO 5
    (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    (os.path.join('share', package_name, 'models'),
     glob('models/*.xml') + glob('models/*.urdf')),
    (os.path.join('share', package_name, 'models', 'assets'),
     glob('models/assets/*.stl') + glob('models/assets/*.png')),
],
entry_points={
    'console_scripts': [
        # TODO 6
        'arm_io = week09_mujoco_ros.arm_io:main',
        'comparison_goal = week09_mujoco_ros.comparison_goal:main',
        'mujoco_ros_bridge = week09_mujoco_ros.mujoco_ros_bridge:main',
        'real_sim_comparator = week09_mujoco_ros.real_sim_comparator:main',
    ],
},
```
- `hardware_interface.py`(모듈)와 `mujoco_lab.py`(직접 실행)는 등록하지 않는다.
- `data_files`는 Python이 아닌 파일을 install 위치에 배치 → 안 하면 `ros2 launch`·모델 경로 조회 실패.

### `setup.cfg`
```ini
[develop]
script_dir=$base/lib/week09_mujoco_ros
[install]
install_scripts=$base/lib/week09_mujoco_ros
```

### TODO 7 — `package.xml`
```xml
<exec_depend>rclpy</exec_depend>
<exec_depend>sensor_msgs</exec_depend>
<exec_depend>std_srvs</exec_depend>
<exec_depend>ament_index_python</exec_depend>
<exec_depend>launch</exec_depend>
<exec_depend>launch_ros</exec_depend>
<exec_depend>python3-matplotlib</exec_depend>
<exec_depend>python3-numpy</exec_depend>
<exec_depend>python3-yaml</exec_depend>
```
`package.xml`은 의존성 **선언**이지 설치가 아니다. MuJoCo는 `requirements.txt`로 venv에 설치한다.

> 빌드 성공 ≠ TODO 완성. 등록 TODO를 비워도 빌드는 성공할 수 있으므로 실행 파일 4개·설치 자산까지 확인한다.

---

## 9. 환경 준비

### 9.1 네트워크 (PPT 22~28, practice 1.0)
| 연결 | 방식 |
|---|---|
| Arm – Jetson | USB Serial `/dev/ttyACM0` |
| Jetson – PC | 유선 Ethernet (USB-Ethernet 어댑터: Ethernet 쪽 Jetson, USB 쪽 PC) |
| Windows – WSL2 | Mirrored Networking |

1. **Jetson**: Settings → Network → Wired → IPv4 Manual, Address 임의, Netmask `255.255.255.0`, Gateway·DNS 공란
2. **Windows**: `Win+R` → `ncpa.cpl` → USB 이더넷 → TCP/IPv4 → Jetson과 마지막 자리만 다른 IP, 서브넷 `255.255.255.0`
3. **WSL mirrored**:
   ```powershell
   notepad $env:USERPROFILE\.wslconfig     # [wsl2] networkingMode=mirrored
   wsl --shutdown
   # 관리자 PowerShell
   Set-NetFirewallHyperVVMSetting -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -DefaultInboundAction Allow
   ```
4. `ping <Jetson_IP>` — Ping은 네트워크 도달만 확인하고 ROS 통신을 증명하지 않는다.

### 9.2 PC venv (Python 3.10, ROS 패키지도 읽도록)
```bash
cd ~/week9 && source /opt/ros/humble/setup.bash
/usr/bin/python3.10 -m venv --system-site-packages .venv   # 없을 때만
source ~/week9/.venv/bin/activate
touch ~/week9/.venv/COLCON_IGNORE
cd ~/week9/week09_mujoco_ros && python3 -m pip install -r requirements.txt
# mujoco==3.10.0, numpy>=1.24,<2, PyYAML, matplotlib
```

### 9.3 Python 구분 ★
- `python3 mujoco_lab.py` → 현재 터미널(venv) Python
- `ros2 run` 실행 파일 → 빌드 때 기록된 **shebang(시스템 Python)** → venv 활성화만으로는 바뀌지 않음 → `No module named mujoco`
- 해결: Launch의 `prefix=[python_executable]`(기본 `~/week9/.venv/bin/python3`)로 Bridge·Comparator 실행

### 9.4 빌드
```bash
# PC
cd ~/week9 && source /opt/ros/humble/setup.bash
/usr/bin/python3 /usr/bin/colcon build --symlink-install \
  --base-paths ./week09_mujoco_ros --packages-select week09_mujoco_ros
source ~/week9/install/setup.bash
ros2 pkg executables week09_mujoco_ros     # 실행 파일 4개 확인

# Jetson (source ~/ros2_base/install/setup.bash 후 동일하게 colcon build)
```
PC와 Jetson은 각자 빌드한다(산출물·venv 복사 금지). Jetson에는 `mujoco_lab.py`·`requirements.txt` 불필요.

### 9.5 조별 통신 설정 (모든 터미널)
```bash
export ROS_DOMAIN_ID="<조 번호>"
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```
PC에서는 설정 변경 전 `timeout 10s ros2 daemon stop` → 설정 → `timeout 10s ros2 daemon start`. 이미 실행 중인 노드에는 반영되지 않으므로 재실행한다.

---

## 10. 실습 진행 순서 요약

### 10.1 MuJoCo 단독 (PC)
```bash
cd ~/week9/week09_mujoco_ros && source ~/week9/.venv/bin/activate
python3 mujoco_lab.py inspect                                         # njnt=8 nq=20 nv=18 nu=6 timestep=0.002
python3 mujoco_lab.py run --joint shoulder_pan --target 0.30 --duration 5   # 정상 목표
python3 mujoco_lab.py run --joint shoulder_pan --target 3.0 --duration 2    # 범위 밖 → 거부
python3 mujoco_lab.py sequence --segment-duration 3                   # A→B→A 미리보기
# Viewer 없이 진단: --no-viewer (GUI 확인을 대체하지 않음)
```

### 10.2 노드 실행
| 터미널 | 명령 | 확인 |
|---|---|---|
| Jetson 1 | `ros2 run week09_mujoco_ros arm_io` | `Publishing ... /real/joint_states`, `Torque service`, 시작 시 토크 OFF |
| PC 1 | `ros2 topic echo --once /real/joint_states` → `ros2 launch week09_mujoco_ros mujoco_compare.launch.py` | 실제 상태 수신, `MuJoCo loaded: nq=20, nv=18, nu=6` |
| PC 2 | `ros2 node list`, `topic list -t`, `service list -t`, 토크 OFF 호출 | 노드 3개, `success: true` |

통신 확인 기준: **실제 상태 수신(Jetson→PC) + 토크 OFF Service 성공(PC↔Jetson 양방향)**. `/sim/joint_states`만 보이는 것은 PC 내부 통신이다.

### 10.3 실습 1 — Real-to-Sim 추종
```bash
ros2 service call /robot/set_torque std_srvs/srv/SetBool "{data: false}"
ros2 service call /sim/set_follow_real std_srvs/srv/SetBool "{data: true}"
# 로봇을 받치고 천천히 움직이며 Viewer 관찰 (추종 중 목표 발행 금지)
ros2 service call /sim/set_follow_real std_srvs/srv/SetBool "{data: false}"
```

### 10.4 실습 2 — 동일 목표 응답 비교

| 관절 | A [rad] | B [rad] | 이동량 |
|---|---:|---:|---:|
| shoulder_pan | 0.00 | 0.65 | 약 37° |
| shoulder_lift | −0.50 | −0.85 | 약 20° |
| elbow_flex | 0.80 | 1.15 | 약 20° |
| wrist_flex | 0.40 | 0.05 | 약 20° |
| wrist_roll | 0.00 | 0.80 | 약 46° |
| gripper | 0.20 | 0.65 | 약 26° |

```bash
ros2 run week09_mujoco_ros comparison_goal --pose B              # 숫자 확인만
ros2 service call /sim/set_follow_real std_srvs/srv/SetBool "{data: false}"
ros2 service call /robot/set_torque std_srvs/srv/SetBool "{data: true}"   # 현재 자세 유지 토크 ON
ros2 run week09_mujoco_ros comparison_goal --pose A --send       # 실제도 A로 이동, Trial saved까지 대기(준비 회차)
ros2 service call /sim/sync_to_real std_srvs/srv/Trigger "{}"    # 시작 자세 1회 동기화
ros2 topic info /joint_targets --no-daemon                       # Subscription count: 3
ros2 run week09_mujoco_ros comparison_goal --pose B --send       # 비교 회차, 8초 동안 새 목표 금지
ls -lh ~/week9/results
```

### 10.5 안전 종료
```bash
ros2 service call /sim/set_follow_real std_srvs/srv/SetBool "{data: false}"
ros2 service call /robot/set_torque std_srvs/srv/SetBool "{data: false}"
# 로봇을 받친 상태에서 성공 확인 → PC Launch, Jetson arm_io 각각 Ctrl+C
```
통신 장애로 OFF가 전달되지 않으면 Jetson 로컬에서 노드를 정상 종료한다. 목표를 추가로 보내 해결하려 하지 않는다.

---

## 11. 결과 해석

### 11.1 기록 방식
- 0초 = `comparison_goal`이 넣은 **PC 목표 timestamp** (`time_origin: pc_target_header_stamp`)
- 상태 시간 = **PC 도착 시각**(장치 동작 시각을 정밀 동기화한 것이 아님)
- 최근 2초 이력으로 목표 이전 상태를 0초 기준값으로 사용 → callback이 늦어도 초기 응답 보존
- 20 Hz(실제)·50 Hz(Sim)를 공통 50 Hz 축으로 보간 (실제를 50 Hz로 측정했다는 뜻은 아님)
- **무효 회차**: 상태 0.5 s 이상 끊김, 기록 중 새 목표 → 저장 안 함 (정지 명령이 아님)

### 11.2 지표

| 지표 | 정의 | 해석 |
|---|---|---|
| RMSE (`real_vs_sim_rmse_rad`) | 실제 곡선과 Sim 곡선 사이의 각도 차이 | **목표 추종 오차가 아님**. 작으면 이번 기록에서 비슷했다는 뜻 |
| 응답 지연 | 시작값에서 0.01 rad 이상 변한 최초 시점 | `real − sim` 지연이 **양수면 실제가 더 늦음** |
| 정착 시간 | 목표 ±0.03 rad 안에 0.25 s 연속 머무른 첫 구간 시작 | 8초 안에 미충족 시 `null` |

- 지표는 명령한 관절만 계산. 명령하지 않은 관절의 target 선은 시작 실제값으로 채운 참고선.
- 그래프마다 세로축 배율·오프셋(`1e-6`, `+4e-1`)이 달라 선 높이만으로 비교하면 안 된다.
- 특정 RMSE 이하가 합격 기준이 아니다. **유효한 기록 + 차이 설명**이 완료 기준.

### 11.3 결과 파일
| 파일 | 내용 |
|---|---|
| `trial_*.csv` | 시간별 각 관절 target·real·sim |
| `trial_*.png` | 6관절 응답 그래프 |
| `trial_*_metrics.yaml` | RMSE·지연·정착 시간, `active_joints`, `time_origin`, `target_callback_delay_s` |

### 11.4 결과 기록 항목
명령 관절·목표 / 실제·Sim 시작값 / RMSE / 지연 차이(값·부호) / 곡선 차이(누가 빠른지, 진동·잔차) / **가능한 원인 2가지**(속도 제한 보간, 서보 내부 제어, 통신·발행 주기, 마찰·하중, PC 부하 등)

---

## 12. 자주 나는 문제

| 증상 | 확인 |
|---|---|
| TODO 줄에서 SyntaxError·TypeError | `### TODO ###`를 값·인자로 바꿨는지, 쉼표·괄호 |
| 실행 파일·Launch·모델 없음 | TODO 5·6, 재빌드, `source install/setup.bash` |
| ROS 노드만 `No module named mujoco` | Launch로 실행했는지, `python_executable` 경로 |
| venv에서 rclpy 실패 | ROS 환경 먼저 source, `include-system-site-packages = true`, Python 3.10 |
| XML·Mesh 오류 | models·assets 전체 복사, 경로·대소문자 |
| Topic은 보이는데 값이 없음 | 이름 발견 ≠ 데이터 수신. Jetson 로컬 echo와 비교 |
| Domain 변경 후 목록 이상 | daemon stop → 설정 → start, 노드 재실행 |
| 비교 중 Sim이 실제 자세를 복사 | follow 모드 false |
| B 목표에서 Sim이 순간이동 | 정상(Sim은 속도 제한 보간 없음). 그래프 초기 구간 확인 |
| 목표 B가 발행 안 됨 | A 준비·기록 종료·동기화, ±0.15 rad, 구독자 3개 |
| 실제 로봇만 안 움직임 | 토크 ON 성공, 목표 수락 로그 |
| 지연·정착 `null` | 충분한 목표 변화, 8초 안의 움직임 |

---

## 13. 핵심 개념 체크 (시험·발표 대비)

1. **`qpos` vs `ctrl`?** `qpos`는 현재 위치(상태), `ctrl`은 Actuator 목표 입력. position Actuator에서 `ctrl=0.3`은 즉시 0.3이 되는 게 아니라 물리 계산으로 접근한다.
2. **`mj_step` vs `mj_forward`?** step은 시간을 한 스텝(2 ms) 진행, forward는 시간 진행 없이 현재 상태 기준 계산값만 갱신.
3. **`nq=20`, `nv=18`인 이유?** 회전관절 6(6/6) + 자유 큐브 2개(각 7/6). Quaternion 4개 때문에 nq > nv.
4. **`mj_name2id`가 −1이면?** 이름 없음. 그대로 인덱스로 쓰면 Python에서 마지막 원소를 가리키므로 반드시 검사.
5. **추종이 비슷하게 보이면 모델이 정확한가?** 아니다. 추종은 자세 복사일 뿐 물리 예측이 아니다.
6. **`sync_to_real`과 `set_follow_real`의 차이?** 1회 복사 vs 연속 복사(물리 정지).
7. **왜 Launch에서 venv Python을 prefix로?** `ros2 run` 실행 파일은 빌드 시 shebang(시스템 Python)을 쓰기 때문.
8. **RMSE의 의미?** 실제 vs Sim 곡선 차이(rad). 목표 추종 오차가 아니다.
9. **토크 ON에서 현재 자세 목표를 먼저 쓰는 이유?** 이전 목표가 남아 있으면 토크 ON 순간 로봇이 튈 수 있기 때문.
10. **5주차 토크 Topic을 보내면?** 9주차 `arm_io`는 반응하지 않는다. `/robot/set_torque` Service를 써야 한다.

---

## 14. 완료 체크리스트
- [ ] 코드 TODO 1~4 완성, `ctrl`과 `mj_step()`의 역할 설명
- [ ] 등록 TODO 5~7 완성, 실행 파일 4개·설치 자산·의존성 확인
- [ ] PC venv import와 Launch `python_executable` 확인
- [ ] 모든 터미널 같은 Domain ID, WSL daemon 갱신
- [ ] 실제 상태 PC 수신 + 토크 OFF Service 성공
- [ ] 로봇 6관절·자유 큐브 2개·Actuator 6개 구분, 단일 관절 이동 확인
- [ ] 범위 밖 목표 거부 확인
- [ ] 5주차와 달라진 상태 Topic·토크 Service 구분
- [ ] 토크 OFF에서 Real-to-Sim 추종 확인
- [ ] A–B–A 미리보기 → 실제 A 준비·동기화 → B 비교 1회
- [ ] 이번 회차 CSV·PNG·metrics YAML 확인
- [ ] 지연·RMSE 의미와 응답 차이 원인 2가지 설명
- [ ] 토크 해제 성공 후 노드 정상 종료
