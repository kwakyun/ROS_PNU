# Jetson Ubuntu에서 Week 6 디렉터리 구성하기

이 안내는 ROS 2가 설치되고 `rosdep`, `colcon`을 사용할 수 있는 Jetson Ubuntu 계정을 기준으로 한다. ROS 2 배포판 설정은 수업 환경에 맞춘다.

## 권장 홈 디렉터리

저장소에서 Week 6 자료를 가져온 뒤 다음 구조로 둔다.

```text
/home/<사용자>/week6/
├── src/
│   └── week06_ee_control/       # ROS 2 패키지
├── docs/                        # lecture.md, practice.md, 강의자료
└── README.md                    # 이 실습의 빠른 시작 메모(선택)
```

`src`가 colcon 작업공간의 소스 디렉터리이며, `build/`, `install/`, `log/`는 빌드할 때 자동 생성된다. 이 디렉터리들을 직접 만들 필요는 없다.

## 저장소에서 복사하는 경우

호스트 저장소를 Jetson에 clone한다. 아래 URL은 실제 저장소 주소로 바꾸고, SSH 키 또는 HTTPS 인증을 준비한다.

```bash
cd ~
git clone <저장소_URL> ROS_PNU
mkdir -p ~/week6/src
cp -a ~/ROS_PNU/week6/week06_ee_control ~/week6/src/
cp -a ~/ROS_PNU/week6/docs ~/week6/
cp ~/ROS_PNU/week6/JETSON_SETUP.md ~/week6/README.md
```

저장소 전체를 Jetson의 `~/ROS_PNU`에 이미 clone했다면 위 절차로 `~/week6`에 패키지와 문서를 구성한다. `week06_ee_control` 폴더가 `~/week6/src/` 바로 아래에 있어야 한다.

## ROS 2 환경 설정과 빌드

새 터미널마다 설치된 ROS 2 환경을 source한다. `humble`은 예시이므로 실제 설치판으로 바꾼다.

```bash
source /opt/ros/<배포판>/setup.bash
cd ~/week6
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install --packages-select week06_ee_control
source install/setup.bash
```

ROS_DOMAIN_ID는 팀에서 지정한 숫자를 사용한다. 모든 실습 터미널에서 같은 값을 사용해야 한다.

```bash
export ROS_DOMAIN_ID=<조_번호>
```

## 실행

먼저 실행 파일 목록을 확인한다.

```bash
ros2 pkg executables week06_ee_control
```

로봇과 게임패드가 연결된 상태에서, 안전 안내 및 토크 절차는 `docs/practice.md`를 따른다. 전체 노드를 실행하려면:

```bash
ros2 launch week06_ee_control joystick_arm_control.launch.py
```

게임패드 장치 ID가 0이 아니면 지정한다.

```bash
ros2 launch week06_ee_control joystick_arm_control.launch.py device_id:=1
```

Python 또는 설정 파일을 수정한 다음에는 `~/week6`에서 다시 빌드하고 환경을 source한다.

```bash
cd ~/week6
colcon build --symlink-install --packages-select week06_ee_control
source install/setup.bash
```

새 터미널을 열 때마다 ROS 2와 작업공간 환경을 source한다. 편의를 위해 `~/.bashrc`에 추가할 수 있다.

```bash
source /opt/ros/<배포판>/setup.bash
source ~/week6/install/setup.bash
export ROS_DOMAIN_ID=<조_번호>
```

## 주의

- `config/joints.yaml`의 `/dev/ttyACM0`, baudrate, 서보 ID와 방향이 실제 장비 설정과 일치하는지 확인한다.
- 장치 권한, 패키지 설치, udev 설정이 필요한 경우 임의로 관리자 명령을 실행하지 말고 담당 조교 지침을 따른다.
- 실습 종료 때 `/safety/torque_enable`에 `false`를 보내 토크 해제를 확인한 뒤 Launch를 종료한다. 상세 명령과 안전 절차는 `docs/practice.md`를 따른다.
