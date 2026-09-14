# [3주차] ROS2 basic 2 — 수업 내용

## 0. 수업 개요

### 수업 목표

이번 수업을 마치면 다음 내용을 설명하고 수행할 수 있어야 한다.

- 2주차에서 배운 Node와 Topic 통신 구조를 실제 로봇 관절값에 적용한다.
- Topic과 Service의 용도 및 동작 차이를 설명한다.
- Service Server와 Client가 요청과 응답을 주고받는 과정을 설명한다.
- `std_srvs/srv/Trigger` 인터페이스를 이용해 최신 관절 상태를 한 번 요청한다.
- Launch 파일로 여러 노드를 함께 실행한다.

### 수업 내용

1. Node, Publisher, Subscriber, Topic 간단 복습
2. `sensor_msgs/msg/JointState`를 이용한 실제 관절 상태 전달
3. Service Server와 Service Client
4. `.msg`, `.srv`, `std_srvs/srv/Trigger` 인터페이스
5. Launch 파일과 `setup.py`의 데이터 파일 등록

---

## 1. Topic 통신 복습

2주차에서 하나의 노드는 메시지를 발행하고 다른 노드는 같은 Topic을 구독했다.
3주차에서는 문자열 대신 실제 로봇의 관절 상태를 전달한다.

```text
joint_state_publisher
        │
        │ /joint_states
        ▼
joint_state_listener
```

- `joint_state_publisher`는 서보 모터에서 관절값을 반복해서 읽는다.
- 읽은 값은 `sensor_msgs/msg/JointState` 메시지로 만들어 `/joint_states`에 발행한다.
- `joint_state_listener`는 메시지가 도착할 때마다 콜백을 실행한다.
- Publisher는 특정 Subscriber가 있는지 확인하지 않고 계속 발행한다.

`JointState`에서 이번 실습이 사용하는 주요 필드는 다음과 같다.

| 필드 | 의미 | 예시 |
|---|---|---|
| `name` | 관절 이름 배열 | `shoulder_pan`, `elbow_flex` |
| `position` | 이름 순서에 대응하는 관절 각도 배열 | radian 단위의 실수값 |
| `header.stamp` | 메시지를 생성한 ROS 시간 | 발행 시각 |

`name[0]`의 관절 위치는 `position[0]`, `name[1]`의 관절 위치는
`position[1]`과 대응한다. 따라서 두 배열의 길이와 순서가 일치해야 한다.

### 1.1 `JointState`는 어디에서 오는가

Publisher 파일의 다음 코드는 `JointState`라는 클래스를 현재 패키지에서 정의하는
것이 아니라 ROS 2 표준 패키지인 `sensor_msgs`에서 가져온다.

```python
from sensor_msgs.msg import JointState
```

ROS 2에는 로봇 관절 상태를 전달하기 위한 `sensor_msgs/msg/JointState` 인터페이스가
미리 정의되어 있다. 원본 `.msg` 규격은 다음 필드를 가진다.

```text
std_msgs/Header header
string[] name
float64[] position
float64[] velocity
float64[] effort
```

ROS 2 빌드 시스템은 이 `.msg` 정의를 Python에서 사용할 수 있는 `JointState`
클래스로 생성한다. 따라서 `JointState`는 관절을 직접 측정하는 기능이 아니라,
측정한 관절 상태를 정해진 형식으로 담는 데이터 객체이다.

설치된 인터페이스의 실제 필드는 다음 명령으로 확인할 수 있다.

```bash
ros2 interface show sensor_msgs/msg/JointState
```

`JointState()`로 새 객체를 만들면 배열에는 아직 값이 없다.

```python
message = JointState()

# 처음에는 다음 배열이 비어 있음
message.name       # []
message.position   # []
message.velocity   # []
message.effort     # []
```

### 1.2 Publisher가 실제 관절값을 발행하는 과정

`joint_state_publisher.py`의 데이터 흐름은 다음과 같다.

```text
joints.yaml
  └─ 관절 이름, 서보 ID, 영점, 부호, 통신 설정
                         │
                         ▼
FeetechReader.read_positions()
  └─ 서보 tick 읽기 → radian으로 변환 → positions 배열 반환
                         │
                         ▼
JointState 객체 생성
  ├─ header.stamp = 현재 ROS 시간
  ├─ name = joints.yaml의 관절 이름 배열
  └─ position = 하드웨어에서 읽은 관절 각도 배열
                         │
                         ▼
Publisher.publish(message)
                         │
                         ▼
                /joint_states Topic
```

Timer는 `joints.yaml`의 `publish_hz`에 맞춰 `_publish_state()`를 반복 호출한다.
콜백 안에서는 다음 순서로 메시지를 만든다.

```python
positions = self._reader.read_positions()

message = JointState()
message.header.stamp = self.get_clock().now().to_msg()
message.name = list(self._config.joint_names)
message.position = list(positions)

self._publisher.publish(message)
```

- `positions`: 실제 서보에서 읽고 radian으로 변환한 6개 값
- `header.stamp`: 이 메시지를 만든 시각
- `name`: 각 값이 어느 관절에 해당하는지 나타내는 이름
- `position`: `name`과 같은 순서로 정렬된 실제 관절 각도

이번 코드에서는 관절 속도와 토크를 측정하지 않으므로 `velocity`와 `effort`는 빈
배열로 둔다. `JointState` 규격에서는 사용하지 않는 배열을 비워 둘 수 있다.

`publish()`가 호출되면 메시지가 `/joint_states` Topic으로 전달된다. Publisher는
Listener나 Service Server를 직접 호출하지 않는다. 같은 Topic을 구독하고 있는
노드들이 ROS 2 통신 계층을 통해 각자 메시지를 받는다.

---

## 2. Topic과 Service의 차이

Topic은 상태가 계속 변하는 데이터를 전달하는 데 적합하다. 반면 Service는
Client가 요청했을 때 Server가 결과를 한 번 반환하는 통신 방식이다.

| 구분 | Topic | Service |
|---|---|---|
| 통신 흐름 | Publisher가 계속 발행 | Client 요청 1회 → Server 응답 1회 |
| 데이터를 받는 쪽 | Subscriber | Service Client |
| 실행 시점 | 메시지가 발행될 때마다 | Client가 호출할 때만 |
| 이번 실습 | `/joint_states` | `/get_joint_state` |
| 적합한 예 | 센서값, 관절 상태 스트리밍 | 현재 상태 조회, 설정 요청 |

이번 실습의 전체 구조는 다음과 같다.

```text
PhysicAI Arm
     │
     │ 모터 위치 읽기
     ▼
joint_state_publisher
     │
     │ /joint_states Topic
     ├──────────────────────> joint_state_listener
     │
     └──────────────────────> joint_state_service_server
                                      │
                                      │ 최신 JointState 저장
                                      │
joint_state_service_client ───────────┘
                    /get_joint_state 요청·응답
```

여기서 Service Server는 모터나 `/dev/ttyACM0`을 직접 열지 않는다.
`/joint_states`를 구독하여 가장 최근에 받은 메시지를 저장하고, Service 요청이
들어오면 저장된 값을 응답한다. 따라서 시리얼 장치는 Publisher 한 개만 관리한다.

---

## 3. ROS 2 인터페이스: `.msg`와 `.srv`

ROS 2 노드끼리 통신하려면 송신 측과 수신 측이 데이터의 구조를 미리 알고 있어야
한다. 이 데이터 구조에 대한 약속을 ROS 2에서는 인터페이스라고 한다.

### 3.1 `.msg`: 한 방향으로 전달할 메시지 형식

`.msg` 파일은 Topic으로 전달할 한 개 메시지의 필드와 타입을 정의한다.

```text
string[] name
float64[] position
```

이는 `name`이라는 문자열 배열과 `position`이라는 실수 배열을 가진 메시지라는
뜻이다. Publisher와 Subscriber는 같은 `.msg` 규격을 사용해야 한다.

### 3.2 `.srv`: 요청과 응답을 함께 정의하는 형식

Service에는 Client가 Server로 보내는 요청과 Server가 Client로 돌려주는 응답이
모두 필요하다. `.srv` 파일은 이 두 데이터 구조를 한 파일에 정의한다.

```text
string item_name       # Client가 Server에 보내는 Request
---
bool success           # Server가 Client에 돌려주는 Response
string message
```

대시 세 개(`---`)는 데이터를 전송한다는 명령이 아니라, 인터페이스 파일에서
Request와 Response의 경계를 표시하는 구분선이다.

```text
--- 위쪽: Client가 채워서 보내는 값
--- 구분선
--- 아래쪽: Server가 처리 후 채워서 돌려주는 값
```

예를 들어 Client가 `item_name`에 조회할 항목을 넣어 요청하면, Server는 요청을
처리한 뒤 `success`와 `message`를 채워 응답한다. Topic 메시지와 달리 하나의
Service 호출 안에는 요청과 그 요청에 대응하는 응답이 한 쌍으로 존재한다.

### 3.3 이번 실습의 `std_srvs/srv/Trigger`

이번 실습에서는 새로운 `.srv` 파일을 직접 만들지 않고 ROS 2가 제공하는 표준
인터페이스 `std_srvs/srv/Trigger`를 사용한다.

```text
---
bool success
string message
```

`---` 위에 필드가 없으므로 Client가 요청과 함께 전달할 데이터는 없다. 호출 자체가
“지금 작업을 수행해 달라” 또는 “현재 결과를 알려 달라”는 신호가 된다.

Server는 응답에 다음 값을 채운다.

- `success`: 요청을 정상적으로 처리했는지 나타내는 `True` 또는 `False`
- `message`: 처리 결과 또는 오류 원인을 담는 문자열

이번 실습에서는 요청이 들어오면 최신 6개 관절값을 `message`에 넣는다. 아직
`/joint_states`를 한 번도 받지 못했다면 `success=False`와 오류 이유를 반환한다.

`Trigger`는 이미 `std_srvs` 패키지에 정의되어 있으므로 이번 패키지에 별도의
`.srv` 파일이나 인터페이스 생성용 `CMakeLists.txt`를 만들 필요가 없다.

---

## 4. Service Server의 동작

Service Server 노드는 Subscriber와 Service Server 역할을 동시에 수행한다.

```text
1. /joint_states 메시지 수신
2. Subscriber 콜백에서 최신 메시지 저장
3. /get_joint_state 요청 대기
4. 요청이 들어오면 저장된 메시지 확인
5. success와 message를 작성하여 응답
```

두 종류의 콜백이 사용된다.

- Topic 콜백: 새 `JointState`가 도착할 때 실행되어 최신값을 갱신한다.
- Service 콜백: Client 요청이 도착할 때 실행되어 Response를 작성한다.

Service Server가 실행 중이라는 사실만으로 관절값이 준비되는 것은 아니다.
Publisher가 `/joint_states`를 실제로 발행하고 Server가 최소 한 번 이상 수신해야
정상 응답을 만들 수 있다.

---

## 5. Service Client와 비동기 호출

Service Client는 특정 Service를 찾아 Request를 보내고 Response를 받는 노드이다.
이번 Python Client는 다음 순서로 한 번 호출하고 종료한다.

```text
Service Client 생성
        ↓
/get_joint_state Server가 나타날 때까지 대기
        ↓
비어 있는 Trigger Request 전송
        ↓
Response가 도착할 때까지 ROS 이벤트 처리
        ↓
success와 message 확인 후 종료
```

### 5.1 Client도 ROS 2 Node로 만드는 이유

Service를 검색하고 네트워크로 Request와 Response를 주고받으려면 ROS graph에
참여하는 Node가 필요하다. 따라서 `JointStateServiceClient`도 `Node`를 상속한다.

```python
class JointStateServiceClient(Node):
    def __init__(self):
        super().__init__("joint_state_service_client")
```

`super().__init__(...)`은 부모인 `rclpy.node.Node`를 초기화하고 ROS graph에서 사용할
노드 이름을 지정한다. 이 초기화가 끝나야 `create_client()`, `get_logger()` 같은
Node 메서드를 사용할 수 있다.

### 5.2 `create_service()`: Service 제공 창구 생성

`create_service()`는 `rclpy.node.Node`가 제공하는 메서드이다.

```text
Node.create_service(ServiceType, service_name, callback)
```

| 인자 | 의미 |
|---|---|
| `ServiceType` | Request와 Response 구조를 정의하는 Service 인터페이스 |
| `service_name` | 생성할 Service의 ROS graph 이름 |
| `callback` | 요청을 받았을 때 실행할 함수 |
| 반환값 | 요청을 받아 처리하는 `Service` 객체 |

Service 타입과 이름은 Client 쪽과 모두 일치해야 한다. 예를 들어 Server가
`Trigger` 타입으로 `/get_joint_state`를 열었다면 Client도 같은 타입과 이름을
사용해야 한다.

`callback`은 Client가 보낸 Request와 응답 작성에 사용할 Response를 전달받는다.
필요한 작업을 수행한 뒤 값을 채운 Response를 반환한다.

```python
def service_callback(self, request, response):
    response.success = True
    response.message = 'Service request processed'
    return response
```

반환된 Service 객체는 Service가 유지되도록 인스턴스 변수에 보관한다.

```text
self._service
     │
     └─ Client 요청 수신
          │
          └─ callback(request, response)
                 │
                 └─ Response 반환
```

이름 앞의 `_`는 “이 클래스 내부에서 사용하는 값”이라는 Python 명명 관례이며
ROS 2의 특별한 문법은 아니다.

### 5.3 `create_client()`: Service 호출 창구 생성

`create_client()`는 `rclpy.node.Node`가 제공하는 메서드이다.

```text
Node.create_client(ServiceType, service_name)
```

| 인자 | 의미 |
|---|---|
| `ServiceType` | Request와 Response 구조를 정의하는 Service 인터페이스 |
| `service_name` | 연결할 Service의 ROS graph 이름 |
| 반환값 | 요청을 보내는 `Client` 객체 |

Service 타입과 이름은 Server 쪽과 모두 일치해야 한다. 예를 들어 Server가
`Trigger` 타입으로 `/get_joint_state`를 열었다면 Client도 같은 타입과 이름을
사용해야 한다.

반환된 Client 객체는 이후 Server 탐색과 요청 전송에 계속 사용되므로 인스턴스
변수에 보관한다.

```text
self._client
     │
     ├─ wait_for_service()
     └─ call_async()
```

이름 앞의 `_`는 “이 클래스 내부에서 사용하는 값”이라는 Python 명명 관례이며
ROS 2의 특별한 문법은 아니다.

### 5.4 `wait_for_service()`: Server 발견 대기

Client 객체를 생성했다고 해서 Server가 이미 실행 중이라는 뜻은 아니다.
`wait_for_service()`는 같은 이름과 타입을 가진 Server가 ROS graph에서 발견될
때까지 기다린다.

```text
Client.wait_for_service(timeout_sec=대기할_초)
```

- 제한 시간 안에 Server를 발견하면 `True`
- 제한 시간이 지나도 발견하지 못하면 `False`

이번 코드에서는 반환값이 `False`일 때 `RuntimeError`를 발생시켜, 요청을 보내지
못한 이유를 명확히 표시한다. 이 검사가 없으면 Server가 없는 상태에서 요청을
보낸 뒤 결과를 계속 기다리는 상황을 이해하기 어려울 수 있다.

### 5.5 `Trigger.Request()`: 빈 요청 객체 생성

ROS 2 인터페이스를 Python에서 사용하면 Request와 Response 클래스도 함께
제공된다.

```text
Trigger.Request()   # Client가 보내는 요청 객체
Trigger.Response()  # Server가 작성하는 응답 객체
```

`Trigger`는 `---` 위쪽에 필드가 없기 때문에 `Trigger.Request()`를 생성한 뒤 따로
입력할 값이 없다. 빈 객체이지만 “요청이 한 번 발생했다”는 사실을 Server에
전달한다.

### 5.6 `call_async()`: 비동기 요청 전송

`call_async()`는 `create_client()`가 반환한 Client 객체의 메서드이다.

```text
Client.call_async(request) → Future
```

비동기 호출은 메서드가 Response를 받을 때까지 그 자리에서 멈추는 방식이 아니다.
Request를 전송한 뒤, 미래에 결과가 들어올 자리인 `Future` 객체를 즉시 반환한다.

```text
Request 전송 직후
Future: 아직 완료되지 않음

Server 응답 도착 후
Future: Response 또는 오류를 보관
```

따라서 `future`는 응답 그 자체가 아니라 “나중에 응답을 확인하기 위한 객체”이다.

### 5.7 `spin_until_future_complete()`: 응답이 올 때까지 ROS 이벤트 처리

Request를 보낸 후에는 네트워크에서 도착하는 Response를 ROS 2가 처리해야 한다.

```text
rclpy.spin_until_future_complete(node, future)
```

이 함수는 지정한 `future`가 완료될 때까지 해당 Node의 ROS 이벤트를 처리한다.
일반적인 `rclpy.spin(node)`은 종료 요청 전까지 계속 실행되지만,
`spin_until_future_complete()`는 한 번 보낸 요청의 Future가 완료되면 반환한다.
따라서 요청 한 번만 보내고 끝나는 이번 Client에 적합하다.

### 5.8 `future.result()`와 `future.exception()`

Future가 완료된 다음 결과를 확인한다.

| 메서드 | 역할 |
|---|---|
| `future.result()` | 정상적으로 도착한 Response 객체 확인 |
| `future.exception()` | 요청 처리 중 발생한 예외 확인 |

정상적인 `Trigger.Response`에는 다음 두 필드가 있다.

```text
response.success   # Server의 요청 처리 성공 여부
response.message   # 관절값 또는 오류 설명
```

Response가 도착했다는 것과 Server의 작업이 성공했다는 것은 서로 다르다. 예를 들어
Service 통신 자체는 성공했어도 Server가 아직 `/joint_states`를 받지 못했다면
Response는 도착하지만 `response.success`는 `False`가 된다.

```text
future.result()가 있음
        │
        ├─ response.success == True
        │      └─ 최신 관절값 사용
        │
        └─ response.success == False
               └─ response.message로 실패 이유 확인
```

### 5.9 `request_once()`의 반환값과 `main()`의 종료 과정

`request_once()`는 Service 요청이 정상 처리되면 `True`, 실패하면 `False`를
반환한다. `main()`은 이 값을 프로세스 종료 코드로 바꾼다.

```text
request_once() == True  → exit code 0: 정상 종료
request_once() == False → exit code 1: 오류 종료
```

Client 실행 전후의 ROS 2 생명주기는 다음과 같다.

| 코드 | 역할 |
|---|---|
| `rclpy.init()` | 현재 프로세스에서 ROS 2 사용 시작 |
| `JointStateServiceClient()` | Client Node 생성 및 Server 확인 |
| `request_once()` | Request 전송 및 Response 처리 |
| `destroy_node()` | 생성한 Node 자원 정리 |
| `rclpy.shutdown()` | 현재 프로세스의 ROS 2 사용 종료 |

`finally`에서 정리 함수를 호출하면 정상 응답, 오류, `Ctrl+C` 중 어느 경로로
종료되더라도 생성한 ROS 2 자원을 정리할 수 있다.

### 5.10 Client 메서드 사용 순서

완성 코드의 값을 직접 제시하지 않은 일반적인 Service Client 패턴은 다음과 같다.

```text
Node.create_client(ServiceType, service_name)
        ↓ Client
Client.wait_for_service(timeout_sec=...)
        ↓
ServiceType.Request()
        ↓ Request
Client.call_async(request)
        ↓ Future
rclpy.spin_until_future_complete(node, future)
        ↓
future.result()
        ↓ Response
response.success / response.message 확인
```

Python Client가 반드시 있어야만 Service를 사용할 수 있는 것은 아니다. 터미널의
`ros2 service call` 명령으로도 같은 Service를 호출할 수 있다. 하지만 다른 ROS 2
노드가 판단 결과에 따라 자동으로 Service를 호출하거나, 응답을 다음 코드에
사용하려면 프로그램 형태의 Client가 필요하다.

---

## 6. Launch 파일

노드를 각각 `ros2 run`으로 실행하면 노드 수만큼 터미널을 관리해야 한다. Launch
파일은 함께 사용해야 하는 여러 노드와 설정을 하나의 실행 구성으로 묶는다.

Launch 파일의 주요 요소는 다음과 같다.

| 요소 | 역할 |
|---|---|
| `generate_launch_description()` | `ros2 launch`가 호출하는 진입 함수 |
| `LaunchDescription` | 함께 실행할 동작의 목록 |
| `Node` | 실행할 ROS 2 패키지와 실행 파일에 대한 정의 |
| `package` | 실행 파일을 제공하는 패키지 이름 |
| `executable` | `setup.py`에 등록된 실행 이름 |
| `name` | ROS graph에 표시할 실행 중인 노드 이름 |
| `output="screen"` | 노드 로그를 현재 터미널에 표시 |

Launch 파일의 `Node(...)`는 Python 소스 안의 `Node` 클래스를 직접 생성하는 코드가
아니다. 설치된 ROS 2 패키지에서 실행 항목을 찾아 별도의 프로세스로 시작하도록
Launch 시스템에 알려 주는 실행 정의이다.

```python
Node(
    package="week03_ros2_jetson",
    executable="joint_state_publisher",
    output="screen",
)
```

각 인자의 의미는 다음과 같다.

- `package="week03_ros2_jetson"`: 실행 파일을 어느 ROS 2 패키지에서 찾을지
  지정한다. `source install/setup.bash`로 현재 터미널에 등록된 패키지 중에서 이
  이름을 검색한다.
- `executable="joint_state_publisher"`: 해당 패키지에서 실행할 항목의 이름이다.
  Python 파일명 자체를 지정하는 것이 아니라 `setup.py`의 `console_scripts`에
  등록된 왼쪽 이름을 사용한다.
- `name="joint_state_publisher"`: 실행된 노드가 `ros2 node list`에 표시될 이름을
  지정한다. 생략하면 Python 코드에서 `Node`를 초기화할 때 지정한 이름을 사용한다.
- `output="screen"`: 실행된 프로세스의 표준 출력과 ROS 로그를 Launch를 실행한
  터미널 화면에 표시한다. 따라서 여러 노드의 시작 메시지와 오류를 한 터미널에서
  확인할 수 있다.

예를 들어 `setup.py`에 다음 진입점이 등록되어 있다면,

```python
"joint_state_publisher = week03_ros2_jetson.joint_state_publisher:main"
```

Launch의 `executable="joint_state_publisher"`는 이 진입점을 찾는다. 실행되면
`week03_ros2_jetson/joint_state_publisher.py` 모듈의 `main()` 함수가 호출된다.

```text
package 이름
week03_ros2_jetson
        ↓ 패키지 내부에서 executable 검색
joint_state_publisher
        ↓ setup.py의 console_scripts 연결
week03_ros2_jetson.joint_state_publisher:main
```

실습 1에서 사용하는 Publisher와 Listener 구성을 예로 들면 다음과 같다.

```python
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            Node(
                package="week03_ros2_jetson",
                executable="joint_state_publisher",
                name="joint_state_publisher",
                output="screen",
            ),
            Node(
                package="week03_ros2_jetson",
                executable="joint_state_listener",
                name="joint_state_listener",
                output="screen",
            ),
        ]
    )
```

실습 2의 Service Launch 구성 코드는 이론 자료에 제시하지 않는다. 어떤 노드가
함께 실행되어야 하는지는 각 노드의 데이터 흐름을 바탕으로 구성한다.

---

## 7. `setup.py`와 Launch·Config 파일 설치

`ament_python` 패키지에서 Python 노드는 `console_scripts`에 등록해야
`ros2 run`으로 실행할 수 있다. Launch와 YAML 파일은 Python 모듈이 아니므로
`data_files`에 별도로 등록해야 `ros2 launch`가 설치 공간에서 찾을 수 있다.

```text
패키지 원본
├── launch/*.launch.py
└── config/*.yaml
        │
        │ colcon build
        ▼
install/share/week03_ros2_jetson/
├── launch/
└── config/
```

실습 1에서 확인한 데이터 파일 등록 형식은 다음과 같다.

```python
(os.path.join("share", package_name, "config"), glob("config/*.yaml")),
(os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
```

`ros2 pkg create --build-type ament_python`이 `setup.py`, `setup.cfg`,
`package.xml` 등을 생성한다. `colcon build`가 이 파일들을 새로 만들어 주는 것은
아니다. 생성된 파일에는 실행 파일, 데이터 파일, 의존성 정보를 직접 등록해야 한다.

---

## 8. ROS 2 CLI 확인 도구

| 확인 항목 | 명령어 | 의미 |
|---|---|---|
| Topic 타입 | `ros2 topic type /joint_states` | 사용 중인 메시지 인터페이스 확인 |
| Topic 주기 | `ros2 topic hz /joint_states` | 초당 메시지 발행 횟수 확인 |
| Service 목록 | `ros2 service list` | 현재 발견된 Service 이름 확인 |
| Service 타입 | `ros2 service type /get_joint_state` | 요청·응답 인터페이스 확인 |
| Service 규격 | `ros2 interface show std_srvs/srv/Trigger` | Request와 Response 필드 확인 |
| Service 호출 | `ros2 service call /get_joint_state std_srvs/srv/Trigger "{}"` | 빈 Trigger Request를 한 번 전송 |

CLI 호출과 Python Client 호출은 같은 Server에 같은 형식의 요청을 보낸다. 차이는
사람이 터미널에서 직접 호출하는지, 다른 프로그램이 코드로 호출하는지에 있다.
