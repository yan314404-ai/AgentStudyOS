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
│       ├── db.py             # 建表 + 迁移机制（版本号已到 v8）
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

1. **桌面图标「Agent学习OS」**：无黑窗独立应用窗口启动（`tools/launch_hidden.py`，pythonw 静默，日志 `backend/data/server.log`）；停止用桌面「停止Agent学习OS」
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
- **桌面无黑窗启动**：`tools/launch_hidden.py` + `stop_service.py` + 桌面 .lnk；打开方式为 Chrome/Edge 应用模式独立窗口；自绘图标 `assets/agentos.ico`（**v2 学习主题：📖打开书本+金色对勾+翡翠绿背景**，脚本 `tools/make_icon.ps1`；旧学士帽版备份在 `tools/make_icon_cap.ps1` 可回退）
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

### 断点 / 待办
- **复盘闭环两个真实 bug 已修（2026-11-01）**：见下方进度记录。真实库现有 1 份计划（id=1，2026-11-02 生效中，3 项 180 分钟）和 1 条 active 记忆；**下次可用真实库走一遍「昨天计划 → 点🤖复盘 → 确认调整」验收**
- **Phase 6（多模型）已完成，后端已重启 + 新前端构建**（2026-08-25）：去「⚙️ 设置」页选供应商/模型/key + 「测试连接」；各 tab 显示 ✅ 已配置徽章。当前活动供应商仍是 deepseek（config.json 只 deepseek_* 三键）。**建议验证**：去 openai/console 或 anthropic/console 拿 key 配上，跑一次 Agent / AI 助手 / 周月报看是否切到对应模型（Claude 若「未返回合法 JSON」是已知限制，run 会落 failed 且显示内容预览）
- **Phase 5（Trace 回放页）已完成**：去「📜 Trace」页看历史运行回放（真实库现有 run 6b88c55 等可直接看，显示为 #2/#1）；新跑一次 run 会展示完整 9 类时间轴，可截图放 README
- **阶段 4（长期记忆）已跑通并已有真实数据（2026-11-01 补）**：真实库现有 1 条 active 记忆（key=「学习时段」，工作日 20:00-23:00 高效）。要再体验：Agent 页说「记住：…」→ 面板出现待确认 → 点「✅ 确认生效」→ 再「安排明天的学习」，计划卡显示 ⏰ 建议时段
- **阶段 3（跨天计划-执行-复盘-调整闭环）已跑通，真实库有 1 份计划但尚未复盘过（2026-11-01 补）**：真实库 plan id=1（2026-11-02 生效中）。2026-11-01 已修掉复盘确认的两个 bug，**下次可放心用真实库走一遍完整验收**：让 Agent「安排明天的学习」→ 第二天学完点「🤖 复盘」→「✅ 确认调整」
- 阶段 2 遗留验收：真实库曾在冒烟中被改过（任务 12 +120 分钟、任务 6 进度锁定 50%），可在 Agent 页历史 run 看「🧾 操作记录」
- 二期计划：**MCP / RAG / 向量库 / LangGraph**；Memory 二期（记忆进 AI 助手聊天页、面板手动加记忆）；以及规划中未实现的**间隔复习、推荐任务、导入导出、AI 流式输出**

### 进度记录（按时间倒序追加）
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
