# 5주차 구현 및 검증 기록

기준 문서는 `docs/practice.md`, `docs/lecture.md`, `docs/week5_ROS2_joint_control.pptx`다.
아래 로컬 검증은 실물 로봇 실습의 완료 판정을 대신하지 않는다.

## 요구사항 대응

| 실습 항목 | 구현 위치 | 검증 내용 |
|---|---|---|
| 4.1 `/joint_states`, JointState, depth 10 | `joint_controller.py` 생성자 | Publisher 타입·이름·depth, 측정값·시각 |
| 4.2 `/joint_targets`, `_on_target`, depth 1 | 같은 생성자 | 구독과 callback 연결 |
| 4.3 Bool `/safety/torque_enable`, depth 10 | 같은 생성자 | 구독·callback 연결, 요청만 저장 |
| 4.4 Soft Limit 전체 거부 | `_on_target` | 모든 관절의 양쪽 경계 허용, 범위 이탈·NaN·무한대 거부, 다중 요청 원자성 |
| 5 패키지 등록 | `setup.py`, `setup.cfg`, `package.xml`, resource | 두 실행 진입점·YAML·ament 식별 파일·실행 의존성 |
| 7 Controller 시작과 상태 발행 | `main`, `_read_and_publish_state` | 시작 OFF 및 20 Hz Timer 구성 |
| 8 토크 ON | `_apply_torque_request`, `FeetechBus` | 현재 자세 재측정, 목표 레지스터 검증 후 ON |
| 8 단일·다중 목표 | `_on_target`, `_control_step` | 부분 갱신, 다른 관절 목표 유지, 양방향 속도 제한, overshoot 없음 |
| 자세 유지 | `_control_step` | 명령 변화 없을 때 쓰기 생략, 10 Hz Heartbeat, 도달 로그 1회 |
| 9 요청값 시각화 | `joint_plotter.py` | 거부되는 3.5 rad도 원본 requested에 기록 |
| 10 토크 OFF·종료 | Controller, FeetechBus | 쓰기 중단, 초기화 실패 시 정리, OFF 실패 시 모든 ID 시도 |
| 10 CSV·PNG | Plotter | CSV 13열·전체 샘플, PNG 6개 축·마지막 30초, Ctrl+C·창 닫기 저장 |

`source_code/` 완성 파일과 배포 패키지의 파일이 일치하는지도 검사한다.

## 실행한 검증

- 테스트: `python -m unittest discover -s week5/tests -v`, **33개 통과**.
- 환경: Windows의 Python 3.12, PyYAML 6.0.3, Matplotlib 3.11.2(Agg),
  vassar-feetech-servo-sdk 1.5.0, pyserial 3.5.
- ROS Node·메시지·Executor는 테스트 대체 객체를 사용했다.
- 시리얼은 가상 케이블로 교체했지만 `scservo_sdk`의 패킷 생성·응답 해석은 실제 구현을 사용했다.
- 초기 goal 레지스터를 다른 값으로 설정한 상태에서 OFF·새 goal 기록·읽기 확인·ON 순서를 검증했다.
- 잘못된 goal readback, 일부 ON 실패, OFF 실패, SyncWrite 전송 실패를 주입했다.
- Plotter CSV는 가상 40초/801샘플의 데이터가 802행(헤더 포함), 13열로 저장되는지 확인했다.
- PNG의 실제 6개 그래프, current/requested 구분, 마지막 30초 표시를 열어 확인했다.
- Python wheel 빌드를 통해 설정·모듈·진입점의 설치 산출물을 만들었다.

의도적인 실패 주입 테스트에서는 `종료 중 토크 해제 실패: OFF failed` 메시지가 나올 수 있다.
실제 장치 오류 로그가 아니라 실패 처리 검증용 출력이다.

## 구현상 해석과 한계

1. `Target reached`는 제공 보간 로직대로 commanded와 target이 같아진 시점이다.
   실제 measured가 도달했는지는 별도 그래프에서 확인해야 한다.
2. 시간 간격 `dt = 1 / control_hz`는 제공 로직을 유지했다.
   OS·시리얼 지연까지 포함한 실제 물리 속도를 이 검사로 보장하지 않는다.
3. SyncWrite의 전송 성공은 전체 장치의 실행 완료를 뜻하지 않는다.
   토크 ON 전에는 별도 goal 레지스터 readback을 수행한다.
4. GUI는 로컬 검증에서 Agg로 저장했으며 Jetson의 실제 GUI·ROS 이벤트 처리는 현장 검증 대상이다.
5. `scservo_sdk`는 설정된 STS 위치 모드 0을 사용한다. 자동 phase·EEPROM 모드 변경을 하지 않는다.
6. 실제 가동 범위, 배선, 시리얼 권한, 토크 응답과 로봇 추종은 실습 장비에서 확인해야 한다.

## 재실행

저장소 최상위에서, ROS 대체 객체를 사용하는 소프트웨어 검증을 실행한다.
별도의 가상환경에서 필요한 테스트 패키지를 준비해도 된다. 실제 ROS 실행 환경은 변경하지 않는다.

```bash
python3 -m pip install PyYAML matplotlib 'vassar-feetech-servo-sdk==1.5.0'
MPLBACKEND=Agg python3 -m unittest discover -s week5/tests -v
```

시험 결과 이미지는 `week5/.test-build/plot-check/`에 저장한다.
실습용 `~/week5/results/`와 구분한다.
