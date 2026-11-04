#!/usr/bin/env bash
# 在容器内用 beeline 执行一个 SQL 文件，输出存到 logs/<name>.log
# 用法：bash hr.sh <sql文件相对路径>
set -uo pipefail

C="hive-demo-hive-server-1"
BEELINE="/opt/hive/bin/beeline"
URL="jdbc:hive2://localhost:10000/default"
ROOT="C:/Users/DELL/Desktop/第二周"
SRC="$1"
NAME="$(basename "$SRC" .sql)"
OUT="$ROOT/logs/$NAME.log"

mkdir -p "$ROOT/logs"
MSYS_NO_PATHCONV=1 docker cp "$ROOT/$SRC" "$C:/tmp/run_$NAME.sql" >/dev/null 2>&1 || {
  echo "COPY FAIL $SRC"; exit 1; }

MSYS_NO_PATHCONV=1 docker exec "$C" "$BEELINE" \
  -u "$URL" \
  --hiveconf mapreduce.job.counters.max=2000 \
  --hiveconf mapreduce.job.counters.limit=2000 \
  --hiveconf tez.counters.max=2000 \
  --hiveconf tez.counters.max.groups=1000 \
  --hiveconf hive.exec.parallel=false \
  --silent=true --outputformat=tsv2 \
  --force=true \
  -f "/tmp/run_$NAME.sql" > "$OUT" 2>&1
RC=$?

# 过滤日志噪声
grep -vE "^(INFO|WARN|SLF4J|Beeline|Closing|Connecting|Connected|\[WARN\])" "$OUT" > "$OUT.clean" || true
echo "RC=$RC  -> $OUT"
grep -iE "^Error|FAILED|Exception|Error while" "$OUT.clean" | head -5
exit $RC
