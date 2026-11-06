# Agent 学习 OS Web 版 — 项目说明（供 AI Agent 读取）

> 本文件是**给 AI Agent 看的项目基线**，每次进入本项目自动加载。
> 用途：项目介绍 + 当前进度 + 关键约定 + 断点。改代码前先读「当前进度与断点」，动手后更新「进度记录」。

## 🎯 项目是什么

面向「AI Agent / LLM 应用开发」岗位的个人学习管理系统。本地 Web 应用，全中文 UI，数据全部存本机 SQLite，无需联网即可运行（AI 复盘/助手/Agent 除外，需在「⚙️ 设置」页配置模型 API key）。

## 🧱 技术栈与架构

- **前端**：React 19 + Vite 6（`frontend/src`），构建产物 `frontend/dist`，由后端静态托管（单进程运行）
- **后端**：Python 3.10+ · FastAPI · uvicorn · SQLite（标准库 sqlite3）
- **零外部服务**：不依赖任何云端，数据不上传（AI 调用除外）
- **路由**：前端用 hash 路由（`#/reports` 等），刷新不丢页

### 目录结构

```
Agent学习OS_Web版/
├── 启动.bat                  # 一键启动（主入口，生产模式）
├── 启动-开发模式.bat          # 开发模式：后端热重载 + Vite dev server(5173)
├── 备份数据库.bat / 重新构建前端.bat
├── 预览新界面.html           # 各页首屏截图预览（自包含 base64）
├── CLAUDE.md                 # 本文件
├── backend/
│   ├── main.py               # FastAPI 入口：建库+播种+托管前端
│   ├── config.json           # 配置（provider + 各家 api_key/model；只存本机）
│   ├── data/                 # agent_study.db 数据库在此；server.log 启动日志
│   └── app/
│       ├── db.py             # 建表 + 迁移机制（版本号已到 v9）
│       ├── seed.py           # 种子数据（Excel 提取，首次启动自动播种）
│       ├── stats.py          # 准备度 / 连续天数 / 热力图 / 周月报聚合
│       ├── llm.py            # 多模型 LLM 统一入口（DeepSeek/GPT/Claude + 结构化输出 + ping）
│       └── routers/          # 各模块 API（reports/summaries/config/chat 等）
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # 侧边栏 + 页面切换（hash 路由）
│   │   ├── pages/            # 各页面组件
│   │   └── styles.css        # 设计系统
│   └── dist/                 # 构建产物（跑的就是它）
└── tools/                    # launch_hidden.py / stop_service.py / make_icon.ps1
```

## 🚀 启动方式（按推荐顺序）

1. **桌面图标「Agent学习OS」**：无黑窗独立应用窗口启动（`tools/launch_hidden.py`，pythonw 静默，日志 `backend/data/server.log`）；**停止服务在网页「⚙️ 设置 → 🔌 关闭服务」点一下**（`POST /api/shutdown`），桌面只有一个图标
2. **`启动.bat`**：一键启动（带浏览器标签页），黑窗方式，保留
3. **`启动-开发模式.bat`**：改代码时用（后端热重载 + 前端 5173 热刷新）；首次需先跑过 `启动.bat` 完成依赖安装

### 手动命令

```bash
# 后端（在项目根目录，用根目录 .venv，不是 backend/.venv）
.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000

# 前端开发服务器（frontend/ 下）
npm run dev
```

**改前端后必须 `npm run build`**，构建产物进 `frontend/dist` 才在 `启动.bat` / 桌面图标模式下生效。

## ⚠️ 关键约定（必须遵守）

1. **不要用 Tkinter**（用户明确禁止；UI 全走 React + 浏览器）
2. **诚实测试**：只报告真实执行的验证结果，不虚构断言通过
3. **模型 API key（DeepSeek/GPT/Claude）只存本机** `backend/config.json`：不进数据库、不被 `/api/backup` 导出、不上传；`GET /api/settings` 永不回传 key（只回 `has_key`/`has_keys` 布尔）
4. AI 复盘未配 key 时自动降级为「仅统计数据」（不能崩）
5. 中文 Windows 下 .bat 脚本按 **GBK** 编码保存；**勿用编辑器改成 UTF-8**
6. 数据库是单文件 `backend/data/agent_study.db`，删掉即重置（下次启动自动重播种）；备份到 `backups/`
7. 全局模型在「⚙️ 设置」页选（供应商 + 模型 + key），存 config.json 的 `provider` + `{provider}_model`/`{provider}_api_key`；三家默认 deepseek-chat / gpt-4o-mini / claude-sonnet-5；**Claude 无 json_object 原生模式**（结构化输出走提示词 + `_extract_json` 抽取兜底，失败如实上报）

## 📊 当前进度与断点（2026-11-01 交接更新，完整交接见 `交接提示词.md`）

### 已完成
- **学习路线重构（用户 4 需求，全部完成）**：
  1. **进度自动化**：迁移 v4（`tasks.spent_minutes`/`manual_progress` + 新表 `task_sessions` + 补 15 任务目标小时 + 课程→任务映射）；进度 = 累计分钟/(目标小时×60) 自动算，滑块=手动锁定（✋ 手动 / 🔄 自动 + 恢复自动）；计时器（<30秒不记录）+「＋记一笔」；自动同步当天打卡分类（`tasks.py` 的 `CATEGORY_FIELD_MAP`）
  2. **课程并入路线**：`courses.task_id`，路线任务展开显示配套课程（＋30分），缺课任务标「⚠️ 暂无配套课程·添加课程」；课程页显示归属任务 + 归属任务下拉
  3. **课程链接验证**：`tools/verify_courses.py`（B站官方 API 实测）→ 4 门低质课已换（黑马RAG+Agent 331.8万 / 李沐官方 74.4万 / 吃透AI全家桶 / MCP入门实战 2.4万 / 面试50题 1.4万），报告见根目录 `课程验证报告.md`，替换前备份在 `backups/`
  4. **阶段讲解+岗位要求**：`phase_guides.py` + `GET /api/phases`，6 阶段含讲解/岗位要求/真实来源链接（牛客 JD、CSDN 面经）
- **MVP**：总览 / 每日打卡 / 学习路线 / 算法 / 八股 / 课程 / 项目 / 全局搜索 8 页
- **第二阶段**：GitHub 风格学习热力图 + DeepSeek AI 周报/月报（reports 表缓存防重复花钱）+ 手写每日总结（按日期看历史）；hash 路由支持刷新
- **UI 全面美化**：深色渐变侧边栏 + 玻璃拟态卡片 + 翡翠绿渐变主按钮带光晕 + 毛玻璃吸顶顶栏 + 三层光晕背景 + 渐变进度条（21/21 computed-style 断言通过）
- **打开即最新（自动刷新）**：改完代码重建前端+重启后端后，已打开的窗口无需手动 F5 —— 后端 `GET /api/version`（dist/index.html 的 mtime+size 摘要，`no-store`）+ 静态托管 HTML 打 `Cache-Control: no-cache`（每次回源校验）、`/assets/*` 哈希资源打 `immutable` 长缓存；前端 App.jsx 版本探测器（窗口切前台/每 10s 查一次 version，变了 toast 后自动 `location.reload()`，hash 路由刷新不丢页；dev 模式跳过）
- **第 3 阶段 · AI 助手聊天**：导航新页「💬 AI 助手」，把学习数据摘要（准备度/本周本月统计/近14天打卡/最近总结/未完成任务）注入 system prompt + 最近 30 条对话历史，一次往返调 DeepSeek；聊天记录持久化到 `chat_messages` 表（迁移 v3）。`llm.py` 重构出多轮 `chat(messages, timeout)`（generate 内部调用，报告向后兼容）。**已修复 bug**：INSERT user 消息未 commit 导致丢失 → 已加 `conn.commit()`
- **桌面无黑窗启动**：`tools/launch_hidden.py` + 桌面 .lnk；打开方式为 Chrome/Edge 应用模式独立窗口；**关闭服务走网页「⚙️ 设置 → 🔌 关闭服务」→ `POST /api/shutdown`**（`app/shutdown.py` 守护线程延迟 0.8s `os._exit(0)`；有 Agent run 在跑时 409 不关）；`tools/stop_service.py` 保留为命令行备用；自绘图标 `assets/agentos.ico`（**v2 学习主题：📖打开书本+金色对勾+翡翠绿背景**，脚本 `tools/make_icon.ps1`；旧学士帽版备份在 `tools/make_icon_cap.ps1` 可回退）
- **第 4 阶段 · Agent 自主规划（最小闭环）**：导航新页「🤖 Agent」，Observe→Plan→Execute→Reflect 闭环真实跑通（迁移 v5：`agent_runs`+`agent_trace_events`；`backend/app/agent/` 包：registry/state/trace/repo/llm_provider/planner/executor/reflector/runtime + prompts/；5 个工具 4 读 1 写，唯一写工具 `create_task` 强制「待确认」人工门禁；Planner/Reflector 走 `response_format=json_object` 结构化输出，**非 function calling**，确定性核心（observe/execute/trace）与 LLM 边缘完全分离；`MAX_ITER=3` 硬上限 + 单运行锁 + 取消端点 + 崩溃残留恢复）。**单测 27 个全过**；**真实 DeepSeek 冒烟成功**（4 观察 + 6 工具调用 + 复盘 + 总结，5278 token / 7s，Planner 创建 2 条「待确认」任务）
- **阶段 2 · 把数据库变成 Agent 的真实 Environment**：注册表扩到 **11 工具 = 6 读 + 5 写**，用户示例 8 个工具全覆盖（get_task_list/get_courses/get_reports/add_session/update_task/complete_task/create_review_task + 原 4 读）；**写操作全部「全直接生效」**（create_task 去掉待确认门禁，属行为变更），由迁移 v6 `agent_actions` 审计表（run_id/tool/args/before/after/ok/error）+ `GET /api/agent/run/{id}/actions` 端点 + Agent 页「🧾 操作记录」块兜底（before→after 快照=回滚依据）；**services 层抽取**（`app/services/tasks.py`）为进度/打卡/时间不变量唯一来源，routers 与 agent 工具全部委托；权限模型扩 `Permission: READ/APPEND/MUTATE` + `ToolSpec.category` 分组进 Planner 提示词；`update_task` 的 `progress` 参数=手动锁定（映射 manual_progress，-1 恢复自动）；AgentContext 注入（写工具统一签名 `(args, ctx=None)`，失败也审计 ok=0）。**单测 53/53 全过**；**真实 DeepSeek 冒烟成功**（run 6b88c55：Planner 精准 add_session(算法,120min) + update_task(RAG,progress 50)，审计 2 行含 before→after，task_sessions/daily_logs/manual 锁定全同步）
- **阶段 3 · 真正的跨天闭环（Autonomous Agent）**：持久化「计划」实体（迁移 v7 `agent_plans` 一天一份 + `agent_plan_items` 关联任务）；`app/services/plans.py` 业务唯一来源（create_plan upsert 保 prev_plan_id 计划链 / get_plan 含实时实际分钟 / **compute_plan_vs_actual 确定性偏差不调 LLM**（阈值 20%：over/under/ok）/ submit_review **调整待确认不生效** / confirm_review 应用 adjust/remove/add/next_plan 每步 confirm:* 审计 / find_unreviewed）；**运行时反馈回路**（runtime.py 种子观察后确定性注入 prior_plan_vs_actual 到 observations，planner+reflector 都可见，无则零噪音 + trace plan_compare）；注册表 **11→15 工具**（+get_plan/get_plan_vs_actual 读、create_plan 写直接生效、submit_review 写待确认）；planner.txt 闭环规则（复盘调整禁止直接建/改任务）；路由 `GET /plans`、`POST /plan/{id}/confirm|reject`、`GET /reminder` + main.py lifespan `maybe_auto_review()` 半自动提醒；前端 Agent.jsx 提醒横幅 + 「📅 学习计划」区（状态徽章/expected vs actual 进度条/待确认调整/确认拒绝）+ plan_compare 分支。**单测 84/84 全过**；**真实 DeepSeek 冒烟全闭环成功**（安排昨天计划 120 分钟 → 补 40 实际 → 偏差 -67% over → 复盘 pending（adjust+remove×2）→ confirm 应用 + 3 条 confirm:* 审计 → 提醒消失；临时 DB 未污染真实库）
- **阶段 4 · 长期记忆（结构化 Memory，已跑通）**：给 Agent 装**结构化长期记忆**（第一版直接 SQLite，**不向量库、不为 RAG 而 RAG**）。用户已确认：**记忆写入=先待确认再生效**（像 Phase 3 复盘调整）+ 计划项加可选「建议时段」字段。交付物：
  - 迁移 v8：`agent_memories` 表（mkey UNIQUE 同主题覆盖更新 / mtype preference·fact·goal·rule / content / keywords / importance 1-5 / status pending·active·rejected·forgotten / source_run_id）+ `agent_plan_items.suggested_time` 列
  - `app/services/memories.py` 业务唯一来源：remember（按 mkey upsert 待确认）/ get_memories（pending 在前 importance 降序）/ **active_memories（仅 active 供注入，限 20 条防烧 token）** / confirm_memory（pending→active）/ reject_memory / forget_memory（软删留痕）
  - services/plans.py + plan_tools：**suggested_time 贯通**（create_plan 清洗落库 / get_plan 带回 / _compact_plan 快照）
  - 注册表 **15→18 工具**（category「记忆」）：get_memories（读）/ remember（写，**待确认** + 审计）/ forget_memory（写，软删 + 审计）；**registry 补强**：参数校验失败（args_handler）也写一条 ok=0 审计（写工具），让「Agent 试过但被拒」可见
  - **运行时注入**：runtime.py 种子观察后 `_inject_memories` 把已确认记忆写 `observations["user_memories"]`（planner+reflector+synthesizer 三方自动消费）+ trace `user_memories`；无记忆零噪音
  - 提示词：planner.txt 规则 13-15（**遵守记忆：重任务放高效时段 + items 带 suggested_time；用户明确要求才 remember 且待确认；get_memories/forget_memory**）、synthesizer.txt 规则 5
  - 路由：`GET /memories`、`POST /memories/{id}/confirm|reject`、`DELETE /memories/{id}`（确认/拒绝/删除=用户面板操作，不写 agent_actions）
  - 前端 Agent.jsx：「🧠 已记住的记忆」面板（type 徽章/status 徽章/importance★/pending 显示确认·拒绝、active 显示删除）+ 计划卡 `⏰ 建议时段` 徽章 + `user_memories` trace 分支；styles.css `.memory-*` 族 + `.plan-slot`
  - **验证**：**117/117 单测全过**（+33 = 记忆服务 20 + 记忆工具 9 + 闭环集成 4，含 registry 审计补强的回归）；**真实 DeepSeek 冒烟 ALL PASS**（temp DB 8001：run1「记住偏好」→ remember pending + confirm 端点生效 → run2「安排明天的学习」→ planner **真把 3 项任务排进 20:00-23:00 高效时段**、`suggested_time` 3/3、注入事件 count=1；临时库不污染真实库）
- **Phase 5 · Agent Trace 回放视图（已完成）**：独立「📜 Trace」页（导航新页），一屏把一次 Agent 运行回放成可截图、可面试讲解的时间轴。**Agent 运行逻辑零改动**：
  - 后端最小改动（向后兼容）：`RunRepo.list` SELECT 加 `id` 列 + `GET /run/{id}` 返回 `id`（agent_runs AUTOINCREMENT 数字主键 → `#编号` 式 Run 编号）
  - `frontend/src/pages/Trace.jsx`（新）：左侧运行历史（#id + goal + 状态点 + 时间，最新在前，点击切换）、右侧 `Agent Run #id` + 状态徽章 + 🎯 goal + 4 统计卡（耗时/token/迭代/工具调用数）+ 按类型着色的可折叠时间轴；`#/trace` 直达可刷新；运行中每 2s 轮询实时更新
  - 时间轴 9 类事件着色（🔭观察💭规划🛠️工具📊计划对比🧠记忆🔄复盘🔁重规划⚠️错误🏁Finish）；**tool_call+tool_result 合并一行**（executor 总是成对写，工具数=行数）；`<details>` 原生折叠展开规划推理/工具参数+结果/复盘 4 字段；**底部合成 Finish 行**（trace 无 finish 事件，由 status+finished_at 得出）
  - App.jsx 4 处注册（import/NAV/PAGE_TITLES/渲染）；styles.css `.trace-*` 类族 + 9 个 `.t-*` 变体（复用设计 token 与 .card/.run-list/.stat-chip 等类）；**无新依赖**（纯 hash 路由、无 markdown 库）
  - **验证**：117/117 单测全过；`npm run build` 成功；进程内冒烟确认 `/runs` 与 `/run/{id}` 均返回数字 id + 9 类事件形状正确；8000 后端已重启（实测 `/api/agent/runs` 返回 id:2/id:1 + 新版本号触发自动刷新）
- **Phase 6 · 多模型（DeepSeek / GPT / Claude 供应商抽象，已完成）**：llm.py 从「单 DeepSeek」重构成**三家统一入口**。全站只设一个全局模型（用户已确认：不做按任务路由、不要 OpenAI-compatible 自定义供应商）：
  - `backend/app/llm.py`：`Provider` 类封装三家差异（请求 URL/Header/payload/响应解析/token 提取）+ `PROVIDERS` 注册表；**统一 `_http_post`** 合并原 llm.py 与 AgentLLM._post 两套 urllib（错误映射 401/402/429/URLError/TimeoutError 原样保留）；公开 API 签名向后兼容（chat/generate 不变 + 新增 chat_with_usage/structured_json/ping）；`_extract_json` 三家共用兜底；**Claude 分支**：system 置顶层、max_tokens 必填（自由 2048/结构化 4096/ping 8）、相邻同 role 合并、无 json_object 走「强提示+抽取+重试 1 次」（**已知限制，如实标注**）
  - **config.json 新键**：`provider` + 三家 `{provider}_model`/`{provider}_api_key`/`{provider}_base_url`；旧 `deepseek_*` 零迁移兼容（provider 缺省回退 deepseek）；**`save_config` 改为合并当前文件内容**（`{**DEFAULTS, **load_config(), **非空cfg}`）——否则切供应商会把已存 key 冲掉（本 Phase 审出并修的真 bug）
  - `agent/llm_provider.py`（AgentLLM）：委托 llm.py 删掉 `_post`/`_model`/urllib；`__init__` 即读 `llm.active_model()`（**修复 agent_runs.model 存空串 bug**，runtime.py 建行前 model 就正确）；token 累计现含 planner+reflector+synthesizer 全路径
  - 新 `routers/settings.py`：`GET/PUT /api/settings` + `POST /api/settings/test`（**永不回传 key**，test 用表单当前值不落库）；`GET /api/config` 增量加 provider/model
  - 前端「⚙️ 设置」页（`pages/Settings.jsx`）：三 `.tab-btn` 切换 + datalist 模型 + password key（显示切换）+「测试连接」（复用 Reports loading/失败态）+ 保存；Chat/Agent 未配置横幅跳 `#/reports`→`#/settings` 且文案改通用；**Reports 内联 DeepSeek key 表单收敛为「去设置」横幅**（删 apiKey/saveKey/PUT /config 调用，端点保留向后兼容）
  - **验证**：148/148 单测全过（117 原有 + 新增 llm 配置 9 / HTTP 15 / provider 6）；`npm run build` 成功（47 模块）；temp DB 8001 HTTP 冒烟 **8/8 PASS**（含 **真实 DeepSeek key 测试连接 ok:true** + 切 openai 后旧 deepseek key 保留 + anthropic 无 key 不泄漏 + config.json 结束恢复）

- **Phase 7 · 意图识别 + 对话管理 + Agent 评测 + 成本看板（已完成，按 JD 补齐）**：起因是用户要求按 Boss 直聘 AI Agent 岗位 JD 优化项目，用户从 4 个候选里**只勾选了「评测 + 成本看板」和「意图识别 + 对话管理」两项**（明确没选 MCP 和多智能体协作）。交付物：
  - **迁移 v9**：`agent_conversations`（conv_id 唯一 / status / pending_json 挂起槽位）+ `agent_conversation_turns`（role / content / intent_json / run_id）+ 索引；`agent_eval_cases`（name 唯一 / kind / goal / available_time / expect_json / enabled）+ `agent_eval_runs`（eval_id / status / total / passed / failed / total_tokens / cost_cny）+ `agent_eval_results`（eval_id / case_id / passed / detail_json）+ 索引；`ALTER TABLE agent_runs ADD COLUMN intent TEXT NOT NULL DEFAULT ''`
  - **`backend/app/agent/intent.py`（意图识别，纯规则零成本）**：7 类意图 plan/review/record/remember/forget/query/chat + `SLOT_SCHEMA`（plan 必填 date、record 必填 minutes 等）+ `_RULES` 顺序（forget 0.95 → remember 0.95 → review 0.9 → record 0.85 → plan 0.85 → query 0.8）+ `extract_date`（相对词按**词长倒序**匹配，否则「大后天」被「后天」先吃）/`extract_minutes`/`extract_task_ref`/`classify`/`merge_pending`/`next_question`/`build_goal`/`describe`。**为什么用规则不用 LLM**：每轮输入都过一次 LLM 是纯开销（用户每敲几个字就一次请求），7 类意图边界清晰、规则可解释可单测
  - **`backend/app/agent/eval_cases.py` + `eval_runner.py`（评测执行）**：19 条用例（意图 14 / 多轮 3 / 真实运行 2），`expect_json` 支持 `$today/$tomorrow/$yesterday/$next_monday` 相对日期占位（**任何一天跑都成立**）；`run_eval(kinds=("intent","dialog"))` 默认只跑零成本用例（run 类延迟 import AgentRuntime，不拉起 LLM），单条用例异常不毁整轮
  - **`backend/app/services/conversations.py`（多轮对话持久化）**：挂起槽位**落库而不是放内存**（Web 版会刷新页面、后端会重启，内存状态一丢用户就得重说一遍）
  - **`backend/app/agent/cost.py` + `services/usage.py`（成本核算）**：`PRICING` 前缀价目表（13 条，元/百万 token，**顺序有意义**——`deepseek-reasoner` 要在 `deepseek` 之前）+ `estimate_cost`/`usage_summary`；`usage.summary(days)` 返回 totals/by_day/by_model/by_intent/recent。**诚实设计**：token 是 API 真值、单价是常量、未收录模型 `price_known=False`；早期 run 只有 `total_tokens` 没有输入输出分项时 `detail_available=False` 且**不瞎拆**，计入 `legacy_runs`
  - **`llm.py` 用量明细**：`Provider.extract_usage()` 三家各自取 input/output；新增 `chat_with_detail()`/`structured_json_detail()`（`structured_json` 签名与返回值**保持不变**，向后兼容）；`_structured_json_detail` 在重试循环里**累加** token，不丢账
  - **`agent/llm_provider.py` 重写**：`AgentLLM` 新增 `input_tokens/output_tokens/latency_ms/calls/model` + `usage_snapshot()`，`runtime._usage_json()` 记账（**异常时回退 `{"total_tokens": ...}`，记账失败不能毁 run**）；`token_usage_json` 现在含 input/output/cost/latency/llm_calls
  - **新端点**：`POST /intent`（只识别，不写库不花钱）、`GET/POST /conversations`、`GET /conversations/{id}`、`POST /conversations/{id}/close`、`POST /chat`（action = ask/answer/run 三态）、`GET /cost?days=`、`GET /cost/prices`、`GET /evals`、`POST /evals`、`GET /evals/{id}`
  - **前端**：新页「💭 多轮对话」（`Dialog.jsx` 275 行：例句空态、意图徽章、槽位/缺失展示、防抖 350ms 实时意图提示、run 结果内嵌）+ 新页「🧪 评测 / 成本」（`Eval.jsx` 317 行：跑评测 + 逐条用例结果 + 历史评测、7/30/90/365 天成本看板、手写横向条形图**不引图表库**、最近运行明细、价目表）；`Agent.jsx` 加目标输入框下方 `intent-bar` 实时意图提示 + run 头 intent 徽章 + `run-usage` 用量块；`Trace.jsx` 统计卡 4 → 6（加 💰成本、📡 LLM 调用）；`styles.css` +113 行
  - **验证**：新增 `test_intent.py`（26）、`test_eval.py`（18）；**206/206 单测全过**（161 + 45），真实库 mtime 未变；真实库执行 v9 迁移后 **24 张表**、业务数据一行没少（tasks 27 / courses 7 / bago 22 / runs 5 / plans 1 / plan_items 3 / memories 1）；真实 8000 端口冒烟 `/intent` 5 句全部识别正确（含缺槽位追问）、`/chat` 走完「帮我安排学习 → 追问哪一天 → 明天 120 分钟 → 发起 run」四轮、`/evals` 17/17 通过、`/cost` 真实记账（run 6：input 13789 / output 579 / cost ¥0.03221 / 3 次 LLM 调用 / 9571ms）；`npm run build` 成功 49 模块，headless Chrome 确认两个新页真实渲染且数据来自真实 API

### 断点 / 待办
- **Phase 7 已上线，真实库已迁移到 v9**（2026-11-06）：`/intent`、`/chat`、`/conversations`、`/evals`、`/cost` 全部可用。**下次可做**：① 去「💭 多轮对话」页说半句话试追问（如「帮我安排学习」→ 它问哪一天 → 回「明天，120 分钟」）② 去「🧪 评测 / 成本」页点「跑一轮评测」看 17/17（零成本）③ 成本看板目前只有 1 条带完整分项的 run（id=6），再跑几次 Agent 才有像样的曲线 ④ 评测用例集只有 19 条，可仿 `eval_cases.py` 的格式继续加
- **学习路线已按 AI Agent 岗位 JD 重构（2026-11-06）**：`ROUTE_VERSION = "v2-jd-2026-11"`，22 条任务 493h（真实库 27 条含 5 条历史 Agent 派生任务）。**下次可做**：① 在「📚 任务」页逐阶段看新路线是否符合预期，不合就手动改（`seed.py` 是唯一来源，改完把 `ROUTE_VERSION` 加一个后缀即可重跑升级）② 课程挂靠有一处不准（「2026吃透AI大模型应用开发全套教程」同时含 LangGraph/MCP，现挂到 MCP），可在任务页手动改挂靠
- **复盘闭环两个真实 bug 已修（2026-11-01）**：见下方进度记录。真实库现有 1 份计划（id=1，2026-11-02 生效中，3 项 180 分钟）和 1 条 active 记忆；**下次可用真实库走一遍「昨天计划 → 点🤖复盘 → 确认调整」验收**
- **Phase 6（多模型）已完成，后端已重启 + 新前端构建**（2026-08-25）：去「⚙️ 设置」页选供应商/模型/key + 「测试连接」；各 tab 显示 ✅ 已配置徽章。当前活动供应商仍是 deepseek（config.json 只 deepseek_* 三键）。**建议验证**：去 openai/console 或 anthropic/console 拿 key 配上，跑一次 Agent / AI 助手 / 周月报看是否切到对应模型（Claude 若「未返回合法 JSON」是已知限制，run 会落 failed 且显示内容预览）
- **Phase 5（Trace 回放页）已完成**：去「📜 Trace」页看历史运行回放（真实库现有 run 6b88c55 等可直接看，显示为 #2/#1）；新跑一次 run 会展示完整 9 类时间轴，可截图放 README
- **阶段 4（长期记忆）已跑通并已有真实数据（2026-11-01 补）**：真实库现有 1 条 active 记忆（key=「学习时段」，工作日 20:00-23:00 高效）。要再体验：Agent 页说「记住：…」→ 面板出现待确认 → 点「✅ 确认生效」→ 再「安排明天的学习」，计划卡显示 ⏰ 建议时段
- **阶段 3（跨天计划-执行-复盘-调整闭环）已跑通，真实库有 1 份计划但尚未复盘过（2026-11-01 补）**：真实库 plan id=1（2026-11-02 生效中）。2026-11-01 已修掉复盘确认的两个 bug，**下次可放心用真实库走一遍完整验收**：让 Agent「安排明天的学习」→ 第二天学完点「🤖 复盘」→「✅ 确认调整」
- 阶段 2 遗留验收：真实库曾在冒烟中被改过（任务 12 +120 分钟、任务 6 进度锁定 50%），可在 Agent 页历史 run 看「🧾 操作记录」
- 二期计划：**MCP / RAG / 向量库 / LangGraph**（2026-11-06 已全部纳入学习路线的阶段 3-5，但项目代码本身还没实现）；Memory 二期（记忆进 AI 助手聊天页、面板手动加记忆）；以及规划中未实现的**间隔复习、推荐任务、导入导出、AI 流式输出**

### 进度记录（按时间倒序追加）
- 2026-11-06：**Phase 7 · 按 JD 补齐「意图识别 + 对话管理」与「Agent 评测 + 成本看板」**。起因：用户要求去 Boss 直聘查 AI Agent 岗 JD 后优化项目，从 4 个候选里**只勾选这两项**（没选 MCP、没选多智能体协作）。**为什么做这两项**：① JD 里「任务规划 / 对话管理 / 意图识别 / 流程工程」是硬要求，原项目直接吃 goal 文本、没有意图层；② Gartner 说 88% 的 Agent 试点因为缺可观测与评估跨不过生产鸿沟，而原项目 `token_usage_json` 只存一个 `total_tokens`、没有任何成本概念，面试讲不出「这个 Agent 一次多少钱」。**做法**：迁移 v9 加 5 张表 + `agent_runs.intent` 列；`intent.py` 纯规则 7 类意图 + 槽位抽取（**不上 LLM：每轮输入都调模型是纯开销**）；`eval_cases.py` 19 条用例（相对日期占位让用例任何一天跑都成立）+ `eval_runner.py`（默认只跑零成本用例，run 类延迟 import）；`conversations.py` 挂起槽位**落库**（Web 会刷新、后端会重启）；`cost.py` 前缀价目表 + `usage.py` 聚合（**诚实设计**：token 真值、单价常量、未收录模型标 `price_known=False`、早期 run 只有总 token 时 `detail_available=False` 不瞎拆）；`llm.py` 加 `chat_with_detail`/`structured_json_detail`（**旧 `structured_json` 签名与返回值不变**，重试循环里 token 累加不丢账）；`llm_provider.py` 重写记账 + `runtime._usage_json()`（**记账异常回退总 token，不能毁 run**）。前端两个新页 + Agent 页实时意图提示 + Trace 页成本卡。**踩的坑**：① 我用 pwsh 的 `Get-Content -Raw` + `Set-Content -Encoding utf8` 改文件，**PowerShell 5.x 默认按 GBK 读**，把 `Eval.jsx` 和 `styles.css` 的 UTF-8 中文读成乱码写回，build 报 `Expected "}" but found "涓"`——从 git 恢复 `styles.css` 后用 `write`/`edit` 工具重做，**教训：改文件内容一律用 write/edit/read，不用 pwsh 管道**；② `usage.price_table()` 里 `for model, (pin, pout) in PRICING` 报 `ValueError: too many values to unpack`（PRICING 是三元组）；③ `test_llm_provider.py` 单独跑会 `ModuleNotFoundError: No module named 'app'`，因为它没像别的测试那样先 `import helpers` 把 `backend/` 加进 sys.path，全量跑时靠别的测试先导入才侥幸过——已补 `import helpers`。**验证**：`test_intent.py` 26 + `test_eval.py` 18；**206/206 单测全过**（161 + 45），真实库 mtime 前后一致；真实库 v9 迁移后 24 张表、业务数据零损失；真实 8000 冒烟——`/intent` 5 句全对（含「帮我安排学习」缺 date 追问）、`/chat` 四轮走完追问→发起 run、`/evals` 17/17、`/cost` 真实记账（run 6：in 13789 / out 579 / ¥0.03221 / 3 次调用 / 9571ms）；`npm run build` 49 模块，headless Chrome 确认两个新页真实渲染且数据来自真实 API；冒烟留下的 4 个会话 8 条 turn 已清理（真实 run / eval 记录 / 计划保留）
- 2026-11-06：**学习路线按 AI Agent 岗位 JD 全面重构**。起因：用户要求去 Boss 直聘等招聘站查 AI Agent 开发岗的要求，据此优化项目和路线。**调研**：`web_fetch` 抓 zhipin.com / csdn.net 均被拦（域名解析到非公网 IP），只能用搜索摘要；共取到 3 份 Boss 直聘 JD 原文口径 + 牛客/腾讯云/CSDN 路线共识。**JD 高频要求**：任务规划 / 对话管理 / 意图识别 / 流程工程、规划+记忆+工具调用、RAG 架构与企业知识库、检索准确率与生成质量、智能体工作流引擎、多 Agent 协作与任务分解、LangChain+FastAPI、Docker、MCP/A2A（2026 热点）、Context Engineering、可观测与评测（Gartner：88% Agent 试点缺评估跨不过生产鸿沟）。**做法**：① 重写 `backend/app/seed.py`——`TASKS` 15 条 900h → **22 条 493h**（阶段1 基础 70h / 阶段2 LLM 38h 含 Context Engineering 15h / 阶段3 RAG 55h 含 RAG 评测 15h / 阶段4 Agent 90h 含任务规划 18h·意图识别 12h·LangGraph 20h / 阶段5 工程化 65h 含 MCP 20h·多智能体 18h·评测与成本 15h / 阶段6 实习 175h），`BAGU` 15→21 条，`MILESTONES` 项目2 改为「Agent 学习 OS（主力项目）」并补 V4 工程化（评测集 + LLM-as-Judge + 成本看板）；② 新增 **`upgrade_route()` 幂等升级**（`ROUTE_VERSION` 记在 settings，改名保 id/进度/已花时间 → 按 TASKS upsert → 项目改名 → 里程碑补 V4 → 课程按关键词重挂 → 八股去重补录），在 `main.py` 的 lifespan 里 `seed_if_empty()` 之后调用，**老库用户升级不丢进度**；③ 重写 `backend/app/phase_guides.py` 6 个阶段的 guide/job_reqs/sources（sources 换成 Boss 直聘真实 JD 链接 + 牛客/腾讯云/CSDN/百度百科），标题带小时数。**踩的坑**：第一版 `RENAMES` 漏了 3 条旧标题（`Python 基础：函数/类/异常/文件/虚拟环境`、`BM25 / Hybrid / Rerank / Query Rewrite`、`简历 / 面试 / 牛客面经复盘`）→ upsert 找不到就另插一条，临时库跑出 30 个任务含重复；补齐后复测 27 条无重复。**课程挂靠顺序**也有讲究：`COURSE_LINKS` 里越具体的规则要放越后面（后面的覆盖前面的），否则「LangChain+LangGraph+RAG+Agent+MCP」全家桶课程会被宽泛规则抢走。**验证**：新增 `backend/tests/test_route_upgrade.py` 5 用例（版本标记 / 幂等 / 改名保 id 与进度 / 无重复标题 / 覆盖 JD 关键词）；**161/161 单测全过**（156 原有 + 5 新增），真实库 mtime 未变；真实库执行升级后 27 条无重复、`route_version=v2-jd-2026-11`、任务 1 spent 19/prog 50 与任务 12 spent 120 全部保留；8000 端口 `/api/phases` 6 阶段标题与 `/api/tasks` 27 条、`/api/dashboard` 分类进度均正常。**未改前端**（阶段名前缀不变，`stats.py` PHASE_MAP 与 `Tasks.jsx` PHASES 无需同步，dist 未重建）
- 2026-11-01：**关闭服务搬进网页，桌面只留一个图标**。起因：用户看到桌面上 `Agent学习OS` 和 `停止Agent学习OS` 两个图标长得一模一样，问「为什么有两个」「一个软件还要点两个吗」。核查发现不是重复安装，是启动/停止两个入口复用了同一个 `assets/agentos.ico`。**做法**：① 后端新增 `backend/app/shutdown.py`（`request_shutdown()` 起守护线程延迟 0.8s 调退出钩子；钩子是 `os._exit(0)`——本应用所有 SQLite 写都是每次 connect/commit/close，请求返回时已落盘，硬退出不丢数据；`set_exit_hook()` 供测试替换，避免把测试进程杀掉）；② `backend/main.py` 新增 **`POST /api/shutdown`**，**有 Agent run 正在跑时返回 409**（`agent.has_running_run()`，避免误点打断正在花钱的 LLM 调用），重复调用也 409；③ 前端 `Settings.jsx` 页尾新增「🔌 关闭服务」卡片（`btn danger`，`confirm()` 二次确认，成功后整页换成「👋 服务已关闭」提示）；④ **删除桌面 `停止Agent学习OS.lnk`**，`tools/create_desktop_shortcut.ps1` 同步改为只建启动图标 + 自动清理旧版停止快捷方式（`tools/stop_service.py` 保留，命令行仍可用）。**验证**：新增 `backend/tests/test_shutdown.py` 5 用例；**156/156 单测全过**（151 + 5，真实库 mtime 未变）；临时库 8011 端到端——`POST /api/shutdown` → 200 → 1.82s 后 health 连不上、端口 0 条 LISTENING、进程 `poll()=0`、关服务后 agent_runs 计数不变（数据没丢）；临时库 8012 验证 409 分支——注入 status='running' 后 409 且服务仍活，改回 succeeded 后 200 并真退出；**真实 8000 实例实测 POST 也真把服务关掉了**（随后用 `launch_hidden.py` 重新拉起）；`npm run build` 成功（47 模块，`index-DPVjBqHm.js`），bundle 里确认含「关闭服务」「服务已关闭」「/shutdown」，`/api/version` 已变
- 2026-11-01：**复盘闭环两个真实 bug 修复 + 真实库跑通记忆/计划闭环**。① 用真实库（8000）驱动 Agent 跑通记忆闭环（记住偏好→pending→confirm→active）与计划闭环（安排明天学习→plan 3 项全排进 20:00-23:00 高效时段，trace 第 5 条 `user_memories` 证明记忆真实注入 prompt）；真实库现有 agent_plans=1（id=1，2026-11-02）/agent_plan_items=3/agent_memories=1（active）。② 临时库（`AGENT_STUDY_DB`+8011，验证后已删库）跑 9 步复盘闭环，暴露并修掉两个 bug：**BUG-1** `compute_plan_vs_actual` 的 items 只返回 `task_id` 不返回 `item_id`，而 `submit_review` 的 `adjust/remove` 要的是计划项 id——模型唯一能看到的 id 就是 task_id，于是必然误填，confirm 时 400「调整项 18 不存在」；**修复**：items 增加 `item_id`、两个工具 description 明确 item_id 来源、新增 `_resolve_item_ids()` 兼容层（模型误填 task_id 时自动翻译成计划项 id，都对不上才报错）。**BUG-2** `confirm_review` 逐条 `_apply_adjustment` 各自 commit，第 2 条失败时第 1 条已落库、`review_status` 仍 pending——用户看到 400 却已被改了一半，重试会重复应用；**修复**：新增 `_precheck_adjustments()`，在任何写库前校验所有 adjust/remove 的 item_id 都属于本计划。③ 前端 `Agent.jsx` 复盘调整项文案由「调整计划项 #4」改为显示任务名「调整「Python 基础…」预期为 30 分钟」。④ 验证：**151/151 单测全过**（148 原有 + 3 个新回归用例，真实库 mtime 未变）；临时库 8011 真实 DeepSeek 端到端复盘闭环跑通——模型提交 item_id 4/5/6（计划项 id）→ confirm **200 applied**（修复前此处必 400）→ 5 条 confirm 审计全 ok；`npm run build` 成功（47 模块，`index-BxweXTCF.js`），`/api/version` 已变、8000 首页引用新 bundle
- 2026-10-30：**项目交接**（用户更换 AI 继续开发）。核实：项目已迁至 `D:\Learn\Agent学习OS_Web版`（旧 `Desktop\Learn\` 不存在；桌面 `Agent学习OS.lnk` 已修好指向新路径，「停止Agent学习OS」快捷方式缺失未重建）；git 仓库 `yan314404-ai/AgentStudyOS` 干净且与 origin 同步（47ba55e）；**148/148 单测通过**；schema v8；后端在 8010 端口起服务冒烟 `/api/health`、`/api/version`、`/api/agent/runs` 均 200；真实库 tasks17/courses7/runs2/actions2，但 agent_plans=0、agent_memories=0（闭环与记忆尚无真实使用数据）。新增 **`交接提示词.md`**（给下一个 AI 的完整交接：目的/设计思路/进度/代码地图/命令/坑/待办/自查清单）。本文件进度记录补齐至移交状态。
- 2026-08-25：**Phase 6 多模型（DeepSeek/GPT/Claude）完成**（llm.py 重构成 Provider 注册表 + 统一 HTTP 层合并两套 urllib；config.json 新 provider + 三家 {provider}_* 键、save_config 改合并当前文件防冲 key（审出并修的真 bug）；新增 chat_with_usage/structured_json/ping，Claude 顶层 system+max_tokens+同 role 合并+_extract_json 兜底（无 json_object 已知限制）；AgentLLM 委托删 _post、model 初始化即活动模型（修 agent_runs.model 空串 bug）；/api/settings 三端点 + GET /api/config 加 provider/model；「⚙️ 设置」页 + Chat/Agent 横幅跳 #/settings + Reports 内联表单收敛；148 单测全过（+31）+ build 成功 + temp DB 8001 冒烟 8/8（真实 DeepSeek key 测试连接 ok:true、切供应商保留旧 key、config 恢复））
- 2026-08-25：**Phase 5 Agent Trace 回放视图完成**（独立「📜 Trace」页：RunRepo.list/get_run 暴露数字 id → #编号；Trace.jsx 左运行历史 + 右 Agent Run #id + 4 统计卡 + 9 类着色可折叠时间轴 + tool_call/result 合并 + 合成 Finish 行 + 2s 轮询；App.jsx 4 处注册；styles.css .trace-* + 9 个 .t-* 变体；零改动 Agent 运行逻辑、无新依赖；117 单测全过 + build 成功 + 进程内冒烟确认 id 字段 + **8000 后端重启实测 /runs 返回 id:2/id:1**）
- 2026-08-24：**阶段 4 长期记忆完成**（迁移 v8 agent_memories + plan_items.suggested_time；services/memories.py；15→18 工具 get_memories/remember/forget_memory；registry 补参数失败 ok=0 审计；运行时注入 active 记忆到 observations + trace user_memories；planner 规则13-15/synthesizer 规则5；4 个记忆端点；Agent.jsx 记忆面板+计划时段徽章；117 单测全过；真实 DeepSeek 冒烟 ALL PASS——记住偏好 pending→confirm→安排学习，planner 真排 3 项进 20:00-23:00 高效时段带 suggested_time 3/3；临时库不污染真实库）+ **8000 后端已重启加载 v8 + 记忆端点 + 新前端构建**（打开即最新生效）
- 2026-08-24：**打开即最新（自动刷新）完成**（后端 /api/version 摘要 + HTML no-cache/哈希资源 immutable + 前端切前台/10s 检测版本变化自动 reload；重建前端并重启后端验证 header 生效）+ **8000 端口后端已重启为最新代码**（v7 + 新端点 + 自动复盘全部在线）
- 2026-08-24：阶段 3 跨天闭环完成（迁移 v7 agent_plans/agent_plan_items + services/plans.py + 运行时注入 prior_plan_vs_actual + 4 新工具 15 总 + 复盘待确认/确认应用/审计 + 半自动提醒 + 计划区/横幅；84 单测全过；真实 DeepSeek 冒烟全闭环：安排昨天计划→补实际→偏差 -67% over→复盘 pending→confirm 应用+审计；临时库不污染真实库）
- 2026-08-24：阶段 2 数据库→Agent Environment 完成（services 层抽取 + 迁移 v6 agent_actions + 11 工具 6读5写 + 全直接生效 + before/after 审计 + Agent 页操作记录块；53 单测全过；真实冒烟 run 6b88c55 计划精准执行 add_session+update_task，审计/落库全同步）
- 2026-08-24：第 4 阶段 Agent 自主规划最小闭环完成（迁移 v5 + `app/agent` 包 + 5 工具 + 3 提示词 + `/api/agent` 路由 + 「🤖 Agent」页；27 单测全过；真实 DeepSeek 冒烟复现固定流程并创建 2 条待确认任务）
- 2026-08-21：学习路线重构 4 需求完成（迁移 v4 + 进度自动化 + 课程并入路线 + 阶段讲解/岗位要求 + 课程链接验证与替换）；puppeteer 11/11 断言通过；课程替换前备份 + `课程验证报告.md`
- 2026-08-20：第 3 阶段 AI 助手完成（含 chat_messages 迁移 v3 + commit 修复）；UI 美化完成 21/21 断言通过；桌面无黑窗图标启动 + 独立应用窗口 + 🎓新图标；创建本 CLAUDE.md
- 2026-08-19：MVP + 第二阶段完成，UI 美化进行中
