#!/bin/bash
# Start the full stack locally (no docker in this sandbox):
# PostgreSQL 16 (portable binaries) + mini-redis + uvicorn + worker.
set -e
PG=/tmp/pgsrv/postgresql-16.16.0-aarch64-unknown-linux-gnu
export DATABASE_URL='postgresql+psycopg2://app:local_demo_4101@127.0.0.1:15432/query_review'
export REDIS_URL='redis://127.0.0.1:16379/0'
export JWT_SECRET='local-test-secret-gb4101'
export SEED_DEMO=true
mkdir -p /tmp/artifacts
$PG/bin/pg_ctl -D /tmp/pgdata -l /tmp/pg.log -o "-p 15432 -k /tmp -c listen_addresses=127.0.0.1" -w start 2>&1 | tail -1 || true
python3 /workspace/test-artifacts/gb-4101/mini_redis.py > /tmp/mini_redis.log 2>&1 &
echo $! > /tmp/mini_redis.pid
cd /workspace/backend
python3 -m uvicorn src.main:app --host 127.0.0.1 --port 8000 > /tmp/uvicorn.log 2>&1 &
echo $! > /tmp/uvicorn.pid
python3 /workspace/test-artifacts/gb-4101/worker_launcher.py > /tmp/worker.log 2>&1 &
echo $! > /tmp/worker.pid
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then echo "STACK READY"; exit 0; fi
  sleep 1
done
echo "STACK FAILED"; tail -20 /tmp/uvicorn.log; exit 1
