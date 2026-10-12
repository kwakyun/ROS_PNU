# [6주차] 게임패드 기반 말단부 제어와 FK/IK — 수업 내용

## 0. 수업 개요

### 수업 목표

이번 수업을 마치면 다음 내용을 설명하고 수행할 수 있어야 한다.

- 작업 공간(Task Space)과 관절 공간(Joint Space)의 차이를 설명한다.
- 정운동학(Forward Kinematics, FK)과 역운동학(Inverse Kinematics, IK)의 입력과 출력을 구분한다.
- 게임패드 입력을 말단부(End-Effector, EEF)의 목표 위치와 Pitch로 변환한다.
- 목표 자세를 5개 로봇 암 관절값으로 변환하고 그리퍼 명령을 결합한다.
- 측정 관절값으로 현재 말단부 자세를 다시 계산하여 제어 결과를 확인한다.
- ROS 2 Launch 파일에서 여러 노드를 하나의 제어 파이프라인으로 구성한다.
- 입력 타임아웃, 작업 공간 제한, 관절 제한, 속도 제한, 토크 해제의 역할을 구분한다.

### 실습 완료 기준

다음 항목을 모두 확인하면 실습을 완료한 것으로 판단한다.

1. `joystick_to_pose.py`의 Publisher 2개와 Subscriber 1개를 완성한다.
2. `ik_solver.py`의 Subscriber 3개와 Publisher 1개를 완성한다.
3. Launch 파일에서 `joy_node`와 5개 실습 노드의 실행 항목을 완성한다.
4. 완성한 Launch로 6개 노드를 실행하고 전체 Topic 연결을 확인한다.
5. 게임패드로 EEF의 X, Y, Z, Pitch와 그리퍼를 제어한다.
6. `/ee_pose`에서 측정 관절값으로 계산한 현재 EEF 자세를 확인한다.
7. 입력 단절 시 새 목표 발행이 멈추고 마지막 명령 자세를 유지하는 흐름을 확인한다.
8. 실습 종료 전에 명시적으로 토크를 해제한다.

---

## 1. 전체 제어 구조

6주차 실습은 게임패드 입력을 작업 공간 목표로 바꾸고, IK로 관절 목표를 계산한 뒤
실제 모터를 구동한다. 동시에 측정 관절값으로 FK를 수행하여 현재 EEF 자세를 확인한다.

```text
USB Gamepad
    │
    ▼ /joy
joystick_to_pose
    ├── /target_pose ──> ik_solver
    └── /gripper_open ─> ik_solver
                           │
                           ▼ /joint_targets
                       arm_driver ──> Feetech Servo
                           │
                           ▼ /joint_states
                       fk_solver
                           │
                           ▼ /ee_pose
                    ee_pose_listener
```

Topic의 의미는 다음과 같다.

| Topic | 메시지 타입 | 의미 |
|---|---|---|
| `/joy` | `sensor_msgs/msg/Joy` | 게임패드의 축과 버튼 상태 |
| `/target_pose` | `geometry_msgs/msg/PoseStamped` | `base_link` 기준 EEF 목표 위치와 자세 |
| `/gripper_open` | `std_msgs/msg/Bool` | 그리퍼 열림·닫힘 상태 |
| `/joint_targets` | `sensor_msgs/msg/JointState` | arm joint 5개와 gripper의 목표값 |
| `/joint_states` | `sensor_msgs/msg/JointState` | 서보에서 읽은 6개 관절의 현재값 |
| `/ee_pose` | `geometry_msgs/msg/PoseStamped` | 측정 관절값으로 계산한 현재 EEF 자세 |
| `/safety/torque_enable` | `std_msgs/msg/Bool` | 모터 토크 활성화 또는 해제 요청 |

### 1.1 주요 파일의 역할

| 파일 | 역할 | 실습 범위 |
|---|---|---|
| `joystick_to_pose.py` | `/joy`를 EEF 목표 자세와 그리퍼 상태로 변환한다. | Publisher 2개, Subscriber 1개 |
| `ik_solver.py` | EEF 목표를 관절 목표로 변환한다. | Subscriber 3개, Publisher 1개 |
| `arm_driver.py` | 관절 상태를 읽고 검증된 목표를 실제 서보에 전달한다. | 제공 코드 사용 |
| `fk_solver.py` | 측정 관절값으로 현재 EEF 자세를 계산한다. | 제공 코드 사용 |
| `ee_pose_listener.py` | 현재 EEF 자세를 읽기 쉬운 로그로 출력한다. | 제공 코드 사용 |
| `kinematics.py` | 로봇의 링크 변환과 FK 계산 함수를 제공한다. | 제공 코드 사용 |
| `hardware_interface.py` | Feetech SDK 연결과 radian-tick 변환을 담당한다. | 제공 코드 사용 |
| `joystick_arm_control.launch.py` | `joy_node`와 5개 실습 노드를 함께 실행한다. | 6개 Node의 `package`, `executable`과 게임패드 설정 연결 |

### 1.2 5주차 Joint Controller와의 연결

5주차에는 사용자가 `/joint_targets`에 관절각을 직접 보내고
`joint_controller`가 모터를 제어했다.

```text
5주차
사용자 관절 목표 ── /joint_targets ──> joint_controller ──> Servo
                                         │
                                         └── /joint_states
```

6주차에는 게임패드와 IK가 상위 제어 계층으로 추가된다. 5주차
`joint_controller`가 담당하던 하위 관절 제어 역할은 `arm_driver`가 이어받는다.

```text
6주차
Gamepad ──> EEF 목표 ──> IK ── /joint_targets ──> arm_driver ──> Servo
                                                    │
                                                    └── /joint_states
```

따라서 `arm_driver`는 완전히 새로운 종류의 노드가 아니라, 연속적인 IK 목표를 받도록
5주차 Controller를 변경한 하드웨어 제어 노드이다. `arm_driver`는 EEF 자세나 IK를
직접 계산하지 않고, 계산이 끝난 관절 목표를 검사하고 실제 모터에 전달한다.

두 노드가 공통으로 수행하는 기능은 다음과 같다.

- Feetech 서보에서 현재 관절값을 읽어 `/joint_states`로 발행한다.
- `/joint_targets`의 관절 이름과 Soft Limit을 검사한다.
- 관절별 최대 속도에 따라 명령을 보간한다.
- `/safety/torque_enable`로 토크 요청을 처리한다.
- 토크를 켤 때 현재 자세를 첫 유지 목표로 사용한다.
- 마지막 명령을 Heartbeat 주기로 다시 전송한다.
- 시작과 정상 종료 과정에서 토크 해제를 시도한다.

주요 변경점은 다음과 같다.

| 항목 | 5주차 `joint_controller` | 6주차 `arm_driver` |
|---|---|---|
| 목표 생성 주체 | 사용자가 명령어로 직접 발행한다. | `ik_solver`가 연속 발행한다. |
| 목표 구성 | 일부 관절만 포함할 수 있다. | arm joint 5개와 gripper가 모두 필요하다. |
| 목표 유지 | 한 번 받은 목표를 계속 추종한다. | 300 ms 동안 목표가 없으면 진행 중 이동을 멈춘다. |
| 상태 발행·제어 주기 | 20 Hz·30 Hz | 50 Hz·100 Hz |
| 최대 관절 속도 | 0.35~0.60 rad/s | 1.0~2.0 rad/s |

같은 `/joint_targets` Topic을 사용하지만 메시지 운용 방식이 다르다는 점에 주의한다.
5주차처럼 관절 하나만 포함한 목표를 6주차 `arm_driver`에 보내면 불완전한 목표로
거부된다. 반대로 6주차 IK는 항상 6개 관절의 완전한 목표를 만들어 보낸다.

### 1.3 Launch 파일의 역할

각 Python 파일을 따로 실행해도 제어할 수 있지만, 전체 파이프라인에는 6개 노드가
필요하다. Launch 파일은 여러 `ros2 run` 명령을 하나로 묶어 동일한 설정으로 실행한다.

```text
LaunchDescription
  ├─ joy/joy_node
  ├─ week06_ee_control/joystick_to_pose
  ├─ week06_ee_control/arm_driver
  ├─ week06_ee_control/ik_solver
  ├─ week06_ee_control/fk_solver
  └─ week06_ee_control/ee_pose_listener
```

Launch의 `Node`는 ROS 2 노드 자체의 구현이 아니라 어떤 패키지의 어떤 실행 파일을
어떤 이름과 설정으로 시작할지를 나타내는 실행 항목이다.

```python
Node(
    package="패키지 이름",
    executable="setup.py에 등록한 실행 파일 이름",
    name="실행할 노드 이름",
    output="screen",
)
```

이번 실습에서는 두 Launch 인자가 미리 제공된다.

- `device_id`: `joy_node`가 사용할 SDL 게임패드 번호를 지정한다.
- `start_joy`: `false`이면 Launch가 `joy_node`를 실행하지 않는다.

각 Node의 `name`, `output`과 전체 구조는 제공된다. 학생은 6개 Node의 `package`와
`executable`을 작성하고, `joy_node`에는 `start_joy`와 `device_id` LaunchConfiguration을
연결한다. Launch 파일은 Topic을 직접 연결하지 않는다. 각 노드가 동일한 Topic 이름으로
Publisher와 Subscriber를 만들면 ROS 2가 연결하며, Launch는 필요한 프로세스를 함께
시작하는 역할을 한다.

---

## 2. 작업 공간과 관절 공간

### 2.1 작업 공간

작업 공간은 로봇의 손끝을 기준으로 명령하는 공간이다. 이번 실습에서는 다음 네 값을
목표로 사용한다.

```text
target pose = (X, Y, Z, Pitch)
```

- X, Y, Z는 `base_link` 기준 위치이며 단위는 m이다.
- Pitch는 손끝이 위아래로 기울어진 각도이며 단위는 radian이다.
- `wrist_roll`은 작업 공간 목표에 포함하지 않고 현재 관절값을 유지한다.
- 그리퍼는 IK 대상이 아니라 별도의 열림·닫힘 목표로 다룬다.

### 2.2 관절 공간

관절 공간은 각 모터의 회전각으로 로봇 자세를 표현한다. IK/FK에 사용하는 arm joint는
다음 5개이며, 실제 `/joint_targets`와 `/joint_states`에는 `gripper`를 추가하여 총 6개
관절값을 사용한다.

```text
shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll
```

작업 공간 명령은 사람이 손끝의 이동을 생각하기 쉽지만, 모터는 관절 공간 명령을
필요로 한다. 두 공간 사이를 FK와 IK가 연결한다.

---

## 3. 정운동학

정운동학(Forward Kinematics, FK)은 각 관절이 현재 얼마나 회전했는지를 보고
로봇 손끝이 어디에 있는지 계산하는 과정이다.

```text
현재 관절각 5개 ── FK ──> 현재 손끝의 위치와 방향
```

예를 들어 어깨와 팔꿈치가 움직이면 손목과 그리퍼의 위치도 함께 달라진다.

```text
어깨가 회전한다.
  └─ 팔꿈치의 시작 위치가 바뀐다.
      └─ 팔꿈치가 회전한다.
          └─ 손목과 그리퍼의 최종 위치가 바뀐다.
```

FK는 이 연결 관계를 로봇 베이스부터 그리퍼까지 순서대로 계산한다.
`kinematics.py`에는 각 링크의 길이와 연결 방향이 저장되어 있고,
`forward_matrix()`는 다음 과정을 수행한다.

```text
베이스 위치에서 시작
  → shoulder_pan 회전 반영
  → shoulder_lift 회전 반영
  → elbow_flex 회전 반영
  → wrist_flex 회전 반영
  → wrist_roll 회전 반영
  → 그리퍼의 최종 위치와 방향 계산
```

코드에서는 위치와 회전을 한꺼번에 계산하기 위해 4×4 행렬을 사용한다. 학생이 이
행렬을 직접 계산할 필요는 없다. 계산 결과에서 다음 정보만 꺼내 사용한다.

- X, Y, Z: 손끝의 현재 위치
- Quaternion: 손끝이 향하고 있는 현재 방향을 ROS 2 메시지로 표현한 값

예를 들어 현재 관절값이 다음과 같다고 가정한다.

```text
shoulder_pan  =  0.00 rad
shoulder_lift = -0.80 rad
elbow_flex    =  0.60 rad
wrist_flex    =  1.20 rad
wrist_roll    =  0.00 rad
```

`fk_solver.py`는 이 값을 `/joint_states`에서 읽고 다음 결과를 `/ee_pose`로 발행한다.

```text
현재 EEF 위치 = (X, Y, Z)
현재 EEF 방향 = Quaternion
```

따라서 `/ee_pose`는 명령으로 보낸 목표 자세가 아니라, 실제 서보에서 읽은 관절값을
바탕으로 계산한 현재 자세이다. 목표와 실제 자세가 얼마나 비슷한지 확인할 때 이 값을
사용한다.

---

## 4. 역운동학

역운동학은 목표 EEF 자세를 만들 수 있는 관절각을 계산한다.

```text
X, Y, Z, Pitch ── IK ──> q1, q2, q3, q4, q5
```

같은 EEF 자세를 만드는 관절 조합이 여러 개일 수 있고, 로봇이 도달할 수 없는 목표에는
해가 존재하지 않을 수 있다. 이번 솔버는 다음 순서로 하나의 해를 찾는다.

1. 목표 X-Y 방향으로 `shoulder_pan`을 계산한다.
2. 직전 IK 해가 있으면 이를 초기값으로 사용하고, 없으면 측정 관절값을 사용한다.
3. `shoulder_lift`와 `elbow_flex`를 조금씩 변화시켜 3×2 Jacobian을 수치적으로 근사한다.
4. Damped Least Squares 방식으로 위치 오차가 줄어드는 방향을 계산한다.
5. 한 번의 보정량을 제한하고 관절 범위 안에서 총 8회 반복한다.
6. `wrist_flex = target_pitch - shoulder - elbow` 관계로 Pitch를 맞춘다.
7. 위치 오차가 0.020 m보다 크면 해당 목표를 거부한다.

---

## 5. 게임패드 입력과 목표 자세 생성

`joystick_to_pose.py`는 `/joy`의 최신 축과 버튼 상태를 저장하고 25 Hz Timer에서 목표
자세를 갱신한다.

| 입력 | 목표 변화 |
|---|---|
| 왼쪽 스틱 상하 `axes[1]` | X 증가·감소 |
| 왼쪽 스틱 좌우 `axes[0]` | Y 증가·감소 |
| 방향 입력 `axes[7]` | Z 증가·감소 |
| 오른쪽 스틱 좌우 `axes[3]` | Pitch 증가·감소 |
| A 버튼 `buttons[0]` | 그리퍼 열림·닫힘 토글 |

각 축 입력은 속도와 Timer 주기 `dt`를 곱하여 현재 목표에 누적한다.

\[
x_{next} = x_{current} + v_x \times axis_x \times dt
\]

작은 입력은 Deadzone으로 0 처리한다. X, Y, Z, Pitch 각각의 범위와 베이스에서의 XY
반지름도 제한한다. 이 제한은 지나치게 큰 요청을 줄이지만, 제한 안의 모든 목표가 IK로
도달 가능하다는 뜻은 아니다. 최종 도달 가능 여부는 IK 위치 오차 검사로 판단한다.

A 버튼은 누르고 있는 동안 반복해서 상태가 바뀌지 않도록 0에서 1로 변하는 순간에만
그리퍼 상태를 토글한다.

---

## 6. Callback과 Timer의 실행 흐름

ROS 2 Callback은 새 메시지가 도착했을 때 실행되고, Timer Callback은 정해진 주기에
실행된다. 두 노드는 수신과 계산을 분리한다.

```text
/joy 도착
  └─ _on_joy(): 최신 axes/buttons 저장, 버튼 edge 검사
       └─ 25 Hz _tick(): 목표 누적 및 /target_pose, /gripper_open 발행

/joint_states, /target_pose, /gripper_open 도착
  └─ 각 Callback: 측정값·목표값·그리퍼 상태 저장
       └─ 60 Hz _tick(): 새 목표의 IK 계산 및 /joint_targets 발행
```

학생이 작성하는 부분은 이 흐름에 필요한 Publisher와 Subscriber 생성 코드이다.
메시지 타입, Topic 이름, Callback, QoS queue depth를 올바른 순서로 연결해야 한다.

---

## 7. 제어와 안전 동작

### 7.1 세 단계 입력 타임아웃

이번 코드에는 서로 다른 역할의 타임아웃이 있다.

| 위치 | 기준 시간 | 동작 |
|---|---:|---|
| `joystick_to_pose` | 0.50초 | `/joy`가 끊기면 새 목표 자세 발행을 중단한다. |
| `ik_solver` | 0.25초 | 오래된 `/target_pose`로 관절 목표를 발행하지 않는다. |
| `arm_driver` | 300 ms | `/joint_targets`가 끊기면 진행 중 이동을 멈추고 마지막 명령 자세를 유지한다. |

스틱을 중립에 놓는 것은 연결 단절과 다르다. `joy_node`가 중립값을 계속 발행하면 목표
자세도 같은 값으로 계속 발행한다. 타임아웃은 USB 분리나 노드 중단처럼 새 `/joy`
메시지가 들어오지 않을 때 동작한다.

### 7.2 관절 제한과 속도 제한

`arm_driver`는 6개 관절 목표가 모두 포함되었는지 확인하고, 각 값이 `joints.yaml`의
`limit_rad` 안에 있는지 검사한다. 하나라도 범위를 벗어나거나 유한하지 않으면 전체
목표를 거부한다.

허용된 목표는 한 제어 주기마다 다음 값 이하로 이동한다.

\[
max\_step = max\_vel\_rad\_s \times dt
\]

### 7.3 토크 활성화와 자세 유지

토크를 활성화할 때 현재 측정 자세를 첫 명령으로 기록한다.
이후 목표가 끊기면 마지막으로 보낸 관절 명령을 유지하고, 10 Hz Heartbeat로
같은 명령을 주기적으로 다시 전송한다.

Heartbeat는 Controller가 정상 실행되고 시리얼 통신이 가능한 동안 마지막 명령을
재전송하는 기능이다. 프로세스 비정상 종료, 케이블 단절, 전원 장애까지 감시하는
독립적인 watchdog은 아니다.

### 7.4 명시적 토크 해제와 정상 종료

`false`를 `/safety/torque_enable`에 발행하면 모든 서보의 토크를 해제한다.
`arm_driver`는 정상 종료 과정에서도 토크 해제를 시도하지만, 프로그램이 강제로
종료되거나 통신이 이미 끊긴 경우 성공을 보장할 수 없다. 따라서 실습 종료 순서는
토크 해제 확인 후 Launch 종료로 한다.

---

## 8. 결과 해석과 진단 원칙

- `/target_pose`는 조이스틱에서 생성한 목표 EEF 자세이다.
- `/joint_targets`는 IK가 계산한 관절 목표이다.
- `/joint_states`는 실제 서보에서 읽은 관절 상태이다.
- `/ee_pose`는 측정 관절 상태에 FK를 적용한 현재 EEF 자세이다.

문제가 생기면 결과만 보지 말고 Topic을 입력부터 차례로 확인한다.

```text
/joy
  └─ /target_pose, /gripper_open
       └─ /joint_targets
            └─ /joint_states
                 └─ /ee_pose
```

중간 Topic이 처음 끊기는 지점이 원인에 가장 가깝다. 예상하지 못한 움직임이 발생하면
먼저 토크를 해제한 뒤 Topic, 축 번호, 단위, 관절 이름과 제한값을 확인한다.
