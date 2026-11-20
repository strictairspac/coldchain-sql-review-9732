# gb-4101 账单调号 · 测试工件

本目录是 gb-4101（运费账单号码成批调正）的测试脚本、日志与截图，按项目约定不放入源码目录。

## 内容

- `renumber_tests.py` — API/DB 实测：只读限制、参数校验、互换、链式腾出号、冲突退回、空号生效、并发争空号（只准一批生效）、并发无关批次（照常写）、落库后断线幂等重试、REPEATABLE READ 两侧同一版、旧证据保留原号码、审计留痕；结尾自动还原 600 条演示账单并全量比对。
- `ui_test.js` — Playwright 无头 Chromium 实测页面：登录、办理互换（整批生效）、办理冲突（整批退回并标出冲突号）、历史批次查明细、viewer 按钮禁用。
- `run_stack.sh` — 无 docker 环境下的本地栈：便携版 PostgreSQL 16 + `mini_redis.py`（仅实现 PING/RPUSH/BLPOP 等演示所需命令）+ uvicorn + `worker_launcher.py`（仅把 worker 的 /artifacts 重定向到 /tmp，逻辑不变）。
- `ui_server.py` — 静态前端 + /api 去前缀代理（对齐 frontend/nginx.conf 行为）。
- `results.log` — 最近一次完整实测输出（API 41 项 + UI 11 项，全部通过）。
- `ui-swap-applied.png` / `ui-conflict-rejected.png` / `ui-viewer-readonly.png` — 页面截图（沙箱浏览器缺中文字体，徽标文字显示为方框，属测试环境限制）。

## 复现

```bash
bash run_stack.sh                 # 启动本地栈（pg:15432 redis:16379 api:8000）
python3 renumber_tests.py         # API/DB 实测，结尾自动还原演示数据
python3 ui_server.py &            # 前端 :8080
node ui_test.js                   # 需 playwright-core 与 chromium 及系统库
```
