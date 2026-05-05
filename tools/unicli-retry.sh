#!/usr/bin/env bash
# unicli-retry: ドメインリロード中の一時切断をリトライで吸収するラッパー
# 使い方: ./tools/unicli-retry.sh exec Compile --json
#
# PlayMode遷移時にUniCliサーバーが一時停止するため、
# 接続失敗時に最大5回リトライする（各2秒間隔）。

MAX_RETRIES=5
RETRY_DELAY=2

for i in $(seq 1 $MAX_RETRIES); do
    output=$(unicli "$@" 2>&1)
    exit_code=$?

    # 成功、またはサーバー接続以外のエラー
    if [ $exit_code -eq 0 ]; then
        echo "$output"
        exit 0
    fi

    # "Server is busy" or connection error → リトライ
    if echo "$output" | grep -qE "Server is busy|not running|not responding|connection refused|pipe"; then
        if [ $i -lt $MAX_RETRIES ]; then
            echo "[unicli-retry] サーバー未応答、リトライ $i/$MAX_RETRIES (${RETRY_DELAY}s後)..." >&2
            sleep $RETRY_DELAY
            continue
        fi
    fi

    # リトライ不要なエラー、またはリトライ上限
    echo "$output"
    exit $exit_code
done

echo "$output"
exit 1
