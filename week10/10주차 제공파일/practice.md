# [10주차] Gymnasium 환경 구조와 Episode 실행 — 실습 안내서

> `lecture.md`를 먼저 읽고 순서대로 수행한다.
> **PC = Windows PC 안의 WSL2 Ubuntu 22.04**이다. 아래 명령은 WSL 터미널에서 실행한다.
> Viewer는 WSLg로 표시된다. 이번에는 ROS 2·Jetson을 실행하지 않는다.
> 실습 프로젝트는 `~/week10/gymnasium_lab`, Python 코드는 그 안의 `week10_push_env/`이다.
> 가상환경은 `~/week10/.venv`를 사용한다. 시작할 때 이전 분반의 `~/week10`을 삭제하고 새로 준비한다.

## 0. 실습 전

최종 동작은 다음과 같다.

```text
이전 분반 자료 삭제 → 새 venv 생성 → 원본 모델과 제공 파일 배치 → TODO 1~6 완성
6차원 Observation·XYZ 3차원 Action 확인 → 한 Step의 다섯 반환값
Gymnasium API 확인 → 한 Episode → 세 Episode·Seed 비교
Viewer 확인 → 결과 기록 → 프로그램·가상환경 종료 → 실습 폴더 삭제
```

### 제공 파일 한눈에 보기

| 파일·폴더 | 역할 | 사용·수정 범위 |
|---|---|---|
| `gymnasium_lab_env.py` | Space·Observation·초기화·보상·종료 | TODO 1~5 작성 |
| `random_agent.py` | 무작위 Action으로 Episode 실행 | TODO 6 작성·실행 |
| `mujoco_simulation.py` | 모델·좌표변환·IK·물리·화면 | 제공 코드 사용 |
| `inspect_environment.py` | 장면·Space·한 Step의 결과 출력 | 실행·관찰 |
| `contact_demo.py` | 두 큐브의 로봇 접촉·이동 확인 | 선택 실습, 제공 코드 사용 |
| `task.yaml` | 작업영역·제어·Episode·보상 설정 | `config/`에 배치 |
| `models/` | 9주차 원본 실행 XML·STL·PNG | 전체 배치 |
| `requirements.txt` | 검증한 Python 패키지 버전 | 설치 |

추가 목표 표시·목표 도달·성공률은 없다. 물체를 특정 위치로 보내는 것이 완료 기준은 아니다.
학생은 핵심 코드 여섯 곳을 작성하고 입출력과 Episode 반복을 설명한다.

---

## 1. 파일 배치와 환경 준비

### 1.1 이전 분반 자료 삭제와 새 venv 생성

공용 PC에 이전 분반이 남긴 `~/week10`을 모두 삭제하고 처음부터 준비한다.
이 명령은 해당 폴더의 소스·모델·가상환경을 함께 삭제한다. 보관할 파일이 있다면 먼저 개인 저장소에 복사한다.
삭제할 폴더 밖으로 이동한 뒤 실행한다.

```bash
cd ~
rm -rf ~/week10
mkdir -p ~/week10
cd ~/week10
python3 -m venv .venv
source ~/week10/.venv/bin/activate
export PYTHONDONTWRITEBYTECODE=1
command -v python3
python3 -m pip --version
```

Python·pip 경로가 `~/week10/.venv/` 아래인지 확인한다.
`PYTHONDONTWRITEBYTECODE=1`은 Python 캐시 생성을 줄인다.
ROS Python 패키지가 필요하지 않으므로 venv 생성 시 `--system-site-packages`를 추가하지 않는다.

venv 생성 기능이 없어 `ensurepip is not available` 오류가 나면 다음 두 명령을 한 번 실행한다.
venv 생성에 성공했다면 이 설치 블록은 건너뛴다.

```bash
sudo apt update
sudo apt install python3.10-venv
```

설치 후 `cd ~/week10`, `python3 -m venv .venv`부터 생성·활성화 명령을 다시 실행한다. sudo 비밀번호는 WSL Ubuntu 계정의 비밀번호이다.
권한이 없으면 apt 설치는 조교가 수행한다. 이후 venv와 pip는 학생 계정으로 사용한다.

### 1.2 새 실습 위치에 제공 파일 배치

제공 파일을 아래 실습 위치에 배치한다. 1.1절의 삭제 명령은 파일 배치 전에만 실행한다.

배치 후 구조는 다음과 같다.

```text
~/week10/
├── .venv/                         Python 실행 환경
└── gymnasium_lab/                 프로젝트 루트, python -m 실행 위치
    ├── requirements.txt
    ├── config/task.yaml
    ├── models/
    │   ├── scene.xml
    │   ├── physicai_arm.xml
    │   ├── robot.xml
    │   └── assets/                STL·PNG 전체
    └── week10_push_env/
        ├── gymnasium_lab_env.py
        ├── mujoco_simulation.py
        ├── inspect_environment.py
        ├── random_agent.py
        └── contact_demo.py
```

### 1.3 의존성과 버전 확인

```bash
cd ~/week10/gymnasium_lab
source ~/week10/.venv/bin/activate
python3 -m pip install -r requirements.txt
python3 - <<'PY'
import sys
import numpy
import gymnasium
import mujoco
import yaml
assert sys.prefix != sys.base_prefix, 'venv를 활성화한다.'
assert numpy.__version__ == '1.26.4'
assert gymnasium.__version__ == '1.3.0'
assert mujoco.__version__ == '3.11.0'
assert yaml.__version__ == '6.0.3'
print('Python:', sys.executable)
print('NumPy:', numpy.__version__)
print('Gymnasium:', gymnasium.__version__)
print('MuJoCo:', mujoco.__version__)
print('PyYAML:', yaml.__version__)
print('PC packages OK')
PY
```

`PC packages OK`를 확인한다. 새 터미널에서는 프로젝트 루트 이동·venv 활성화·캐시 환경 변수를 다시 적용한다.

---

## 2. 핵심 코드 TODO 1~6 완성

`~/week10/gymnasium_lab/week10_push_env/`의 파일을 연다.
`lecture.md`와 제공 코드를 참고하여 TODO 1~6을 완성한다.
작성 범위는 `### TODO ###`로 표시된 부분이다.

### 2.1 TODO 1 — 두 Space 선언

`gymnasium_lab_env.py`의 `__init__()`에서 이번 환경의 Observation과 Action 규격에 맞게 두 Space 선언을 완성한다.

### 2.2 TODO 2 — Observation 구성

같은 파일의 `_observation()`에서 EEF, 초록 큐브, 파란 큐브의 XY를 순서대로 담은 Observation을 구성한다.

### 2.3 TODO 3 — `reset()`의 두 반환값

같은 파일의 `reset()`이 초기화 결과를 Gymnasium 규약에 맞게 반환하도록 완성한다.

### 2.4 TODO 4 — `step()`의 다섯 반환값

같은 파일의 `step()`이 행동 이후의 결과를 Gymnasium 규약에 맞게 반환하도록 완성한다.

### 2.5 TODO 5 — 종료와 시간 제한

같은 파일의 `step()`에서 큐브의 작업영역 이탈과 최대 Step 수 도달을 구분하여 종료 조건을 작성한다.
두 조건이 동시에 충족되면 작업영역 이탈에 따른 종료를 우선한다.

### 2.6 TODO 6 — Random Agent의 한 Step 연결

`random_agent.py`에서 무작위 Action 선택, 한 Step 실행, Episode의 Return 누적이 이어지도록 반복문을 완성한다.

---

## 3. 소스와 한 Step 확인

### 3.1 빈칸·문법 검사

```bash
cd ~/week10/gymnasium_lab
source ~/week10/.venv/bin/activate
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
from pathlib import Path
paths = sorted(Path('week10_push_env').glob('*.py'))
assert len(paths) == 5, 'Python 파일 배치를 확인한다.'
for path in paths:
    source = path.read_text(encoding='utf-8')
    assert '### TODO ###' not in source, f'남은 빈칸: {path}'
    compile(source, str(path), 'exec')
print('Source check OK')
PY
```

구문 검사만으로 동작 확인까지 완료된 것은 아니다. 다음 명령을 실행한다.

### 3.2 한 Step 실행

```bash
python3 -m week10_push_env.inspect_environment
```

| 출력 | 확인할 내용 |
|---|---|
| 모델 | `nq=20`, `nv=18`, `nu=6`, `dt=0.0020 s` |
| Space | Observation `(6,)`, Action `(3,)`, `float32` |
| 첫 Observation | 약 `[0.1999, 0, 0.3100, 0.0300, 0.3700, 0]` |
| Action | `[0.5, -0.25, 1.0]` |
| 요청 이동 XYZ | `[+0.004, -0.002, +0.005] m` |
| 실측 이동 XYZ | 검증 환경에서 약 `[+0.003447, -0.001836, +0.004262] m` |
| 행동 이후 EEF XYZ | 약 `[0.203383, -0.001836, 0.014109] m` |
| Reward | `{'action_cost': -0.013125}`, 합계 `-0.013125` |
| 종료 신호 | `False/False` |

이동량의 소수점 끝자리보다 요청과 실측의 차이를 확인한다.
Reward는 큐브 이동량이 아니라 Action 크기로 계산한다.

### 3.3 Gymnasium API·보상 확인

```bash
python3 - <<'PY'
from gymnasium.utils.env_checker import check_env
import numpy as np
from week10_push_env.gymnasium_lab_env import GymnasiumLabEnv

environment = GymnasiumLabEnv()
try:
    check_env(environment, skip_render_check=True)
    observation, info = environment.reset(seed=10)
    assert observation.shape == (6,) and observation.dtype == np.float32
    assert environment.observation_space.contains(observation)
    assert environment.action_space.shape == (3,)
    assert environment.action_space.dtype == np.float32
    before_z = info['eef_position'][2]
    observation, reward, terminated, truncated, info = environment.step(
        np.array([0.5, -0.25, 1.0], dtype=np.float32))
    assert abs(reward + 0.013125) < 1e-12
    assert info['eef_position'][2] > before_z
    assert not terminated and not truncated
    print('Gymnasium API OK, reward =', reward)
finally:
    environment.close()
PY
```

`Gymnasium API OK, reward = -0.013125`를 확인한다. `az=1`에 따라 실제 높이가 증가했는지도 검사한다.
검사기는 Observation Space의 상·하한이 무한대라는 경고를 출력할 수 있다.
이번에는 실측값을 자르지 않고 반환하기 위해 선택한 선언이므로 이 경고만으로 실패로 처리하지 않는다.
직접 생성한 환경에 `spec`이 없다는 안내가 나올 수도 있다.
예외·Assertion 실패는 수정한 뒤 진행한다. GUI는 5절에서 별도로 확인한다.

---

## 4. Episode 반복

### 4.1 먼저 한 회차를 끝까지 실행

```bash
python3 -m week10_push_env.random_agent --episodes 1 --seed 10
```

`steps=150`, `end=time_limit`, `completed episodes: 1/1`을 확인한다.
물리 시간 150 Step은 7.5초지만 화면 없는 실행은 실제 시간 7.5초보다 빠르게 끝날 수 있다.

### 4.2 세 Episode와 Return

```bash
python3 -m week10_push_env.random_agent --episodes 3 --seed 10
```

처음 세 Step에는 Action·Reward·종료 신호, 각 회차 끝에는 Step 수·Return·종료 원인이 출력된다.
검증 환경에서는 각 150 Step으로 끝났고 Return은 순서대로 약 `-1.446450`, `-1.492363`, `-1.629437`였다.
`end=time_limit`과 `completed episodes: 3/3`을 확인한다. 성공률은 표시하지 않는다.

```bash
python3 -m week10_push_env.random_agent --episodes 3 --seed 10
python3 -m week10_push_env.random_agent --episodes 1 --seed 11
```

같은 Seed의 첫 Action·Step 수·Return을 비교한다.
Seed 11에서는 Action 순서가 바뀌지만 XML의 초기 큐브 배치는 같다.
Return이 개선되는 것을 합격 조건으로 삼지 않는다.

## 5. Viewer 확인

### 5.1 정지 장면과 한 Step

```bash
python3 -m week10_push_env.inspect_environment --render
```

노란 로봇, 작업대·모니터·기둥, 검정·흰색 바구니, 25 mm 초록·파랑 큐브를 확인한다.
추가한 주황색 목표 원은 없다. 제목은 원본 XML의 `Week09 PhysicAI Arm`이다.
이 화면은 한 Step을 실행한 뒤 정지해 있다.
왼쪽 드래그로 시점을 회전하고 휠로 확대·축소한 뒤 창을 닫는다.
터미널 프롬프트로 돌아오는지도 확인한다.

### 5.2 움직이는 Episode

```bash
python3 -m week10_push_env.random_agent --episodes 1 --seed 10 --render
```

무작위 XYZ Action에 따라 EEF가 수평·높이 방향으로 움직이고 150 Step을 마치면 자동으로 닫히는 것을 확인한다.
중간에 닫은 회차는 완료 수에 포함하지 않는다. 기록할 회차는 끝까지 열어 둔다.

## 6. 선택 — 두 큐브의 접촉 확인

```bash
python3 -m week10_push_env.contact_demo
python3 -m week10_push_env.contact_demo --render
```

초록 확인 → 초기화 → 파랑 확인 순서로 제공한 Action을 실행한다.
각 회차에서 `contact=True`, `XY displacement`가 5 mm보다 큰지 확인한다.
검증값은 초록 약 64.0 mm, 파랑 약 37.2 mm였다. 변위는 시작점과 끝점의 XY 거리이다.
시연도 3차원 Action을 사용한다. X·Y 경로를 따라가며 Z 성분으로 초기 EEF 높이를 유지하도록 요청한다.
각 확인의 초기화 뒤에는 큐브 좌표를 덮어쓰지 않고 로봇 접촉으로 움직인다.
파란 큐브가 작업영역을 벗어나 종료되어도 이 선택 확인에서는 접촉·이동 여부를 점검한다.
11주차의 두 큐브를 서로 접촉시키는 학습과 이번 물리 확인을 구분한다.

## 7. 결과 기록과 종료·자리 정리

| 항목 | 기록할 내용 |
|---|---|
| Space·Observation | 두 shape·dtype, 6개 값의 순서·좌표계·단위 |
| Action | `[0.5, -0.25, 1.0]`의 XYZ 이동 요청과 실측의 차이, EEF 목표 Z 제한 |
| 메서드 | reset의 두 값, step의 다섯 값, render·close의 역할 |
| Reward·Return | 한 Step의 비용과 한 Episode의 합계 차이 |
| 종료 | 어느 큐브든 이탈하면 terminated, 150 Step이면 truncated가 되는 조건 |
| Seed | 같은 Action 순서 재현과 고정 초기 배치 |

제공 프로그램은 터미널에 결과를 출력한다. Viewer를 닫거나 실행 중 터미널에서 Ctrl+C로 중단한다.
`finally`의 `close()`로 자원을 정리하고 프롬프트로 돌아온다.
조교 확인과 필요한 제출을 마친 뒤, 보관할 소스·기록은 개인 저장소에 복사한다.
가상환경을 종료하고 실습 폴더 밖으로 이동한 다음 `~/week10` 전체를 삭제한다.

```bash
deactivate
cd ~
rm -rf ~/week10
```

**실습을 마치고 자리를 떠나기 전에 작성한 코드·모델·venv를 포함한 `~/week10`을 모두 삭제한다.** 다음 분반을 위해 실습 파일을 남겨 두지 않는다.
제출물에는 venv·`__pycache__`·`*.pyc`를 포함하지 않는다. 모델의 STL·PNG는 실행에 필요한 자산이다.

## 8. 문제 해결과 완료 체크

| 증상 | 확인할 내용 |
|---|---|
| 모듈을 찾지 못함 | `~/week10/gymnasium_lab`에서 `python3 -m ...`으로 실행한다. |
| 상대 import 오류 | `.py`를 직접 실행하지 않고 안내된 모듈 명령을 사용한다. |
| MuJoCo 등을 찾지 못함 | venv의 Python 경로와 requirements를 확인한다. |
| TODO에서 TypeError·ValueError·반환값 개수 오류 | 남은 빈칸·인자 순서·쉼표·shape의 Tuple을 확인한다. |
| Episode가 바로 끝나거나 끝나지 않음 | TODO 5의 조건과 step에서 받는 두 종료 신호를 확인한다. |
| 파일·Mesh 오류 | XML 세 개와 assets 전체를 같은 구조로 배치한다. |
| Viewer 표시 실패 | WSLg·DISPLAY·OpenGL을 확인한다. 필요한 libgl1·libglfw3는 조교가 준비한다. |
| 이전 목표·클래스 이름이 출력됨 | 이전 실습 폴더에서 실행하지 않았는지 확인한다. |

- [ ] WSL·venv·패키지 버전을 확인한다.
- [ ] TODO 1~6, Source check, Gymnasium API 확인을 통과한다.
- [ ] 6차원 XY 관측·XYZ 3차원 Action·반환값 개수를 설명한다.
- [ ] Reward `-0.013125`와 Episode의 Return을 구분한다.
- [ ] 한 회차·세 회차 Episode와 Seed 비교를 실행한다.
- [ ] 원본 모델과 두 큐브를 Viewer로 확인하고 정상 종료한다.
- [ ] 목표 도달·성공률을 10주차 완료 조건으로 삼지 않는다.
- [ ] 제출물에서 캐시를 제외한다.
- [ ] 조교 확인·제출·개인 백업 후 `~/week10` 전체를 삭제하고 자리를 정리한다.
