# [5주차] 관절 단위 위치제어와 자세 유지 — 수업 내용

## 0. 수업 개요

### 수업 목표

이번 수업을 마치면 다음 내용을 설명하고 수행할 수 있어야 한다.

- 관절 공간 제어와 작업 공간 제어의 차이를 설명한다.
- `joint_controller`와 `FeetechBus`의 역할을 구분한다.
- `/joint_states`, `/joint_targets`, `/safety/torque_enable`의 데이터 흐름을 설명한다.
- Subscriber callback과 주기적인 Control Timer를 분리하는 이유를 설명한다.
- 현재 자세에서 안전하게 토크를 활성화하고 단일·다중 관절 목표각을 전송한다.
- 관절별 최대 속도에 따른 속도 제한 보간 과정을 설명한다.
- Soft Limit으로 범위 밖 목표를 거부하고 명시적으로 토크를 해제한다.
- Plotter의 현재값과 요청값을 구분하고 CSV·PNG 결과를 해석한다.

### 실습 완료 기준

다음 항목을 모두 확인하면 실습이 완료된 것이다.

- `joint_controller`와 `joint_plotter`가 정상적으로 실행된다.
- Plotter에서 6개 관절의 현재값을 확인한다.
- 토크 활성화 시 로봇이 갑자기 다른 자세로 이동하지 않고 현재 자세를 유지한다.
- 정상 범위의 단일·다중 관절 요청을 전송하고 현재값이 요청값을 추종하는 것을 확인한다.
- Soft Limit을 벗어난 요청이 거부되고 현재 자세가 유지되는 것을 확인한다.
- 토크 해제 후 위치 제어가 중단되는 것을 확인한다.
- `results/`에 CSV와 PNG가 저장된다.

### 이번 주차의 안전 범위

이번 주차에는 실제 서보의 토크를 활성화하고 관절을 움직인다. 목표값의 단위는
degree가 아니라 radian이다. 로봇의 가동범위 안에 사람과 물체가 없는지 확인한 뒤
명령을 전송하며, 이상 동작이 발생하면 목표값을 추가로 보내지 않고 먼저
`/safety/torque_enable`에 `False`를 발행한다.

---

## 1. 전체 제어 구조

`joint_controller`는 하나의 시리얼 연결로 현재 관절값을 읽고, 안전 검사를 통과한
목표값을 실제 서보에 전송한다. `joint_plotter`는 ROS 2 Topic만 구독하며 시리얼
포트를 열지 않는다.

```text
명령 터미널
  ├── /safety/torque_enable (Bool) ───────────────┐
  └── /joint_targets (JointState, 요청값) ────────┼──> joint_controller
                                                  │      ├─ Soft Limit 검사
                                                  │      ├─ 속도 제한 보간
                                                  │      └─ FeetechBus
                                                  │             │
                                                  │             └─ /dev/ttyACM0
                                                  │
                                                  └──> joint_plotter
                                                        요청값 표시

joint_controller ── /joint_states (JointState) ───────> joint_plotter
                                                        현재값 표시
```

중요한 원칙은 다음과 같다.

- `/dev/ttyACM0`은 `joint_controller`만 연다.
- Subscriber callback은 요청을 검사하고 저장한다.
- 실제 토크 변경과 서보 쓰기는 30 Hz Control Timer에서 처리한다.
- Plotter의 주황 점선은 Controller가 수락한 값이 아니라 `/joint_targets`로 들어온
  원본 요청값이다.

### 주요 파일의 역할

| 파일 | 역할 |
|---|---|
| `hardware_interface.py` | Feetech SDK 연결, radian–tick 변환, 위치 읽기·쓰기, 토크 해제를 담당한다. |
| `joint_controller.py` | 현재 관절값 발행, 목표·토크 요청 수신, 안전 검사와 제어 루프를 담당한다. |
| `joint_plotter.py` | 현재값과 요청값을 그래프로 표시하고 CSV·PNG를 저장한다. |
| `joints.yaml` | 관절 이름, Servo ID, 변환값, Soft Limit, 최대 속도와 제어 주기를 정의한다. |

---

## 2. Controller와 하드웨어 인터페이스

### 2.1 `FeetechBus` 객체

`bus`는 ROS 2 객체가 아니라 `hardware_interface.py`에 정의된 `FeetechBus`의
인스턴스이다. `main()`은 설정을 읽고 시리얼 연결을 만든 뒤 Controller에 전달한다.

```text
joints.yaml 읽기
       │
       ▼
JointConfig 생성
       │
       ▼
FeetechBus(config) 생성 ── /dev/ttyACM0 연결
       │
       ▼
JointPositionController(bus)
```

```python
config = load_joint_config(config_path)
bus = FeetechBus(config)
node = JointPositionController(bus)
```

Controller는 전달받은 객체를 `self._bus`에 저장하고 다음 기능을 사용한다.

| 메서드 | 역할 |
|---|---|
| `read_positions()` | 6개 서보의 현재 위치를 radian 배열로 반환한다. |
| `write_positions()` | 전체 관절 목표를 서보 tick으로 변환해 기록한다. |
| `disable_torque()` | 전체 서보의 토크를 해제한다. |
| `close()` | 시리얼 연결을 닫는다. |

ROS 2 통신과 제어 상태는 `JointPositionController`가 담당하고, 실제 장치 통신은
`FeetechBus`가 담당한다.

### 2.2 Publisher 1개와 Subscriber 2개

| Topic | 타입 | 방향 | 역할 |
|---|---|---|---|
| `/joint_states` | `sensor_msgs/msg/JointState` | Controller → 외부 | 실제로 측정한 6개 관절값을 기본 20 Hz로 발행한다. |
| `/joint_targets` | `sensor_msgs/msg/JointState` | 외부 → Controller | 하나 이상의 관절 이름과 요청 목표각을 전달한다. |
| `/safety/torque_enable` | `std_msgs/msg/Bool` | 외부 → Controller | `True`로 토크 활성화를 요청하고 `False`로 토크 해제를 요청한다. |

목표 메시지에 일부 관절만 포함하면 해당 관절의 목표만 바뀌고 나머지 관절은 이전
목표를 유지한다. 단, 메시지에 알 수 없는 관절이나 범위 밖 값이 하나라도 있으면
그 메시지 전체를 거부한다.

---

## 3. Callback과 Timer의 제어 흐름

실행 중 제어 흐름을 담당하는 joint_controller.py의 다섯 메서드는 다음과 같다.

| 메서드 | 호출 시점 | 역할 |
|---|---|---|
| `_read_and_publish_state()` | State Timer가 기본 20 Hz로 호출한다. | 실제 관절값을 읽고 `_measured`를 갱신한 뒤 `/joint_states`를 발행한다. |
| `_on_torque()` | 토크 요청 메시지가 도착하면 호출한다. | Bool 값을 `_torque_requested`에 저장한다. |
| `_on_target()` | 관절 요청 메시지가 도착하면 호출한다. | 형식·관절 이름·Soft Limit을 검사하고 `_target`을 갱신한다. |
| `_apply_torque_request()` | `_control_step()` 내부에서 호출한다. | 저장된 요청과 현재 상태를 비교해 토크 켬·끔을 처리한다. |
| `_control_step()` | Control Timer가 기본 30 Hz로 호출한다. | 토크 요청 적용, 속도 제한 보간, 서보 명령과 Heartbeat 전송을 처리한다. |

```text
State Timer (20 Hz)
  └─ _read_and_publish_state()
       ├─ read_positions()
       └─ /joint_states 발행

/safety/torque_enable 도착
  └─ _on_torque()
       └─ 토크 요청 저장

/joint_targets 도착
  └─ _on_target()
       └─ 요청 검사 후 목표 저장

Control Timer (30 Hz)
  └─ _control_step()
       ├─ _apply_torque_request()
       ├─ 속도 제한 보간
       └─ write_positions()
```

Subscriber callback이 직접 시리얼 통신을 수행하지 않는 이유는 하드웨어 변경을
하나의 Control Timer에서 순서대로 처리하기 위해서이다. 이 구조를 사용하면 현재값
확보, 최초 목표 설정, 목표 보간과 토크 변경을 일관된 흐름으로 관리할 수 있다.

### 3.1 토크 활성화 요청

`Bool(data=True)`가 도착하면 `_on_torque()`는 요청값만 저장한다. 다음 Control Timer는
최근 측정 자세를 최초 목표와 최초 명령으로 설정하고 `write_positions()`를 호출한다.
따라서 다른 위치로 갑자기 이동하지 않고 토크를 활성화한 순간의 자세에서 위치
유지를 시작한다.

```text
Bool true
  → 토크 요청 저장
  → 다음 Control Timer에서 요청 확인
  → 현재 측정 자세를 최초 목표로 설정
  → write_positions(현재 자세)
  → 서보 내부 위치제어 시작
```

현재 관절값을 아직 읽지 못했다면 토크를 활성화하지 않고 측정값이 들어올 때까지
기다린다.

### 3.2 목표각 요청

`_on_target()`은 메시지를 받으면 다음 순서로 검사한다.

1. `name`과 `position` 배열이 비어 있지 않고 길이가 같은지 확인한다.
2. 모든 관절 이름이 `joints.yaml`에 정의되어 있는지 확인한다.
3. 모든 값이 해당 관절의 `limit_rad` 범위 안에 있는지 확인한다.
4. 토크가 활성화되어 있고 초기 목표가 준비되었는지 확인한다.
5. 요청에 포함된 관절만 기존 목표에서 변경한다.

검사를 통과한 목표는 다음 Control Timer부터 실제 서보 명령에 반영된다.

---

## 4. 관절 공간 제어와 속도 제한 보간

### 4.1 작업 공간과 관절 공간

```text
[작업 공간]                                     [관절 공간]
(x, y, z, roll, pitch, yaw)                     (q1, q2, q3, q4, q5, q6)
            └──────── 역운동학 ────────────────> 개별 관절 목표각
```

- **관절 공간 제어**는 각 관절의 각도를 직접 목표값으로 지정한다.
- **작업 공간 제어**는 로봇 말단의 위치와 자세를 목표로 지정하며 관절값으로 변환하는
  역운동학이 필요하다.

이번 주차는 역운동학을 사용하지 않고 `/joint_targets`에 관절 이름과 radian 값을 직접
전송하는 관절 공간 제어를 다룬다.

### 4.2 속도 제한 보간

현재 Controller는 애플리케이션 레벨에서 별도의 가속·감속 속도 상태를 계산하지 않는다.
각 Control Timer 주기마다 관절별 최대 속도로 이동할 수 있는 각도만 계산한다.

```text
dt       = 1 / control_hz
max_step = max_vel_rad_s × dt
error    = target - commanded
```

- `|error| <= max_step`이면 다음 명령을 목표값으로 설정한다.
- `|error| > max_step`이면 목표 방향으로 `max_step`만 이동한다.

```text
직전 명령 ── max_step ──> 다음 명령 ── max_step ──> ... ──> 최종 목표
```

이 방식은 한 번의 큰 위치 변화를 여러 개의 작은 명령으로 나누어 관절별 최대 이동
속도를 제한한다. `write_positions()`가 SDK에 전달하는 `acceleration` 인자는 서보에
전달되는 장치 측 파라미터이며, 위의 ROS 2 제어 루프 보간과는 별개의 값이다.

---

## 5. 자세 유지와 Heartbeat

목표에 도달하면 Controller는 마지막 명령값을 유지한다. `heartbeat_hz`가 기본
10 Hz이므로 Controller가 정상적으로 실행되는 동안 같은 위치 명령을 주기적으로
다시 전송한다.

```text
목표 도달
  → 마지막 commanded 값 유지
  → Heartbeat 시각마다 write_positions(commanded)
  → 서보 내부 위치제어가 자세 유지
```

Heartbeat는 `/joint_targets`를 한 번만 발행하거나 요청 발행 노드가 종료되어도
Controller가 마지막 목표를 계속 사용하게 한다. 그러나 Controller의 비정상 종료,
Jetson 정지, 시리얼 단절 또는 전원 장애를 감지해 자동으로 토크를 해제하는 watchdog은
아니다.

---

## 6. 안전 기능

### 6.1 Soft Limit

`joints.yaml`의 `limit_rad`는 각 관절에 허용하는 소프트웨어 범위이다.

```text
◄──────────── 기계적 가동범위 ────────────►
      ◄────── Soft Limit 범위 ──────►
```

Controller는 다음 조건을 만족하지 않는 값을 거부한다.

```text
lower <= requested_position <= upper
```

Soft Limit은 기계적 스토퍼를 대신하지 않는다. 설정값과 실제 로봇의 영점이 잘못되어
있다면 안전을 보장할 수 없으므로 임의로 범위를 넓히지 않는다.

### 6.2 급출발 방지

토크 활성화 시 미리 정해 둔 자세로 이동시키지 않고 가장 최근의 측정 자세를 최초
목표로 사용한다. 이로써 토크가 켜지는 순간의 급격한 위치 변화를 방지한다.

### 6.3 명시적 토크 해제와 정상 종료 처리

- `/safety/torque_enable`에 `False`를 발행하면 Control Timer가 전체 토크를 해제한다.
- Controller는 시작할 때 이전 프로그램의 상태와 관계없이 먼저 토크를 해제한다.
- Controller를 `Ctrl+C`로 정상 종료하면 `finally`에서 토크를 다시 해제하고 시리얼
  연결을 닫는다.
- 강제 종료나 시스템 장애에서는 `finally` 실행을 보장할 수 없으므로 정상 종료와
  명시적 토크 해제 절차를 사용한다.

---

## 7. Plotter와 결과 해석

`joint_plotter`는 다음 두 Topic을 구독한다.

- 파란 실선 `current`: `/joint_states`에서 받은 실제 측정값
- 주황 점선 `requested`: `/joint_targets`에서 받은 원본 요청값

첫 요청이 들어오기 전에는 `requested` 선을 표시하지 않으며 CSV에는 `nan`으로
기록한다. 일부 관절만 요청하면 해당 관절의 요청값만 갱신한다.

주황 점선은 Controller가 Soft Limit 검사를 통과시킨 값이 아니다. 범위 밖 요청을
보내면 주황 점선은 해당 값으로 바뀔 수 있지만 Controller는 요청을 거부하므로 파란
현재값은 이를 추종하지 않는다. 이 차이가 Soft Limit 실습의 정상 결과이다.

Plotter를 종료하면 실행한 디렉터리의 `results/`에 다음 파일을 저장한다.

```text
joint_log_날짜_시간.csv
joint_plot_날짜_시간.png
```

CSV의 각 관절 열은 `*_current`와 `*_requested`로 구성한다.

---

## 8. 진단 및 종료 원칙

| 목적 | 명령 |
|---|---|
| 시리얼 장치 확인 | `ls -l /dev/ttyACM0` |
| 사용자 그룹 확인 | `groups` |
| 실행 파일 확인 | `ros2 pkg executables week05_joint_control` |
| 노드 확인 | `ros2 node list` |
| Controller 연결 확인 | `ros2 node info /joint_controller` |
| Topic 확인 | `ros2 topic list` |
| 현재 관절값 1회 확인 | `ros2 topic echo --once /joint_states` |
| Topic 타입 확인 | `ros2 topic type /joint_targets` |

- 제조사 Bringup이나 이전 실습 노드가 `/dev/ttyACM0`을 사용 중이면 먼저 정상
  종료한다.
- 실습 중 이상 동작이 발생하면 토크 해제 명령을 먼저 전송한다.
- Plotter를 먼저 `Ctrl+C`로 종료해 결과를 저장한 뒤 Controller를 정상 종료한다.
- 터미널을 강제로 닫거나 `killall -9 python3`을 일반 종료 방법으로 사용하지 않는다.
