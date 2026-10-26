# [7주차] 컴퓨터 비전과 머신러닝 입문 — 실습 안내서

> 큐브 두 개와 tip의 정답을 직접 만들고, Jetson GPU로 지도학습한 뒤 새로운 장면에서 확인한다.
> 모든 코드와 패키지 설정은 완성본으로 제공됨.

## 1. 환경 확인

### 1.1 실행 폴더와 Python 환경

배포 폴더와 실행 폴더를 구분한다. 실제 작업은 Jetson의 `~/week7`에서 수행한다.
가상환경은 각 계정의 `~/week7/.venv`를 사용한다.

```bash
mkdir -p ~/week7
test -f ~/week7/.venv/pyvenv.cfg || python3 -m venv --system-site-packages ~/week7/.venv
```

매번 새 터미널을 열 때 다음과 같이 환경을 적용한다.

```bash
cd ~/week7
export WEEK7_DIR="$PWD"
source ~/ros2_base/install/setup.bash
source ~/week7/.venv/bin/activate
export PYTHONDONTWRITEBYTECODE=1

command -v python3
command -v colcon
python3 -m pip --version
```

Python과 pip 경로는 자기 계정의 `~/week7/.venv/` 아래여야 한다.

### Python 패키지 설치

현재 실습 Jetson의 NVIDIA torch 2.4 / CUDA 12.2 기준이다.
활성화한 학생 계정의 venv에서 아래 명령을 순서대로 실행한다. `sudo`는 사용하지 않는다.
정답 코드의 학습·추론에 필요한 Ultralytics 8.3.253과 의존성을 설치하고,
기존 NVIDIA torch·NumPy·시스템 OpenCV는 유지한다.

```bash
cd ~/week7
source ~/ros2_base/install/setup.bash
source ~/week7/.venv/bin/activate

# 기존 GPU 패키지 버전을 고정한다.
python3 - <<'PY'
import sys
import torch
from importlib.metadata import version
from pathlib import Path
assert sys.prefix != sys.base_prefix, 'venv 활성화 필요'
assert torch.__version__.startswith('2.4.'), '실습 PC의 NVIDIA torch 2.4가 필요합니다'
assert torch.cuda.is_available(), 'NVIDIA torch의 CUDA 환경을 확인하세요'
Path('week7-constraints.txt').write_text(
    ''.join(f'{name}==={version(name)}\n' for name in ('torch', 'numpy'))
)
PY

# 빌드 도구와 학습·추론 의존성을 설치한다.
python3 -m pip install -c week7-constraints.txt \
  'setuptools<81' wheel ninja \
  'matplotlib>=3.3.0' 'Pillow>=7.1.2' 'PyYAML>=5.3.1' \
  'requests>=2.23.0' 'scipy>=1.4.1' 'psutil>=5.8.0' \
  'polars>=0.20.0' 'ultralytics-thop>=2.0.18'

# torchvision 0.19.0을 현재 NVIDIA torch에 맞춰 CUDA 빌드한다.
(
set -e
export CUDA_HOME=/usr/local/cuda
export PATH="$CUDA_HOME/bin:$PATH"
command -v git
command -v g++
test -x "$CUDA_HOME/bin/nvcc"
mkdir -p ~/week7/build
VISION_BUILD_DIR=$(mktemp -d "$HOME/week7/build/torchvision-0.19.0.XXXXXX")
git clone --depth 1 --branch v0.19.0 https://github.com/pytorch/vision.git "$VISION_BUILD_DIR"
cd "$VISION_BUILD_DIR"
FORCE_CUDA=1 MAX_JOBS=2 BUILD_VERSION=0.19.0 \
  python3 -m pip install --no-build-isolation --no-deps .
)

# 정답 코드에서 사용하는 YOLO 패키지를 설치한다.
python3 -m pip install --no-deps ultralytics==8.3.253

# 이후 설치에서도 torchvision 버전을 유지한다.
python3 - <<'PY'
from importlib.metadata import version
from pathlib import Path
with Path('week7-constraints.txt').open('a') as f:
    f.write(f'torchvision==={version("torchvision")}\n')
PY
```

각 명령이 오류 없이 끝난 다음 다음 명령으로 진행한다. torchvision 빌드는 시간이 걸린다.
`--no-build-isolation --no-deps`는 기존 NVIDIA torch를 사용해 빌드하고,
Ultralytics의 `--no-deps`는 시스템 OpenCV와 GPU 패키지의 자동 교체를 막는다.
설치가 끝나면 바로 아래의 패키지 검사와 CUDA NMS 검사를 실행한다.

### 1.2 패키지 설치 상태와 GPU 확인

환경을 활성화한 터미널에서 다음을 실행한다. 패키지별 OK 또는 FAIL을 확인한다.
버전의 `-` 표시는 버전 속성이 없는 모듈이며, 설치 실패를 뜻하지 않는다.

```bash
python3 - <<'PY'
import importlib
import sys

failed = []
for name in (
    'numpy', 'yaml', 'cv2', 'torch', 'torchvision', 'ultralytics',
    'matplotlib', 'PIL', 'scipy', 'requests', 'psutil', 'polars', 'thop',
    'setuptools', 'rclpy', 'cv_bridge', 'ament_index_python', 'launch', 'launch_ros',
    'sensor_msgs.msg', 'geometry_msgs.msg', 'std_msgs.msg',
):
    try:
        module = importlib.import_module(name)
        print('OK  ', name, getattr(module, '__version__', '-'))
    except Exception as error:
        failed.append(name)
        print('FAIL', name, error)
sys.exit(bool(failed))
PY

python3 - <<'PY'
import cv2
import numpy as np
import torch
import torchvision
from cv_bridge import CvBridge
from importlib.metadata import version

assert version('ultralytics') == '8.3.253', 'Ultralytics 버전을 확인한다.'
assert torch.cuda.is_available(), 'CUDA를 사용할 수 없다.'
assert torchvision.extension._has_ops(), 'torchvision 연산을 사용할 수 없다.'
boxes = torch.tensor([[0., 0., 10., 10.]], device='cuda')
torchvision.ops.nms(boxes, torch.ones(1, device='cuda'), 0.5)
bridge = CvBridge()
image = np.zeros((8, 8, 3), dtype=np.uint8)
assert bridge.imgmsg_to_cv2(bridge.cv2_to_imgmsg(image, 'bgr8'), 'bgr8').shape == image.shape
print('GPU:', torch.cuda.get_device_name(0))
print('CUDA / torchvision CUDA NMS / cv_bridge: OK')
for line in cv2.getBuildInformation().splitlines():
    if 'GStreamer' in line or 'GUI:' in line:
        print(line)
PY
```

모든 패키지가 OK이고, GPU 이름과 연산 검사 OK가 출력되어야 한다.
GStreamer는 YES, GUI는 NONE이 아닌 사용 가능한 백엔드여야 한다.
검사 성공은 실제 카메라 수신이나 학습 완료를 보장하지 않는다. 뒤의 수집 화면과 1 Epoch 시험 학습도 확인한다.

### 1.3 카메라 연결 확인

```bash
ls -l /dev/video*
echo "$DISPLAY"

```

---

## 2. 완성 제공 파일 복사

### 2.1 source_code 내용물 전체 복사

`source_code`에는 빌드 전 ROS 2 패키지 구조가 완성되어 있다.
`source_code` 안의 파일과 `week07_vision_control` 폴더를 전부 `~/week7`에 복사한다.
`~/week7/source_code`가 아니라 아래 트리처럼 `~/week7/week07_vision_control`이 되도록 배치한다.
패키지를 별도로 생성하거나 파일을 하나씩 재배치할 필요는 없다.

배포자료가 `~/Desktop/7주차/7주차 제공파일`에 있으면 다음 명령으로 복사한다.

```bash
mkdir -p ~/week7
cp -a "$HOME/Desktop/7주차/7주차 제공파일/source_code/." "$HOME/week7/"
cd ~/week7
```

다른 경로에서 배포자료를 받았다면 파일 관리자에서 `source_code`의 내용물을 모두 복사해도 된다.

### 2.2 실행 구조 확인

복사 후 실행 폴더는 다음 구조이다. `.venv`와 `week7-constraints.txt`는 1절에서 생성한 항목이다.

```text
~/week7/
├── .venv/
├── week7-constraints.txt
├── yolo_dataset_tool.py
├── yolo_finetune.py
├── yolo_pose_live.py
├── yolo11n-pose.pt
├── requirements-training.txt
└── week07_vision_control/
    ├── config/
    │   └── vision.yaml
    ├── launch/
    │   └── object_detection.launch.py
    ├── models/
    │   └── README.md
    ├── resource/
    │   └── week07_vision_control
    ├── week07_vision_control/
    │   ├── __init__.py
    │   ├── vision_common.py
    │   ├── top_camera_publisher.py
    │   └── yolo_object_detector.py
    ├── setup.py
    ├── setup.cfg
    └── package.xml
```

ROS 2 등록 파일과 `__init__.py`도 포함되어 있으므로 폴더 구조 그대로 사용한다.
학습 데이터와 팀별 학습 모델은 실습을 진행하면서 생성된다.

```bash
python3 yolo_dataset_tool.py --help
python3 yolo_finetune.py --help
python3 yolo_pose_live.py --help
```

세 도구의 옵션 목록이 출력되어야 한다. 학습이 끝나면 8절에서 패키지를 빌드한다.

---

## 3. 큐브 색과 tip 기준 설정

`week07_vision_control/config/vision.yaml`의 description을 촬영 전에 수정한다.
이름·순서는 기본값을 유지하고 실제 팀의 색과 물리적 기준점을 기록한다.

```yaml
classes:
  - name: cube1
    point_mode: box_center
    description: "초록색 큐브 전체 Box 중심"
  - name: cube2
    point_mode: box_center
    description: "파란색 큐브 전체 Box 중심"
  - name: tip
    point_mode: manual
    description: "팀이 정한 도구 끝의 원형 마커 중심"
```

색과 tip 위치는 예시이므로 실제 장비에 맞게 정한다.
큐브는 전체 Box를 그리고 중심점을 자동 생성한다.
tip은 구별에 필요한 주변 도구 영역을 Box로 그리고, 같은 물리적 점을 클릭한다.
그리퍼 중앙과 움직이는 날 끝을 이미지마다 바꾸어 지정하지 않는다.

---

## 4. 촬영과 라벨링

### 4.1 수집 실행

```bash
python3 yolo_dataset_tool.py
```

1920×1080 원본을 표시하는 전체 화면이 열려야 한다.
두 큐브와 tip의 실제 모양이 보이는지 확인한다.
모니터 비율 때문에 생긴 검정 여백은 저장 영상에 포함하지 않는다.
CSI 번호가 다르면 확인한 번호로 `--sensor-id 1`을 지정한다.
USB 카메라는 `--source 0`을 사용할 수 있다.
장치를 사용하는 다른 프로그램과 동시에 실행하지 않는다.

### 4.2 한 이미지의 정답 작성

1. Space로 현재 영상을 고정한다.
2. cube1 전체 Box를 드래그하고 Space로 확정한다.
3. cube2 전체 Box를 드래그하고 Space로 확정한다.
4. tip 주변 Box를 드래그하고 Space로 확정한다.
5. 정한 tip을 클릭하고 Space를 눌러 저장한다.

`Saved: frame_...jpg`가 출력되고 실시간 화면으로 돌아와야 한다.
큐브 중심은 따로 클릭하지 않는다. 고정된 이미지에 나타난 위치를 기준으로 라벨링한다.

| 키 | 실시간 화면 | 라벨링 화면 |
|---|---|---|
| Space | 영상 고정·라벨링 시작 | 현재 단계 확정, 마지막 단계에서 저장 |
| N | 동작 없음 | Box: 객체 제외 / 점: 위치 미상 |
| Backspace | 동작 없음 | 이전 입력 단계 |
| R | 동작 없음 | 현재 단계 초기화 |
| U | 최근 저장 이미지·라벨 삭제 | 동작 없음 |
| Q / Esc | 수집 종료·분할 | 현재 촬영 취소 후 실시간 복귀 |

U로 삭제한 촬영은 복구하지 못한다.
tip이 없으면 Box 단계에서 N을 눌러 점 입력도 건너뛴다.
도구는 보이지만 점 위치를 알 수 없으면 점 단계에서 N을 누른다.
모든 객체를 제외하면 빈 라벨의 배경 이미지로 저장한다.

### 4.3 다양한 조건 촬영

위치, 방향, 그리퍼 상태, 조명과 배경을 바꾸어 촬영한다.
부분 가림, 일부 객체가 없는 장면과 빈 작업판도 포함한다.
같은 장면을 반복 촬영한 수량만으로 데이터가 충분하다고 판단하지 않는다.
한 이미지에는 클래스당 객체 하나를 지정한다.

최소 두 장이면 분할할 수 있지만 학습에 충분하다는 뜻은 아니다.
세 클래스와 다양한 상태가 Train과 Validation에 포함되는지 확인한다.
Q 또는 Esc로 정상 종료하면 다음 형식이 출력되어야 한다.

```text
Dataset: .../datasets/week7/dataset.yaml | train=..., val=...
```

---

## 5. 데이터 분할

데이터 수집과 라벨링이 끝났으면 아래 명령으로 저장된 전체 데이터를 학습용과 검증용으로 분할한다.
기본 비율은 학습용 약 80%, 검증용 약 20%이며 원본 이미지와 라벨은 유지된다.

```bash
python3 yolo_dataset_tool.py --prepare-only
```

다음처럼 학습·검증 데이터 개수가 출력되면 6절의 학습으로 넘어간다.
두 개수 모두 1 이상이어야 한다.

```text
Dataset: .../datasets/week7/dataset.yaml | train=..., val=...
```

촬영을 Q 또는 Esc로 정상 종료했을 때도 자동 분할된다.
데이터를 추가 수집하거나 라벨을 수정했다면 위 명령을 다시 실행한다.

---

## 6. Jetson GPU 파인튜닝

### 6.1 1 Epoch 환경 확인

카메라·실시간 추론을 종료한 뒤 실행한다.

```bash
python3 yolo_finetune.py --epochs 1 --name environment_check
```

CUDA 장치, 학습 진행과 검증 결과가 출력되어야 한다.
기본 설정은 CUDA를 사용할 수 없으면 오류를 알리며 CPU로 자동 전환하지 않는다.
시험 학습은 환경 확인용이며 충분히 학습한 모델이라는 뜻이 아니다.

학습이 끝나면 Best checkpoint와 Installed model 경로가 출력되어야 한다.
실제 Trainer의 best.pt를 기본 모델 위치로 복사한다.

### 6.2 본 학습

```bash
python3 yolo_finetune.py --name week7_pose
```

GPU 0, 최대 100 Epoch, Batch 4, Patience 20, Workers 2, imgsz 640, AMP OFF를 사용한다.
검증 성능이 개선되지 않으면 일찍 끝날 수 있다.
이미 같은 실행 이름이 있으면 번호가 붙은 새 실행 폴더가 만들어질 수 있다.

GPU 메모리가 부족하면 다른 작업을 종료하고 다음과 같이 줄여 실행한다.

```bash
python3 yolo_finetune.py --name week7_small --batch 2 --workers 0
```

학습 대기 중에는 raw 라벨, 클래스별 데이터와 촬영 조건을 검토한다.
메모리를 추가로 사용하는 실시간 추론·ROS 검출은 학습 종료 후 실행한다.
수업 시간 안에 끝나지 않더라도 터미널을 유지하고, 학습 완료 후 남은 검사를 수행한다.

### 6.3 결과 파일

```bash
ls -l week07_vision_control/models/vision_pose_best.pt
cat week07_vision_control/models/vision_pose_best.vision.json
```

최적 모델의 사본과 클래스·점 기준·영상 크기 기록이 있어야 한다.
두 파일은 한 쌍으로 보관한다. 학습 시작용 yolo11n-pose.pt와 혼동하지 않는다.
runs에는 로그·그래프와 weights/best.pt, last.pt 등이 남는다.
본 학습 후 기본 모델은 본 학습 결과로 갱신되며 과거 실행 결과가 자동 삭제되지는 않는다.

---

## 7. 새로운 장면에서 결과 확인 및 조교 검사

```bash
python3 yolo_pose_live.py
```

Box와 십자점이 화면에, 클래스별 좌표와 FPS가 터미널에 표시되어야 한다.
좌표는 640×480 기준이다. 큐브는 검출 Box 중심, tip은 예측 Keypoint를 표시한다.
화면에서 크게 보인다고 출력 좌표계가 바뀌지는 않는다.

조교에게 이 화면을 보여주고 cube1·cube2의 Box와 중심점, tip의 Box와 기준점이
실제 대상에 맞게 표시되는지 검사받는다. 물체를 움직였을 때 검출 위치도 따라가는지 확인한다.

학습에 사용하지 않은 새 장면을 만들고 다음 조건을 검사한다.

| 조건 | 확인 내용 |
|---|---|
| 중앙 | 세 클래스와 점이 실제 대상과 일치하는가 |
| 가장자리 | 위치를 옮겨도 같은 대상과 점을 찾는가 |
| 부분 가림 | 보이지 않는 객체를 엉뚱하게 찾거나 점이 다른 곳으로 튀는가 |
| 조명 변화 | 색을 혼동하거나 검출이 끊기는가 |
| 빈 작업판 | 없는 객체를 반복해서 검출하는가 |

Box가 맞아도 tip이 다른 부위를 가리키면 성공으로 기록하지 않는다.
실패 장면과 실제 관측 결과를 기록한다.

선택적으로 같은 장면에서 임계값만 바꾸어 비교할 수 있다.

```bash
python3 yolo_pose_live.py --confidence 0.45 --keypoint-confidence 0.45
```

Confidence는 정확도 백분율이 아니다.
임계값을 낮추어 틀린 결과를 통과시키는 것으로 학습 문제를 해결했다고 판단하지 않는다.
Q 또는 Esc로 종료하고 카메라가 해제된 뒤 ROS 확인으로 넘어간다.

---

## 8. ROS 2 검출 결과를 터미널에서 확인

### 8.1 빌드

제공한 Publisher·Subscriber·Launch와 패키지 설정을 그대로 사용한다.
코드 빈칸이나 등록 함수를 작성하는 과제는 없다.

```bash
cd "$WEEK7_DIR"
source ~/ros2_base/install/setup.bash
source ~/week7/.venv/bin/activate
colcon build --base-paths week07_vision_control \
  --symlink-install --packages-select week07_vision_control
source install/setup.bash
ros2 pkg executables week07_vision_control
```

`1 package finished`와 두 실행 파일이 출력되어야 한다.

```text
week07_vision_control top_camera_publisher
week07_vision_control yolo_object_detector
```

학습 모델과 .vision.json이 models 안에 있는 상태에서 빌드한다.
설정·모델·Launch를 변경한 뒤에는 다시 빌드하고 setup을 적용한다.

### 8.2 Launch 실행

가상환경을 활성화한 터미널에서 실행한다.

```bash
ros2 launch week07_vision_control object_detection.launch.py \
  python_executable:="$(command -v python3)"
```

Camera에서 /top_cam과 640×480 영상 발행 로그가, Detector에서
YOLO classes와 검출 목록이 출력되어야 한다.
Launch 터미널에서 약 2초마다 `Detected: cube1, cube2, tip`처럼
현재 검출한 클래스가 계속 출력되는지 확인한다. 아무것도 검출하지 못하면 `Detected: none`이 출력된다.
단독 수집·모니터링과 동시에 카메라를 열지 않는다.
지정한 Python은 준비된 가상환경의 실행 파일이며 ROS 모듈도 사용할 수 있어야 한다.

### 8.3 터미널에서 검출 결과 연속 확인

다른 터미널에서 ROS 환경과 가상환경을 적용한다.

```bash
source ~/ros2_base/install/setup.bash
cd ~/week7
source ~/week7/.venv/bin/activate
source install/setup.bash
ros2 node list
ros2 topic info /top_cam --verbose
```

top_camera_publisher와 yolo_object_detector 두 노드가 보여야 한다.
Image Publisher와 Subscriber가 연결되는지 확인한 뒤, 다음 명령으로 검출 여부를 계속 확인한다.

```bash
ros2 topic echo /vision/tip/detected
```

tip이 보이면 `data: true`가 반복 출력되어야 한다.
Ctrl+C로 조회를 종료한 뒤, 다음 명령으로 큐브 좌표도 확인한다.

```bash
ros2 topic echo /vision/cube1/pixel
```

큐브를 움직였을 때 x·y가 바뀌어 출력되는지 확인한다.
`cube1`을 `cube2` 또는 `tip`으로 바꾸면 해당 대상의 좌표를 확인할 수 있다.
좌표는 640×480 기준이며 z=0은 깊이를 측정했다는 뜻이 아니다.
좌표가 출력되지 않으면 Ctrl+C로 조회를 종료하고 해당 대상의 detected와 Launch 로그를 확인한다.
확인이 끝나면 Ctrl+C로 조회만 종료하고 Launch는 계속 실행한다.

### 8.4 미검출 확인

tip을 촬영 영역 밖으로 이동하거나 가린 뒤 확인한다.

```bash
ros2 topic echo /vision/tip/detected
```

유효한 점이 없으면 false가 출력되어야 한다.
그동안 tip의 pixel과 bbox는 새로 발행하지 않고 confidence는 0이다.
마지막 pixel을 현재 위치로 계속 사용하지 않는다.
입력 영상 자체가 끊기면 false 메시지도 오지 않을 수 있으므로
이후 제어에서는 검출 여부와 새 메시지 시각을 함께 검사한다.

---

## 9. 종료와 문제 해결

Launch에서 Ctrl+C로 종료하고 카메라 프로세스가 끝났는지 확인한다.
학습 중인 작업은 결과가 저장되기 전에 임의 종료하지 않는다.
raw 데이터·학습 모델·runs는 실습 결과이므로 임시 파일처럼 삭제하지 않는다.

| 현상 | 확인할 내용 |
|---|---|
| CUDA False / torchvision 오류 | 준비된 GPU 환경과 Jetson용 라이브러리를 조교와 확인한다. |
| GStreamer NO / 카메라 열기 실패 | OpenCV, CSI 연결, sensor-id와 다른 프로세스 점유를 확인한다. |
| GUI가 열리지 않음 | GUI 세션·DISPLAY와 OpenCV GUI를 확인한다. |
| rclpy / cv_bridge 오류 | ROS setup과 가상환경의 시스템 모듈·NumPy 호환성을 확인한다. |
| vision_common import 실패 | 세 도구와 공통 모듈을 2절의 서로 다른 위치에 배치했는지 확인한다. |
| 이미지·라벨 쌍 누락 | raw의 같은 이름 파일을 복구한 뒤 분할한다. |
| 설정 기록 불일치 | 촬영 당시 이름·순서·description·점 기준·크기를 확인한다. 새 기준이면 별도 경로를 사용한다. |
| Dataset YAML 경로 불일치 | 대응 설정으로 --prepare-only를 실행한다. |
| Pose·Keypoint 수 불일치 | 시작 가중치와 학습 모델이 Pose 모델인지 확인한다. |
| GPU 메모리 부족 | 다른 작업을 종료하고 batch·workers를 줄인다. |
| Package / 실행 파일 / Launch 없음 | source_code 전체 복사와 폴더 구조, 재빌드, install/setup 적용을 확인한다. |
| 학습 모델 없음 | 본 학습 완료와 .pt·.vision.json의 배치를 확인한다. |
| 영상 수신 없음 | 카메라 노드의 영상 발행과 제공된 Sensor Data QoS를 확인한다. |
| 엉뚱한 점·종류 출력 | 라벨 기준과 데이터 다양성을 확인한다. 임계값만 낮추지 않는다. |

---

## 11. 실습 완료 체크리스트

- [ ] 이번 실습이 지도학습인 이유와 학습·추론의 차이를 설명한다.
- [ ] 완성 코드와 패키지 설정을 실행 위치에 배치한다.
- [ ] 큐브 색과 tip 기준을 촬영 전에 기록하고 일관되게 라벨링한다.
- [ ] 이미지·라벨 쌍과 Train/Validation 구성을 확인한다.
- [ ] CUDA 환경에서 시험·본 학습을 완료한다.
- [ ] vision_pose_best.pt와 대응하는 .vision.json을 확인한다.
- [ ] 중앙·가장자리·가림·조명 변화·빈 작업판을 확인한다.
- [ ] YOLO 실시간 화면의 Box와 기준점 검출 결과를 조교에게 검사받는다.
- [ ] 실제 실패 사례 두 개와 보완할 촬영 조건을 기록한다.
- [ ] 패키지를 빌드하고 완성 Launch를 실행한다.
- [ ] 터미널에서 검출 로그·pixel·detected가 계속 출력되고 미검출 시 false가 되는지 확인한다.
- [ ] 카메라·추론을 종료하고 데이터와 학습 결과를 보관한다.

---

## 12. 부록: 텀프로젝트 설정 확장

### 12.1 경로와 주요 옵션

세 도구는 `--config 설정파일`을 지원한다.

| 도구 | 주요 옵션 |
|---|---|
| 수집 | --dataset-dir, --source csi/0/영상파일, --sensor-id, --prepare-only |
| 학습 | --data, --weights, --name, --epochs, --batch, --workers, --device, --amp/--no-amp |
| 모니터 | --model, --source, --sensor-id, --device, --confidence, --keypoint-confidence |

설정 안의 상대 경로는 세 도구가 있는 ~/week7 기준이다.
--config 파일 위치를 바꾸어도 이 기준은 같다.
CLI에서 상대 경로를 직접 지정하면 현재 터미널 위치가 기준이다.
다른 장치로 옮긴 데이터는 대응 설정의 --prepare-only로 경로를 갱신한다.

### 12.2 클래스 추가 예시

```bash
cd ~/week7
cp week07_vision_control/config/vision.yaml project.yaml
```

project.yaml의 classes 목록 끝에 다음 항목을 추가한다.

```yaml
  - name: tool_marker
    point_mode: manual
    description: "도구 손잡이에 부착한 원형 마커 중심"
```

기존 세 클래스의 색과 tip description은 실제 팀 기준을 유지한다.
이름은 소문자로 시작하는 소문자·숫자·_ 조합이며 중복할 수 없다.
목록 순서가 ID이므로 새 클래스의 ID는 3이다.
box_center는 Box 한 단계, manual은 Box·점 두 단계가 추가된다.

같은 설정 파일의 paths를 다음처럼 변경하고 다른 설정은 유지한다.

```yaml
paths:
  dataset: datasets/team_project
  weights: yolo11n-pose.pt
  runs: runs
  model: week07_vision_control/models/team_project.pt
```

```bash
python3 yolo_dataset_tool.py --config project.yaml
python3 yolo_finetune.py --config project.yaml --name team_project
python3 yolo_pose_live.py --config project.yaml
```

수집 단계와 결과가 네 클래스로 늘어나야 한다.
클래스 이름·순서·점 기준·description·영상 크기를 바꾸면 새 데이터셋과 모델을 사용한다.
기존 자료를 재사용하려면 사본의 라벨을 새 기준에 맞게 재검토·재라벨링해야 한다.

빌드·setup 적용 후 ROS에도 같은 설정과 모델을 지정한다.

```bash
ros2 launch week07_vision_control object_detection.launch.py \
  python_executable:="$(command -v python3)" \
  config_path:="$WEEK7_DIR/project.yaml" \
  model_path:="$WEEK7_DIR/week07_vision_control/models/team_project.pt"
```

/vision/tool_marker/pixel, detected, confidence, bbox가 추가되어야 한다.
이 확장은 기본 실습의 필수 완료 조건이 아니다.

---
