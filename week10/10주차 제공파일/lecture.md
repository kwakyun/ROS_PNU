# [10주차] 강화학습 환경과 Gymnasium의 기초 — 수업 내용

## 0. 이번 시간에 알아볼 것

로봇이 물체를 움직이려면 현재 상황을 파악하고, 행동을 선택하고, 그 결과를 확인해야 한다.
9주차에는 사람이 관절 목표를 정하여 로봇이나 시뮬레이션에 전달했다.
강화학습에서는 프로그램이 행동을 선택하고 결과를 경험하면서, 더 좋은 행동을 선택하는 방법을 배운다.

그런데 학습 프로그램을 만들기 전에 먼저 준비해야 할 것이 있다.
**현재 상황을 어떤 값으로 알려 줄 것인지, 행동을 어떻게 전달할 것인지, 행동 결과를 어떤 형식으로 돌려줄 것인지**를 정해야 한다.
이번 시간에는 이 연결을 Gymnasium으로 구성하는 방법을 배운다.

수업을 마치면 다음 질문에 답할 수 있어야 한다.

- 강화학습에서 Agent와 Environment는 무엇을 주고받는가?
- Gymnasium은 어떤 라이브러리이며 MuJoCo와 역할이 어떻게 다른가?
- `reset()`과 `step()`은 언제 호출하고 어떤 값을 받는가?
- Observation·Action을 배열로 표현하고 Space를 선언하는 이유는 무엇인가?
- 한 번의 행동을 반복하여 하나의 Episode를 실행하려면 어떤 코드가 필요한가?

이번에는 **학습에 사용할 환경을 만들고 사용하는 단계**까지 진행한다.
행동을 선택하는 규칙을 학습으로 바꾸는 과정은 11주차에서 다룬다.

---

## 1. 강화학습은 무엇을 배우는가

### 1.1 행동의 결과를 경험하며 선택 방법을 바꾼다

로봇 팔이 물체를 움직이는 상황을 생각해 보자.
같은 방향으로 팔을 움직여도 현재 팔과 물체의 위치에 따라 결과가 달라진다.
물체에 닿지 않으면 팔만 움직이고, 닿으면 물체가 밀리거나 회전할 수 있다.
따라서 다음 행동을 정하려면 행동 이후 상황이 어떻게 달라졌는지 다시 확인해야 한다.

강화학습(Reinforcement Learning)은 이러한 상호작용에서 얻은 경험을 이용해
**앞으로 받을 보상의 누적값이 커지도록 행동 선택 방법을 개선하는 학습 방식**이다.
매 순간의 보상만 크게 만드는 것과 앞으로의 결과까지 고려하는 것은 다를 수 있다.
예를 들어 물체를 밀기 위해 먼저 물체 뒤쪽으로 이동하는 행동은 당장 물체를 움직이지 않아도 이후 동작에 도움이 될 수 있다.

이때 행동을 선택하는 주체를 **Agent**, 행동을 받아 결과를 돌려주는 대상을 **Environment(환경)** 라고 한다.
로봇 실습의 환경에는 로봇과 물체의 움직임뿐 아니라, 어떤 정보를 알려 주고 어떤 보상을 계산할지도 포함된다.

### 1.2 관측·행동·보상으로 연결한다

환경은 내부의 모든 정보를 그대로 전달할 필요는 없다.
Agent가 판단에 사용할 정보를 골라 전달하며, 이를 **Observation(관측)**이라고 한다.
Agent가 환경에 전달하는 명령은 **Action(행동)**, 환경이 행동 이후 계산하는 수치 피드백은 **Reward(보상)**이다.

```text
                 ① 현재 정보를 받는다: Observation
          ┌──────────────────────────────────────┐
          ↓                                      │
       Agent                                  Environment
          │                                      ↑
          └──────── ② 행동을 보낸다: Action ────────┘
          ↑                                      │
          └── ③ 새 Observation·Reward·종료 여부 ───┘
```

| 용어 | 로봇 실습에서 생각할 수 있는 예 |
|---|---|
| Observation | 팔 끝과 물체의 현재 위치 |
| Action | 팔 끝을 X·Y·Z 방향으로 얼마만큼 움직일지 |
| Reward | 이번 행동에 대해 환경이 계산한 점수나 비용 |
| Policy(정책) | 어떤 상황에서 어떤 행동을 선택할지 정하는 규칙 |

정책은 처음부터 신경망일 필요는 없다.
사람이 작성한 규칙으로 행동을 정할 수도 있고, 단순히 무작위로 행동을 뽑을 수도 있다.
강화학습에서는 경험을 바탕으로 정책을 개선하지만, 무작위 행동을 반복하기만 하면 정책이 저절로 학습되는 것은 아니다.

### 1.3 이번 수업은 상호작용을 준비하는 단계이다

이번 Agent는 **Random Agent**이다. 유효한 범위에서 행동을 무작위로 뽑으며 학습으로 선택 방법을 바꾸지 않는다.
이를 사용하면 학습 알고리즘을 붙이기 전에 관측·행동·보상이 올바르게 오가는지 확인할 수 있다.

```text
10주차: 환경의 입출력 준비 → 무작위 행동으로 실행 확인
11주차: 준비한 환경을 이용하여 SAC 정책 학습
```

강화학습과 환경 사용의 기본 흐름은 [Gymnasium 기본 사용 안내](https://gymnasium.farama.org/introduction/basic_usage/)에서도 확인할 수 있다.

---

## 2. Gymnasium은 왜 필요한가

### 2.1 서로 다른 환경을 같은 방식으로 사용하기 위해

환경을 만드는 방법은 다양하다.
로봇 시뮬레이션, 게임, 차량 제어는 상태와 행동의 종류도 다르고 내부 계산도 다르다.
환경마다 시작·행동 실행·결과 반환 방법까지 다르면, 학습 프로그램도 환경에 맞춰 연결 부분을 계속 바꿔야 한다.

**Gymnasium은 강화학습 환경을 만들고 사용하는 공통 인터페이스를 제공하는 Python 라이브러리**이다.
인터페이스란 여기서 “어떤 메서드를 어떤 인자로 호출하고, 어떤 값을 돌려받는가”에 대한 약속이다.

예를 들어 로봇이든 게임이든 다음과 같은 형태로 사용할 수 있도록 한다.

```python
observation, info = environment.reset()
observation, reward, terminated, truncated, info = environment.step(action)
```

환경 내부가 무엇을 계산하든 호출하는 쪽은 이 형식으로 시작 상태와 행동 결과를 받을 수 있다.
다만 환경마다 관측·행동의 내용과 모양은 다르므로 그 규격도 함께 확인해야 한다. 이 규격은 5절에서 설명한다.

### 2.2 Gymnasium과 MuJoCo의 역할

9주차에서 사용한 MuJoCo는 물리 엔진이다.
관절 목표를 주었을 때 팔이 어떻게 움직이고, 팔과 큐브가 부딪히면 어떤 운동이 생기는지 계산한다.
Gymnasium은 그 계산을 Agent가 사용할 수 있도록 초기화·행동 실행·결과 반환의 형식으로 연결한다.

| 역할 | 이번 수업에서 담당하는 것 |
|---|---|
| MuJoCo | 로봇과 큐브의 다음 물리 상태를 계산한다. |
| Gymnasium 환경 | 행동을 받아 물리 계산을 실행하고 관측·보상·종료 여부를 반환한다. |
| Agent | 환경이 허용하는 행동 중 무엇을 실행할지 정한다. |
| 학습 알고리즘 | 상호작용으로 모은 경험을 이용해 정책을 개선한다. 이번 시간에는 사용하지 않는다. |

Gymnasium을 사용한다고 학습이 자동으로 진행되지는 않는다.
환경을 실행하는 코드와 정책을 학습시키는 코드는 구분해야 한다.

### 2.3 이번에 사용할 로봇 환경

이번 환경에는 로봇 팔과 초록·파랑 큐브가 있다.
Agent에게는 팔 끝과 두 큐브의 XY 위치를 알려 주고, Agent로부터는 팔 끝 **EEF(End Effector)** 의 XYZ 이동 요청을 받게 한다.

| 환경의 요소 | 관측할 정보 | 행동에 따라 생길 수 있는 변화 |
|---|---|---|
| 로봇 팔 | 팔 끝의 X·Y 위치 | 이동 요청을 받아 팔이 움직인다. |
| 초록 큐브 | 중심의 X·Y 위치 | 팔이나 다른 물체에 닿으면 밀리거나 회전할 수 있다. |
| 파란 큐브 | 중심의 X·Y 위치 | 초록 큐브와 마찬가지로 물리 접촉에 반응한다. |

이 장면을 보면서 두 가지를 정한다.
**“Agent에게 무엇을 알려 줄 것인가?”** 와 **“Agent가 무엇을 명령할 수 있게 할 것인가?”** 이다.
이번에는 위치 여섯 개를 알려 주고 X·Y·Z 이동 비율 세 개를 명령하게 한다.
관측에 선택한 정보의 개수와 명령할 수 있는 방향의 개수는 서로 다를 수 있다.
영상에 보이는 모든 것을 입력으로 사용하거나 모든 관절을 각각 명령하는 구성은 아니다.

---

## 3. 환경을 만들고 한 번 사용해 보기

### 3.1 환경 객체를 생성한다

제공 코드의 `GymnasiumLabEnv`는 `gymnasium.Env`를 상속하여 만든 환경 클래스이다.
클래스는 환경의 동작을 정의하고, 생성한 객체는 실행 중인 한 환경의 상태를 관리한다.

```python
from week10_push_env.gymnasium_lab_env import GymnasiumLabEnv

environment = GymnasiumLabEnv()
```

`week10_push_env`는 실습 안내서에 따라 Python 파일을 배치할 폴더이고,
`gymnasium_lab_env`는 그 안의 `gymnasium_lab_env.py` 파일을 뜻한다.
이 파일에 정의된 `GymnasiumLabEnv` 클래스를 직접 가져와 환경 객체를 만든다.
실습 프로젝트의 최상위 폴더에서 실행하며, `__init__.py`나 환경 ID 등록은 필요하지 않다.

`environment`는 생성한 환경 객체를 가리키는 변수이다.
`environment.reset()`처럼 객체에 속한 함수를 호출할 수 있다.
객체를 만들었다고 곧바로 행동을 반복하는 것은 아니다. 먼저 시작 상태를 준비해야 한다.

### 3.2 `reset()`으로 시작 상태를 받는다

```python
observation, info = environment.reset(seed=10)
```

`reset()`은 한 회차를 시작할 수 있도록 환경을 초기화한다.
이번 환경에서는 로봇과 두 큐브를 초기 상태로 복구하고 Step 수와 시간을 초기화한다.
이때 **첫 Observation과 추가 정보 `info` 두 개**를 반환한다.

첫 Observation이 필요한 이유는 Agent가 첫 행동을 선택하기 전에 현재 상황을 알아야 하기 때문이다.
`reset()`에는 실행할 Action을 전달하지 않는다.

`seed=10`은 난수 생성기를 준비하는 인자이다.
지금은 환경의 초기 배치가 고정되어 있으므로 Seed를 바꾸어도 큐브 위치가 바뀌지는 않는다.
무작위 행동의 Seed와의 관계는 8절에서 다시 설명한다.

### 3.3 `step(action)`으로 한 번 행동한다

```python
observation, reward, terminated, truncated, info = environment.step(action)
```

`step()`은 전달한 Action을 실행하고 **다섯 값**을 반환한다.

| 반환 순서 | 이름 | 의미 |
|---|---|---|
| 1 | `observation` | 행동 이후 새로 확인한 정보 |
| 2 | `reward` | 이번 행동에 대해 계산한 보상 |
| 3 | `terminated` | 환경에서 정한 종료 조건에 도달했는지 |
| 4 | `truncated` | 시간 제한 등으로 회차를 중단해야 하는지 |
| 5 | `info` | 실행 결과를 확인할 때 쓸 추가 정보 |

왼쪽의 다섯 변수는 오른쪽 반환값을 순서대로 받는다.
이전과 같은 변수명 `observation`을 사용하면 그 변수는 이제 **행동 이후의 새 관측**을 가리킨다.
다음 행동은 이 새 정보를 바탕으로 선택할 수 있다.

### 3.4 한 번의 상호작용을 코드로 연결한다

다음은 제공 환경을 완성한 뒤 실행할 수 있는 설명용 예제이다.
코드를 읽을 때 **생성 → 초기화 → 행동 → 결과 확인 → 정리**의 순서에 주목한다.
실습 파일 배치와 TODO 작성은 `practice.md`를 따른다.

```python
import numpy as np
from week10_push_env.gymnasium_lab_env import GymnasiumLabEnv

environment = GymnasiumLabEnv()
try:
    observation, info = environment.reset(seed=10)
    print("처음 받은 관측:", observation)

    action = np.array([0.5, -0.25, 1.0], dtype=np.float32)
    observation, reward, terminated, truncated, info = environment.step(action)

    print("행동 이후 관측:", observation)
    print("행동 이후 EEF XYZ:", info["eef_position"])
    print("보상:", reward)
    print("종료 여부:", terminated, truncated)
finally:
    environment.close()
```

처음에는 팔 끝의 XY가 약 `(0.1999, 0.0000)`이고,
한 번 행동한 뒤에는 약 `(0.2034, -0.0018)`로 바뀐다.
EEF 높이도 약 `0.009847 m`에서 `0.014109 m`로 올라간다. 높이는 `info["eef_position"][2]`로 확인한다.
큐브에 아직 닿지 않았다면 두 큐브의 XY는 거의 그대로일 수 있다.
이 예제에서 받은 값이 각각 무엇을 뜻하는지 다음 절에서 자세히 살펴본다.

메서드의 공통 형식은 [Gymnasium Env API](https://gymnasium.farama.org/api/env/)를 참고한다.

---

## 4. 이 환경은 무엇을 보고 무엇을 움직이는가

### 4.1 Observation의 여섯 숫자 읽기

이번 환경은 다음 순서의 NumPy 배열을 반환한다.

```text
[eef_x, eef_y, green_x, green_y, blue_x, blue_y]

초기 예: [0.1999, 0.0000, 0.3100, 0.0300, 0.3700, 0.0000]
```

| 위치 | 의미 | 초기값의 해석 |
|---|---|---|
| `observation[0:2]` | EEF의 X·Y | 팔 끝이 약 `(0.1999, 0.0000)` m에 있다. |
| `observation[2:4]` | 초록 큐브 중심의 X·Y | 초록 큐브가 `(0.3100, 0.0300)` m에 있다. |
| `observation[4:6]` | 파란 큐브 중심의 X·Y | 파란 큐브가 `(0.3700, 0.0000)` m에 있다. |

모든 위치는 로봇 `base_link` 좌표계 기준이고 단위는 m이다.
예를 들어 0.310 m는 31 cm이다. 카메라 영상의 픽셀 좌표나 관절각 rad와 구분한다.

배열의 순서도 정보의 일부이다.
값이 여섯 개라고 해도 초록과 파랑의 순서를 바꾸면 읽는 쪽은 다른 의미로 해석하게 된다.
제공 `_observation()`은 세 위치 함수에서 `[:2]`로 XY를 선택하여 연결한다.

Observation은 환경 내부의 전체 물리 상태를 모두 담은 것이 아니다.
이번에는 속도·큐브 회전·높이·접촉 등을 제외하고 위치 여섯 값만 선택했다.
따라서 “Agent가 받은 관측”과 “시뮬레이터가 관리하는 전체 상태”는 같지 않다.
Action이 XYZ 3차원이어도 Observation에 높이가 자동으로 추가되지는 않는다.
이번 실습은 환경 API를 익히는 무작위 실행이며, EEF 높이는 `info`로 별도 확인한다.
이 6차원 관측만으로 XYZ 제어에 필요한 모든 상태를 알려 주는 것은 아니다.

### 4.2 Action의 세 숫자 읽기

Action은 X·Y·Z 방향의 이동 비율 세 개이다. 각각 -1부터 1까지 사용한다.
11·12주차와 동일하게 X·Y는 한 Step에 최대 8 mm, Z는 최대 5 mm 이동을 요청한다.

```text
action = [X 방향 이동 비율, Y 방향 이동 비율, Z 방향 이동 비율]
요청 이동량 = action × [0.008, 0.008, 0.005] m
EEF 목표 위치 = 현재 EEF XYZ + 요청 이동량
```

| Action | 요청하는 움직임 |
|---|---|
| `[1.0, 0.0, 0.0]` | X 방향 +8 mm |
| `[0.0, -0.5, 0.0]` | Y 방향 -4 mm |
| `[0.0, 0.0, 1.0]` | Z 방향 +5 mm |
| `[0.5, -0.25, 1.0]` | X 방향 +4 mm, Y 방향 -2 mm, Z 방향 +5 mm |
| `[0.0, 0.0, 0.0]` | XYZ 목표 이동량 0 mm |

EEF 목표 위치는 X `[0.15, 0.40]`, Y `[-0.14, 0.14]`, Z `[0.008, 0.035]` m 안으로 제한한다.
예를 들어 현재 Z가 `0.033 m`이면 `az=1`을 넣어도 목표 Z는 `0.038 m`가 아닌 상한 `0.035 m`가 된다.
이는 로봇에 요청할 목표 위치의 제한이며 실제 위치를 강제로 덮어쓰는 처리는 아니다.

이 숫자는 관절각도 아니고 힘도 아니다. 이번 환경에서 **EEF 이동 요청으로 해석하기로 정한 값**이다.
Action의 의미는 환경을 설계할 때 정하며, 모든 Gymnasium 환경이 같은 명령을 사용하는 것은 아니다.

요청한 만큼 즉시 이동하는 것도 아니다.
제공 제어 코드가 EEF 목표를 관절 목표로 변환하고 MuJoCo가 물리 운동을 계산한다.
IK 오차·관절 제한·물리 응답·접촉에 따라 실제 이동량이 요청과 다를 수 있다.
`[0, 0, 0]`을 넣어도 물리 계산은 진행하므로 움직이던 물체까지 즉시 정지시키는 명령은 아니다.

### 4.3 `info`는 추가 확인용 정보이다

`info`는 이름과 값을 연결한 Dictionary이다. 예를 들어 다음과 같이 확인한다.

```python
print(info["elapsed_steps"])       # 실행한 환경 Step 수
print(info["eef_position"])        # 실제 EEF XYZ
print(info["outside_cubes"])       # 영역 밖 큐브의 색 이름 목록
```

Observation이 Agent에 전달할 관측이라면, `info`는 상태를 점검하거나 결과를 분석할 때 쓰는 추가 정보이다.
이번에는 XYZ·Step 수·이탈 여부·보상 항·접촉 진단 등이 들어간다.
`info`에 있는 값을 전부 Agent가 입력으로 받는다고 생각하지 않는다.
코드에서 따로 꺼내 사용하지 않으면 6차원 Observation에 자동으로 포함되지 않는다.

---

## 5. 입출력의 규격 — Space

### 5.1 값뿐 아니라 모양과 자료형도 맞아야 한다

앞에서 Observation은 값 여섯 개, Action은 값 세 개로 정했다.
만약 Agent가 Action을 두 개 보내거나 환경이 갑자기 Observation을 다섯 개 반환하면 어떻게 될까?
숫자만 전달되었다고 해서 연결이 올바른 것은 아니다.

환경과 Agent가 함께 확인할 수 있도록 **값의 범위·배열 모양·자료형을 선언한 것이 Space**이다.
`observation_space`는 환경이 반환할 관측의 규격,
`action_space`는 환경이 받을 행동의 규격을 뜻한다.
Space는 실제 관측이나 실제 행동 한 개가 아니라, 그 값들이 따라야 할 규격이다.

### 5.2 연속적인 값은 `spaces.Box`로 표현한다

위치나 이동 비율은 중간값을 가질 수 있는 연속적인 값이다.
이런 값의 범위를 Gymnasium의 `spaces.Box`로 선언할 수 있다.

```python
from gymnasium import spaces
import numpy as np

action_space = spaces.Box(
    low=-1.0, high=1.0, shape=(3,), dtype=np.float32
)
```

| 인자 | 이번 선언의 의미 |
|---|---|
| `low=-1.0` | 각 성분의 최소값 |
| `high=1.0` | 각 성분의 최대값 |
| `shape=(3,)` | XYZ 값 세 개를 가진 1차원 배열 |
| `dtype=np.float32` | 각 원소를 표현하는 NumPy 실수 자료형 |

`(3,)`는 배열의 모양을 표현하는 Tuple이다. 값 세 개가 들어 있는 1차원 배열을 뜻하며, 3차원 배열이라는 뜻은 아니다.
`dtype`은 숫자를 저장할 자료형을 지정한다.

이번 Observation도 연속적인 실수 배열이므로 Box로 선언한다.

```python
observation_space = spaces.Box(
    low=-np.inf, high=np.inf, shape=(6,), dtype=np.float32
)
```

`np.inf`는 무한대를 나타낸다. 여기서는 Observation의 각 성분에 유한한 상·하한을 따로 정하지 않은 것이다.
큐브가 허용 작업영역을 벗어났을 때도 실제 위치를 잘라내지 않고 반환하기 위해 이렇게 선언한다.
이는 정상 운영 영역이 무한하다는 뜻이 아니다. 작업영역은 뒤에서 설명하는 종료 조건으로 따로 검사한다.
실제로 측정해 반환하는 좌표에는 유한한 값이 들어가야 한다.

### 5.3 규격 확인과 무작위 추출

Space 객체는 규격을 확인하거나 유효한 값을 뽑는 메서드도 제공한다.

```python
valid_action = np.array([0.5, -0.25, 1.0], dtype=np.float32)
invalid_action = np.array([0.5, -0.25], dtype=np.float32)

print(action_space.contains(valid_action))    # True
print(action_space.contains(invalid_action))  # False: 값이 두 개이다.

random_action = action_space.sample()
print(random_action.shape)                   # (3,)
```

`contains()`는 범위·모양·자료형이 규격에 맞는지 확인한다.
`sample()`은 Space에 맞는 값 하나를 무작위로 추출한다. 목표에 유리한 행동을 찾아 주는 메서드는 아니다.
이 `sample()`을 사용하여 이번 Random Agent를 구성한다.
[Gymnasium Box API](https://gymnasium.farama.org/api/spaces/fundamental/)

---

## 6. Reward를 받고 Episode를 끝내기

### 6.1 이번 환경의 보상 계산

환경은 Action 이후의 관측과 함께 Reward를 반환한다.
Reward의 의미는 환경을 설계하는 사람이 정한다.
예를 들어 목표까지의 거리나 사용한 에너지를 평가에 사용할 수 있으며, 숫자를 어떻게 정의하느냐에 따라 학습 방향도 달라진다.

이번에는 보상 반환 구조를 쉽게 읽기 위해 **행동 크기에 따른 비용**을 제공한다.

```text
reward = -0.01 × (action_x² + action_y² + action_z²)
```

| Action | 계산 결과 |
|---|---:|
| `[0, 0, 0]` | `0` |
| `[0.5, -0.25, 1]` | `-0.013125` |
| `[0, 0, 1]` | `-0.01` |
| `[1, -1, 1]` | `-0.03` |

보상은 음수일 수도 있다. 이 식에서는 행동 크기가 클수록 더 큰 비용을 받는다.
실제 이동량이나 큐브가 움직였는지는 이 식에 들어가지 않는다.

이 보상만 크게 만들려고 하면 `[0, 0, 0]`이 유리하다.
물체 밀기 정책을 학습할 때 이 식 하나만으로 충분하다는 뜻은 아니다.
이번에는 보상 숫자가 만들어지고 반환되는 구조를 익히며, 과제 수행에 맞는 보상은 이후 학습에서 다룬다.

### 6.2 한 Episode와 누적 보상

초기화로 시작하여 종료할 때까지 이어지는 한 회차를 **Episode**라고 한다.
한 Episode 안에는 여러 번의 `step()`이 들어간다.

```text
reset() → step() → step() → ... → 종료
                   한 Episode

reset() → step() → step() → ... → 종료
                 다음 Episode
```

이번 수업에서는 한 Episode 동안 받은 Reward를 모두 더한 값을 **Return**으로 기록한다.
한 Step에서 받은 Reward와 여러 Step의 합인 Return을 구분한다.
예를 들어 세 Step의 Reward가 `-0.01`, `0`, `-0.02`이면 Return은 `-0.03`이다.

### 6.3 종료 신호가 두 개인 이유

환경에서 정한 종료 조건을 만족한 것과, 정해 둔 시간 제한 때문에 멈추는 것은 다른 상황이다.
Gymnasium은 이를 `terminated`와 `truncated`로 나누어 알려 준다.
종료 조건의 구체적인 의미는 환경에 따라 달라지며, 이번 환경은 다음과 같이 정했다.

| 상황 | `terminated` | `truncated` |
|---|---|---|
| 계속 진행할 수 있음 | `False` | `False` |
| 어느 큐브든 중심 XY가 작업영역 밖으로 나감 | `True` | `False` |
| 이탈 없이 최대 150 Step에 도달함 | `False` | `True` |

이번 작업영역은 X `[0.15, 0.40]`, Y `[-0.14, 0.14]` m이며 경계값 자체는 안쪽으로 취급한다.
앞의 EEF 목표 XYZ 제한과 달리, 이 종료 판정은 두 큐브 중심의 XY를 검사한다.
높이·회전이나 두 큐브 접촉은 이번 종료 조건에 포함하지 않는다.
마지막 Step에서 이탈하면 환경 종료를 우선하여 `terminated=True`, `truncated=False`로 반환한다.

어느 신호든 True가 되면 해당 회차의 반복을 끝내고 다음 회차를 `reset()`으로 시작한다.
이번 실습에는 별도의 성공 조건이나 성공률이 없으며, Return이 높아야 완료되는 것도 아니다.

---

## 7. 한 번의 행동을 Episode 반복으로 확장하기

이제 한 Step 예제를 반복문으로 바꿀 수 있다.
처음 관측을 받은 뒤 행동을 고르고, 새 결과를 받아 다시 행동하는 흐름이다.

```python
from week10_push_env.gymnasium_lab_env import GymnasiumLabEnv

environment = GymnasiumLabEnv()
try:
    observation, info = environment.reset(seed=10)
    environment.action_space.seed(10)
    terminated = False
    truncated = False
    episode_return = 0.0

    while not (terminated or truncated):
        action = environment.action_space.sample()
        observation, reward, terminated, truncated, info = environment.step(action)
        episode_return += reward

    print("실행한 Step 수:", info["elapsed_steps"])
    print("Episode의 Return:", episode_return)
finally:
    environment.close()
```

`terminated or truncated`는 둘 중 하나라도 True이면 True이다.
앞에 `not`을 붙였으므로, 둘 다 False인 동안 반복한다.
이번 예제는 매 Step에 `sample()`을 호출하므로 무작위 행동을 선택한다.
새 Observation은 받지만 이를 분석하여 Action을 고르지는 않는다.

여러 Episode를 실행하려면 위의 초기화와 반복을 회차마다 다시 수행한다.
`reset()` 뒤에는 `episode_return`과 두 종료 변수를 다시 초기화해야 한다.
제공 `random_agent.py`는 이 과정을 반복하고 Step 수·Return·종료 원인을 출력한다.

---

## 8. 재현·화면 표시·자원 정리

### 8.1 Seed로 같은 무작위 행동 순서를 만들기

무작위 행동도 같은 조건으로 다시 실행하고 싶을 수 있다.
Seed는 난수 생성기를 같은 방식으로 초기화하기 위해 사용하는 값이다.

```python
observation, info = environment.reset(seed=10)
environment.action_space.seed(10)
```

첫 줄은 환경의 난수 생성기를, 둘째 줄은 Action Space의 난수 생성기를 준비한다.
따라서 같은 Action 추출 순서를 재현하려면 둘째 줄도 필요하다.
`reset(seed=10)`만 호출하면 `action_space.sample()`까지 같은 순서가 된다고 가정하지 않는다.

이번 초기 배치는 고정되어 있으므로 Seed를 바꾸어도 초기 큐브 위치는 유지된다.
제공 Random Agent의 Seed를 바꾸면 무작위 행동 순서가 바뀐다.
같은 라이브러리 버전·설정·Seed를 기준으로 결과를 비교한다.

### 8.2 `render()`로 현재 상태 보기

계산 결과를 화면으로 보고 싶다면 환경 생성 시 렌더링 방식을 지정한다.

```python
environment = GymnasiumLabEnv(render_mode="human")
```

제공 환경은 이 모드에서 `reset()`과 `step()` 내부에 `render()`를 호출하여 Viewer를 갱신한다.
직접 `environment.render()`를 호출하면 현재 상태를 다시 표시할 수도 있다.
반면 `GymnasiumLabEnv()`처럼 생성하면 화면 없이 같은 물리 계산을 수행한다.

| 생성 시 설정 | `render()`의 동작 |
|---|---|
| `render_mode=None` | 화면을 만들지 않으며 `None`을 반환한다. |
| `render_mode="human"` | WSLg Viewer에 현재 상태를 표시한다. |
| `render_mode="rgb_array"` | 높이 480·너비 640·RGB 세 채널의 이미지 배열을 반환한다. |

화면 갱신은 물리 계산과 다르다. `render()`만 반복하면 물리 시간이 진행되는 것은 아니다.
이번에는 `step()` 안에서 물리 계산을 진행한 뒤 그 결과를 화면으로 보여 준다.

### 8.3 `close()`로 실행 마무리하기

`close()`는 Viewer와 이미지 렌더링 자원을 정리한다.
앞의 예제들이 `try/finally`를 사용하는 이유는 실행 중 오류나 중단이 생겨도 정리를 수행하기 위해서이다.
제공 GUI 프로그램은 창을 닫거나 회차를 마치면 환경을 정리하고 종료한다.

---

## 9. 제공 코드 안에서는 어떻게 연결되는가

지금까지는 Agent가 환경을 사용하는 쪽에서 살펴보았다.
실습에서는 그 연결을 만드는 환경 코드의 일부도 작성한다.

```text
random_agent.py
  │  행동을 선택하여 environment.step(action) 호출
  ↓
GymnasiumLabEnv
  │  입력 검사 → 시뮬레이션에 이동 요청
  ↓
MujocoArmSimulation
  │  EEF 목표 → IK로 관절 목표 계산 → data.ctrl
  │  → MuJoCo 물리 계산 → 실제 위치 갱신
  ↓
GymnasiumLabEnv
  │  새 Observation·Reward·종료 신호·info 구성
  ↓
random_agent.py
     반환값 저장 → Return 누적 → 반복 또는 종료
```

`gymnasium_lab_env.py`는 Gymnasium의 입출력과 회차 처리를,
`mujoco_simulation.py`는 물리 계산·좌표변환·IK·화면을 담당한다.
Agent가 모든 MuJoCo 배열을 직접 수정하지 않아도 환경을 통해 행동을 실행할 수 있도록 나눈 것이다.

물리 계산 간격은 0.002초이고 환경 Step마다 25번 진행하므로, 한 Step은 시뮬레이션 시간 0.05초이다.
150 Step의 물리 시간은 7.5초이지만 이를 계산하는 실제 시간은 PC 성능과 화면 표시 여부에 따라 달라진다.
환경 Step 한 번, MuJoCo 물리 계산 한 번, 화면 갱신 한 번이 모두 같은 의미는 아니다.
IK 수식과 접촉 파라미터 튜닝은 제공 코드를 사용하고 이번 작성 범위에 포함하지 않는다.

## 10. 이번 실습에서 작성할 부분

| TODO | 작성하는 내용 | 연결되는 개념 |
|---|---|---|
| 1 | Observation·Action Space 선언 | 서로 주고받을 값의 규격 |
| 2 | EEF·초록·파랑의 XY 연결 | Agent에게 제공할 관측 |
| 3 | `reset()`의 두 반환값 | 새 Episode의 시작 |
| 4 | `step()`의 다섯 반환값 | 한 번 행동한 결과 전달 |
| 5 | 두 종료 신호의 조건 | 종료와 시간 제한 구분 |
| 6 | Action 선택·Step 호출·Return 누적 | Agent와 환경의 반복 실행 |

배치·설치·작성 위치와 실행 명령은 `practice.md`를 따른다.
두 자유 큐브의 물리 접촉을 확인하는 프로그램은 선택 실습으로 제공한다.

이번에는 **환경을 올바르게 사용하고 구성하는 것**이 완료 기준이다.
10·11·12주차의 Action은 모두 XYZ 3차원이며 이동 배율도 같다.
Observation은 10주차의 XY 6차원에서 11·12주차의 관절·영상 좌표 등을 포함한 38차원으로 달라진다.
11주차에는 고정 배치에서 두 큐브 접촉을 성공 조건으로 SAC 정책을 학습하고,
12주차에는 초기 배치 무작위화와 과제 수행에 맞는 보상 설계를 다룬다.
