#!/bin/bash

TARGET_FILE="$HOME/ros2_base/install/setup.bash"

if [ -f "$TARGET_FILE" ]; then
    # 원래 백업본 생성 (만약을 대비해 setup.bash.bak 파일이 만들어집니다)
    cp "$TARGET_FILE" "${TARGET_FILE}.bak"
    
    # soda/ros_ws 설정 부분과 바로 아래의 source 실행문까지 주석 처리
    sed -i '/COLCON_CURRENT_PREFIX="\/home\/soda\/ros_ws\/install"/{N; s/^/#/; s/\n/\n#/}' "$TARGET_FILE"
    
    echo "✅ setup.bash 수정 완료! (백업 파일 생성됨: setup.bash.bak)"
else
    echo "❌ 파일을 찾을 수 없습니다: $TARGET_FILE"
fi

