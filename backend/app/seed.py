"""首次启动时写入种子数据：学习路线 / 课程 / 项目 + 里程碑 / 今日打卡。

路线来源：2026-11 按 AI Agent / LLM 应用开发岗位 JD 重新排布（原路线来自用户桌面
《Agent_大三学习计划_追踪表.xlsx》，15 个任务共约 900 小时，远超实习投递前的可用时间，
且缺少 JD 明确要求的「上下文工程 / 任务规划与分解 / 意图识别 / 多智能体协作 / Agent 评测」）。

版本机制：
- 首次建库（seed_if_empty）直接写入当前路线，并标记 route_version
- 已有库启动时由 upgrade_route() 按 ROUTE_VERSION 幂等升级，保留已有 progress / spent_minutes
"""
from datetime import date

from .db import connect

# 路线版本号：改路线内容时必须同步 +1，否则已有库不会升级
ROUTE_VERSION = "v2-jd-2026-11"

# 元组结构：(阶段, 分类, 标题, 说明, 开始, 截止, 优先级, 状态, 进度, 备注, 目标小时数)
# 排布原则：按岗位 JD 出现频率 × 实习投递时间倒排；总时长约 490h（原 900h）
TASKS = [
    # ---------- 阶段 1 · 基础（70h） ----------
    ("1 · 基础", "编程", "Python 基础：语法 / 函数 / 类 / 异常 / 文件 / venv / typing",
     "能独立写中等规模 Python 程序，会用类型标注", "2026-11-06", "2026-11-25", "高", "待开始", 0,
     "已过半，别恋战，够用就往前走", 35),
    ("1 · 基础", "工程", "工程基本功：Git / Linux / HTTP / JSON / Docker",
     "能协作、能看懂接口、能把服务容器化跑起来", "2026-11-15", "2026-11-30", "高", "待开始", 0,
     "Git 分支合并 + Docker 打包一个服务即可", 15),
    ("1 · 基础", "后端", "FastAPI 后端：路由 / SQLite / 依赖注入 / 部署",
     "做一个可用的 LLM API 服务", "2026-11-25", "2026-12-12", "中", "待开始", 0,
     "你的 Agent 学习 OS 就是最好的练习场", 20),

    # ---------- 阶段 2 · LLM（38h） ----------
    ("2 · LLM", "原理", "LLM 原理速通：Transformer / Attention / Token / Embedding / 上下文窗口",
     "能讲清 LLM 怎么工作，不手推论文", "2026-11-20", "2026-12-05", "高", "待开始", 0,
     "应用岗够用即可（原 40h 压到 15h）", 15),
    ("2 · LLM", "Prompt", "Prompt + Context Engineering：系统提示 / few-shot / CoT / 上下文预算与压缩",
     "能写出稳定可控的提示词与上下文策略", "2026-12-01", "2026-12-18", "高", "待开始", 0,
     "2026 JD 高频词：Context Engineering", 15),
    ("2 · LLM", "LLM", "大模型 API 工程化：多 provider / 流式 / Structured Output / 错误重试",
     "能接任意一家模型并稳定输出结构化数据", "2026-12-10", "2026-12-24", "高", "待开始", 0,
     "JSON Schema 校验 + 失败重试是面试考点", 8),

    # ---------- 阶段 3 · RAG（55h） ----------
    ("3 · RAG", "RAG", "RAG 全链路：文档解析 / Chunk 策略 / Embedding / 向量库（FAISS·Chroma）",
     "做出 PDF 知识库问答 V1", "2026-12-15", "2027-01-08", "高", "待开始", 0,
     "先跑通链路，再谈优化", 22),
    ("3 · RAG", "RAG", "检索质量优化：BM25 / Hybrid / Rerank / Query Rewrite",
     "完成检索质量对比实验", "2026-12-28", "2027-01-15", "高", "待开始", 0,
     "每次改动都要有指标对比", 18),
    ("3 · RAG", "评测", "RAG 评测：评测集构建 / Recall@K / MRR / 忠实度 / 失败案例",
     "能证明你的检索优化真的有效", "2027-01-08", "2027-01-22", "高", "待开始", 0,
     "JD 明确要求「优化检索准确率与生成质量」", 15),

    # ---------- 阶段 4 · Agent（90h） ----------
    ("4 · Agent", "Agent", "手写最小 Agent Loop：ReAct / Tool Calling / JSON 容错 / 终止条件",
     "不套框架，手写一个能跑的多步 Agent", "2027-01-10", "2027-01-28", "高", "待开始", 0,
     "先手写再学框架，面试问的是原理", 25),
    ("4 · Agent", "Agent", "记忆机制：短期上下文 / 长期记忆 / 结构化记忆 / 写入-确认-注入",
     "做出有记忆、越用越准的 Agent", "2027-01-20", "2027-02-05", "高", "待开始", 0,
     "你的项目已有落地，重点是想清边界与失效场景", 15),
    ("4 · Agent", "Agent", "任务规划与任务分解：Plan-Execute / 子任务拆解 / 依赖编排 / 重规划",
     "能把复杂目标拆成可执行步骤", "2027-01-25", "2027-02-10", "高", "待开始", 0,
     "JD 高频：任务规划、任务分解", 18),
    ("4 · Agent", "Agent", "意图识别与对话管理：意图路由 / 多轮状态 / 槽位填充",
     "能分辨用户想干什么并保持多轮上下文", "2027-02-01", "2027-02-14", "中", "待开始", 0,
     "JD 原文：任务规划、对话管理、意图识别", 12),
    ("4 · Agent", "Agent", "工作流编排：状态机 / LangGraph 图·条件边·checkpoint·HITL",
     "把 Agent 做成可控、可恢复的工作流", "2027-02-05", "2027-02-20", "高", "待开始", 0,
     "重点讲清为什么用图而不是链", 20),

    # ---------- 阶段 5 · 工程化（65h） ----------
    ("5 · 工程化", "Agent", "MCP 协议实战：写 MCP Server / 接入客户端 / Tool Registry / 权限沙箱",
     "能把自己的工具开放给任意 MCP 客户端", "2027-02-10", "2027-02-25", "高", "待开始", 0,
     "2026 招聘热点，写到简历上很加分", 20),
    ("5 · 工程化", "Agent", "多智能体协作：Supervisor-Worker / 任务分派 / Agent 间通信 / 共享状态",
     "做出一个多 Agent 协同的完整任务", "2027-02-18", "2027-03-05", "高", "待开始", 0,
     "JD 高频：多 Agent 协作机制", 18),
    ("5 · 工程化", "工程", "可观测性：Trace / 结构化日志 / 审计快照 / 故障定位",
     "Agent 出问题能一眼看出卡在哪一步", "2027-02-20", "2027-03-05", "中", "待开始", 0,
     "你的项目已有 trace + 审计，提炼成方法论", 12),
    ("5 · 工程化", "工程", "Agent 评测与成本：离线评测集 / LLM-as-Judge / 回归测试 / token 成本 / 缓存",
     "改代码不退化，且能算出每次运行成本", "2027-02-25", "2027-03-10", "高", "待开始", 0,
     "Gartner：缺可观测与评估的 Agent 上不了生产", 15),

    # ---------- 阶段 6 · 实习准备（175h，其中算法/八股贯穿全程） ----------
    ("6 · 实习准备", "算法", "LeetCode Hot 100 精刷 + 高频 50",
     "每天 1 题，重点题二刷", "2026-11-06", "2027-03-20", "高", "待开始", 0,
     "贯穿全程，不要堆到最后（原 200h 压到 90h）", 90),
    ("6 · 实习准备", "八股", "八股：OS / 网络 / MySQL / Redis / Python / LLM / Agent",
     "形成自己的面试笔记", "2026-12-01", "2027-03-20", "高", "待开始", 0,
     "每天 30 分钟，LLM/Agent 部分优先", 50),
    ("6 · 实习准备", "项目", "项目作品集：打磨 Agent 学习 OS（README / 架构图 / 指标 / Demo）",
     "GitHub + Demo + README + 指标，能被追问 30 分钟", "2027-02-01", "2027-03-15", "高", "待开始", 0,
     "你已经有一个真实项目，别从零再造（原 Research Agent 120h 改成打磨已有）", 25),
    ("6 · 实习准备", "求职", "简历 / 投递 / 牛客面经复盘",
     "开始投递 AI Agent / LLM 应用开发实习", "2027-03-01", "2027-03-20", "高", "待开始", 0,
     "暑期实习 3-4 月集中投递，提前 2 周备好简历", 10),
]

# 元组结构：(名称, 阶段/主题, 平台, 链接, 老师, 备注, 状态, 进度, 评价, 归属任务标题)
COURSES = [
    ("黑马程序员 Python 基础", "Python", "B站", "https://www.bilibili.com/video/BV1o4411M71o/", "",
     "补 Python 基础", "待开始", 0, "重点语法/面向对象/文件/异常",
     "Python 基础：语法 / 函数 / 类 / 异常 / 文件 / venv / typing"),
    ("李沐《动手学深度学习》", "深度学习", "B站", "https://www.bilibili.com/video/BV1gj2CBsETB/", "",
     "理解 Transformer/Attention", "待开始", 0, "选看 Attention 相关章节即可",
     "LLM 原理速通：Transformer / Attention / Token / Embedding / 上下文窗口"),
    ("AI 大模型 RAG 项目实战", "RAG", "B站", "https://www.bilibili.com/video/BV1LHn3z8EZm/", "",
     "从 0 做 RAG", "待开始", 0, "重点文档解析/Chunk/检索/Rerank",
     "RAG 全链路：文档解析 / Chunk 策略 / Embedding / 向量库（FAISS·Chroma）"),
    ("LangChain + RAG + Agent + LangGraph", "Agent", "B站", "https://www.bilibili.com/video/BV1w8ozBxEAU/", "",
     "Agent 主线课程", "待开始", 0, "理解组件，不要死背 API",
     "工作流编排：状态机 / LangGraph 图·条件边·checkpoint·HITL"),
    ("LLM + RAG + Agent + LangChain + MCP", "Agent", "B站", "https://www.bilibili.com/video/BV12Vshz3EtQ/", "",
     "专题资料库", "待开始", 0, "查缺补漏，不建议从头刷完",
     "MCP 协议实战：写 MCP Server / 接入客户端 / Tool Registry / 权限沙箱"),
    ("Agent / RAG / LangChain / LangGraph 面试", "面试", "B站", "https://www.bilibili.com/video/BV1iBEq62Em4/", "",
     "后期面试复习", "待开始", 0, "大三后期再重点看",
     "简历 / 投递 / 牛客面经复盘"),
    ("LeetCode Hot 100", "算法", "LeetCode", "https://leetcode.cn/studyplan/top-100-liked/", "",
     "校招算法", "进行中", 20, "每天 1~2 题，重点题二刷",
     "LeetCode Hot 100 精刷 + 高频 50"),
]

# (项目, 里程碑, 状态, 进度, 开始, 截止, 面试素材)
# 项目 2 从「从零做 Research Agent」改为「打磨已有的 Agent 学习 OS」——手上已有真实项目，重造是浪费
MILESTONES = [
    ("项目 1：PDF RAG 知识库", "V1 · 文档解析 + Chunk + Embedding + 检索", "待开始", 0, "2026-12-15", "2027-01-08", "RAG 原理"),
    ("项目 1：PDF RAG 知识库", "V2 · BM25 + Hybrid + Rerank", "待开始", 0, "2026-12-28", "2027-01-15", "召回优化"),
    ("项目 1：PDF RAG 知识库", "V3 · 评测集 + Recall@K/MRR + 失败案例", "待开始", 0, "2027-01-08", "2027-01-22", "指标设计"),
    ("项目 2：Agent 学习 OS（主力项目）", "V1 · 单轮 Agent：Tool Calling + ReAct Loop + Trace", "待开始", 0, "2027-01-10", "2027-01-28", "Agent Loop"),
    ("项目 2：Agent 学习 OS（主力项目）", "V2 · 记忆与计划：长期记忆 / 跨天计划 / 复盘调整", "待开始", 0, "2027-01-20", "2027-02-10", "记忆与规划"),
    ("项目 2：Agent 学习 OS（主力项目）", "V3 · 多智能体：Supervisor-Worker / MCP 工具接入", "待开始", 0, "2027-02-10", "2027-03-05", "多 Agent 协作"),
    ("项目 2：Agent 学习 OS（主力项目）", "V4 · 工程化：评测集 / LLM-as-Judge / 成本看板", "待开始", 0, "2027-02-25", "2027-03-15", "可观测与评估"),
    ("项目 3：Coding Agent（加分项）", "V1 · 读取仓库 + 搜索代码 + 运行测试", "待开始", 0, "2027-05-11", "2027-07-20", "代码执行安全"),
]

# 精选八股种子：覆盖 Python / MySQL / Redis / 网络 / OS / LLM / RAG / Agent / 工程
# 后 5 条按 2026 岗位 JD 与面经补充（Context Engineering / 多智能体 / MCP / 评测 / 工具调用容错）
BAGU = [
    ("Python", "解释 Python 的 GIL，以及它带来的影响？",
     "GIL 是 CPython 解释器中的全局解释器锁，同一时刻只允许一个线程执行 Python 字节码。它简化了内存管理和 C 扩展的编写，但限制了多线程的 CPU 密集性能。多线程适合 IO 密集；CPU 密集应使用多进程（multiprocessing）或协程/异步。",
     "GIL", 0),
    ("Python", "深拷贝和浅拷贝有什么区别？",
     "浅拷贝只复制最外层容器，内部可变对象仍共享引用（copy.copy）；深拷贝递归复制所有对象（copy.deepcopy）。切片、list()、dict.copy() 都是浅拷贝。",
     "深浅拷贝", 0),
    ("Python", "生成器（generator）和普通函数有什么区别？",
     "生成器用 yield 产出值，是惰性求值，一次只生成一个，保存执行状态，内存友好；普通函数 return 后结束。生成器可用于流水线处理、无限序列。",
     "生成器", 0),
    ("MySQL", "什么是 MVCC？它如何保证事务隔离？",
     "MVCC（多版本并发控制）通过版本链 + Read View 实现。每行记录有隐藏字段（trx_id、roll_pointer），更新时不覆盖旧值而是生成新版本。事务通过 Read View 判断哪些版本可见，实现 RC（每次读生成 Read View）和 RR（首次读固定 Read View）隔离级别。",
     "MVCC", 0),
    ("MySQL", "为什么 InnoDB 用 B+ 树做索引？",
     "B+ 树矮胖（3~4 层可存千万级数据），非叶子节点只存键、叶子存所有数据并形成有序链表，范围查询高效；节点大小和磁盘页（16KB）匹配，减少 IO 次数。相比哈希不支持范围，相比 B 树，B+ 树叶节点链表更适合范围扫描和顺序 IO。",
     "B+树", 0),
    ("Redis", "缓存穿透、缓存击穿、缓存雪崩分别是什么？怎么解决？",
     "穿透：查一个不存在的数据，请求打到 DB。解决：缓存空值、布隆过滤器。击穿：热点 key 过期瞬间大量请求打 DB。解决：互斥锁、逻辑过期。雪崩：大量 key 同时过期或 Redis 宕机。解决：过期时间加随机值、多级缓存、限流降级。",
     "缓存三兄弟", 0),
    ("Redis", "Redis 有哪些常用数据结构？各自适合什么场景？",
     "String（计数/缓存）、Hash（对象存储）、List（消息队列/列表）、Set（去重/共同好友）、ZSet（排行榜/延迟队列）、Bitmap（签到）、HyperLogLog（UV 统计）、Geo（地理位置）。",
     "数据结构", 0),
    ("计算机网络", "简述 TCP 三次握手和四次挥手。",
     "三次握手：SYN → SYN+ACK → ACK，确认双方收发能力并同步初始序列号。四次挥手：FIN → ACK → FIN → ACK（TIME_WAIT 在主动关闭方），因为 TCP 是全双工，需各自关闭写方向。",
     "TCP", 0),
    ("计算机网络", "HTTP/1.1 和 HTTP/2 的主要区别？",
     "HTTP/1.1：串行请求、文本协议、有队头阻塞。HTTP/2：二进制分帧、多路复用（一个 TCP 连接并发多个流）、头部压缩（HPACK）、服务端推送。但 HTTP/2 仍有 TCP 层队头阻塞，HTTP/3 用 QUIC/UDP 解决。",
     "HTTP", 0),
    ("操作系统", "进程、线程、协程的区别？",
     "进程是资源分配的基本单位，地址空间独立；线程是 CPU 调度的基本单位，共享进程地址空间，切换成本低；协程是用户态调度，由程序主动让出（await），无内核切换，适合高并发 IO，但单线程内无法利用多核（需配合多进程）。",
     "进程线程协程", 0),
    ("LLM", "Transformer 中的 Attention 是什么？",
     "Attention 让每个 token 根据自己的 Query 与其它 token 的 Key 计算相似度（点积 + softmax），再加权求和对应的 Value，从而动态聚合上下文。Self-Attention 是自注意力（序列内），Multi-Head 是多个头并行捕捉不同子空间的关系。复杂度 O(n²)。",
     "Attention", 0),
    ("LLM", "什么是 Context Engineering？和 Prompt Engineering 有什么区别？",
     "Prompt Engineering 关注「指令怎么写」；Context Engineering 关注「在有限上下文窗口里放什么、放多少、按什么顺序放」——系统提示、工具描述、检索结果、长期记忆、对话历史、示例各自的预算分配与压缩策略。2026 年岗位把它当独立能力，因为 Agent 的效果瓶颈往往不在措辞，而在上下文里塞了什么、塞了多少。",
     "Context Engineering", 0),
    ("RAG", "什么是 RAG？主要流程是什么？",
     "RAG（检索增强生成）：先用检索系统从知识库找出相关内容，再拼进 Prompt 让 LLM 基于证据回答，降低幻觉。流程：文档解析 → Chunking → Embedding → 写入向量库；查询时 Embedding 后相似度检索（可混合 BM25），必要时 Rerank，最后生成并附引用。",
     "RAG 流程", 0),
    ("RAG", "RAG 的检索质量怎么评估？Recall@K 和 MRR 有什么区别？",
     "先建评测集（问题 + 标准答案 + 对应文档片段），再算：Recall@K = 前 K 条结果里包含相关文档的比例，衡量「找得到吗」；MRR = 第一个相关结果排名倒数的均值，衡量「排得靠前吗」；再加生成侧指标（忠实度/相关性，用 LLM-as-Judge 或人工）。只看「感觉答得还行」无法定位是检索差还是生成差。",
     "RAG 评测", 0),
    ("Agent", "什么是 ReAct？Agent Loop 的基本流程？",
     "ReAct 是 Reasoning + Acting：模型交替输出思考（thought）和动作（tool call），观察工具结果（observation）后再思考，直到得到答案。Agent Loop = 模型生成 → 解析工具调用 → 执行 → 把结果回填上下文 → 再生成，直到模型输出最终答案或达到最大步数。",
     "ReAct", 0),
    ("Agent", "ReAct 在什么情况下会失效？",
     "典型三种：①工具返回格式不符合预期时模型陷入死循环，反复调同一个工具；②任务需要长期状态或跨会话记忆时，上下文装不下；③工具语义模糊（描述不清、参数重叠）时模型选错工具。对策：工具描述写清输入输出与失败语义、加最大步数与重复调用检测、把长任务拆成子任务、失败信息回填让模型自修复。",
     "ReAct 失效", 0),
    ("Agent", "模型返回的工具调用 JSON 格式错误，你会怎么处理？",
     "四层防御：①结构化输出约束——用 JSON Schema / 原生 function calling，而不是让模型自由输出再正则；②解析容错——容忍多余字段、缺失可选字段、字符串化数字；③重试与自修复——把解析错误信息回填给模型让它重写，限制 1~2 次；④降级——仍失败则走 fallback 工具或返回可读错误。同时在 trace 里记录每次解析失败，用于优化工具描述。",
     "工具调用容错", 0),
    ("Agent", "LangGraph 相对普通链式调用，核心优势是什么？",
     "LangGraph 把 Agent 建模为图：节点（执行逻辑）+ 边（状态流转）+ 共享 State，支持条件分支、循环、并行、持久化 checkpoint，可精确控制何时调用工具、失败重试、人工介入（human-in-the-loop）。",
     "LangGraph", 0),
    ("Agent", "多智能体协作有哪些常见模式？各自适合什么场景？",
     "常见四种：①Supervisor-Worker——主管分派子任务给专职 Agent，最常用，适合任务可分解的场景；②Pipeline——顺序流水线，适合有固定阶段的流程；③Debate/Voting——多 Agent 互相质疑投票，适合需要提高准确率的高风险判断；④Hierarchical——分层主管，适合大规模任务。核心难点是任务分派、Agent 间通信协议、共享状态一致性与成本控制。",
     "多智能体", 0),
    ("Agent", "MCP 是什么？它解决了什么问题？",
     "MCP（Model Context Protocol）是开放协议，用统一方式把「工具 / 资源 / 提示模板」暴露给任意 LLM 客户端。它解决 N×M 集成爆炸：以前每个 Agent 框架要自己适配每个工具，现在工具实现一次 MCP Server，任何支持 MCP 的客户端都能接入。核心概念：Server（提供能力）、Client（Agent 侧）、Tools/Resources/Prompts 三类原语，传输走 stdio 或 HTTP+SSE。",
     "MCP", 0),
    ("工程", "Agent 在生产环境要关注哪些可靠性问题？",
     "Retry（幂等重试）、Timeout（单步超时）、Fallback（模型/工具降级）、缓存（减少重复调用）、日志与 Tracing（链路可观测）、Cost 追踪（token/延迟）、Eval（回归评测）、权限与沙箱（工具调用安全）、Prompt 注入防护、Human-in-the-loop（高风险操作人工确认）。",
     "Agent 工程化", 0),
    ("工程", "Agent 的评测怎么做？为什么不能只看「感觉效果不错」？",
     "分三层：①单元级——工具调用准确率、JSON 解析成功率、参数正确率；②任务级——端到端成功率、平均步数、平均耗时与成本；③质量级——用 LLM-as-Judge 或人工标注打分（相关性、忠实度、完整性）。关键是先建固定评测集（几十条真实任务），每次改动都跑一遍看指标涨跌，否则优化就是抽卡。线上再做采样评测 + Trace 回放定位失败原因。",
     "Agent 评测", 0),
]

# 旧路线标题 → 新路线标题（改名保留原 id 与 progress / spent_minutes）
# 注意：改名的目标是新 TASKS 里真实存在的标题，否则 upsert 会另插一条造成重复
RENAMES = {
    "Python 基础：函数/类/异常/文件/虚拟环境":
        "Python 基础：语法 / 函数 / 类 / 异常 / 文件 / venv / typing",
    "Git + Linux + HTTP/JSON/API": "工程基本功：Git / Linux / HTTP / JSON / Docker",
    "FastAPI + MySQL/Redis + Docker 入门": "FastAPI 后端：路由 / SQLite / 依赖注入 / 部署",
    "Transformer / Attention / Token / Embedding":
        "LLM 原理速通：Transformer / Attention / Token / Embedding / 上下文窗口",
    "大模型 API / Prompt / Structured Output":
        "大模型 API 工程化：多 provider / 流式 / Structured Output / 错误重试",
    "文档解析 / Chunk / Embedding / 检索":
        "RAG 全链路：文档解析 / Chunk 策略 / Embedding / 向量库（FAISS·Chroma）",
    "Tool Calling / Function Calling / ReAct":
        "手写最小 Agent Loop：ReAct / Tool Calling / JSON 容错 / 终止条件",
    "BM25 / Hybrid / Rerank / Query Rewrite":
        "检索质量优化：BM25 / Hybrid / Rerank / Query Rewrite",
    "简历 / 面试 / 牛客面经复盘": "简历 / 投递 / 牛客面经复盘",
    "Memory / Workflow / LangGraph":
        "记忆机制：短期上下文 / 长期记忆 / 结构化记忆 / 写入-确认-注入",
    "MCP / Tool Registry / 权限与重试":
        "MCP 协议实战：写 MCP Server / 接入客户端 / Tool Registry / 权限沙箱",
    "Tracing / Eval / Cost / Latency / Cache":
        "可观测性：Trace / 结构化日志 / 审计快照 / 故障定位",
    "OS / 网络 / MySQL / Redis / Java·Python":
        "八股：OS / 网络 / MySQL / Redis / Python / LLM / Agent",
    "Research Agent / Coding Agent 二选一深挖":
        "项目作品集：打磨 Agent 学习 OS（README / 架构图 / 指标 / Demo）",
    "LeetCode Hot 100 + 高频题型": "LeetCode Hot 100 精刷 + 高频 50",
}

# 课程挂靠：用课程名关键词匹配（真实库里用户可能改过课程名，不能用精确匹配）
# 顺序有意义：后面的规则会覆盖前面的（更具体的关键词要放后面），
# 否则「LangChain+LangGraph+RAG+Agent+MCP」这种全家桶课程会被前面的宽泛规则抢走
COURSE_LINKS = [
    ("黑马程序员 Python", "Python 基础：语法 / 函数 / 类 / 异常 / 文件 / venv / typing"),
    ("动手学深度学习", "LLM 原理速通：Transformer / Attention / Token / Embedding / 上下文窗口"),
    ("RAG", "RAG 全链路：文档解析 / Chunk 策略 / Embedding / 向量库（FAISS·Chroma）"),
    ("MCP", "MCP 协议实战：写 MCP Server / 接入客户端 / Tool Registry / 权限沙箱"),
    ("LangGraph", "工作流编排：状态机 / LangGraph 图·条件边·checkpoint·HITL"),
    ("面试", "简历 / 投递 / 牛客面经复盘"),
    ("LeetCode", "LeetCode Hot 100 精刷 + 高频 50"),
]

# 旧里程碑名 → 新里程碑名（项目 2 从 Research Agent 改成 Agent 学习 OS）
MILESTONE_RENAMES = {
    "V1 · Search + RAG + Report": "V1 · 单轮 Agent：Tool Calling + ReAct Loop + Trace",
    "V2 · Retry + Timeout + Memory + Tracing": "V2 · 记忆与计划：长期记忆 / 跨天计划 / 复盘调整",
    "V3 · 100 条任务评测 + 成本/延迟分析": "V3 · 多智能体：Supervisor-Worker / MCP 工具接入",
}


def _today() -> str:
    return date.today().isoformat()


def seed_if_empty() -> bool:
    """返回 True 表示执行了种子写入。"""
    conn = connect()
    count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    if count > 0:
        conn.close()
        return False

    now = _today()
    cur = conn.cursor()
    for t in TASKS:
        phase, category, title, desc, start, due, prio, status, prog, note, hours = t
        cur.execute(
            "INSERT INTO tasks(phase,category,title,description,start_date,due_date,priority,status,progress,note,hours,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (phase, category, title, desc, start, due, prio, status, prog, note, hours, now),
        )
    # 任务插入后建立 标题→id 映射，供课程挂靠
    task_ids = {r["title"]: r["id"] for r in conn.execute("SELECT id,title FROM tasks")}
    for c in COURSES:
        name, phase, platform, url, teacher, note, status, prog, review, task_title = c
        cur.execute(
            "INSERT INTO courses(name,phase,platform,url,teacher,note,status,progress,review,task_id,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (name, phase, platform, url, teacher, note, status, prog, review, task_ids.get(task_title), now),
        )
    for m in MILESTONES:
        pname, mname, status, prog, start, due, interview = m
        cur.execute(
            "SELECT id FROM projects WHERE name=?", (pname,),
        )
        row = cur.fetchone()
        if row:
            pid = row[0]
        else:
            cur.execute(
                "INSERT INTO projects(name,version,progress,status,interview_points,created_at) VALUES(?,?,?,?,?,?)"
                " ON CONFLICT DO NOTHING",
                (pname, mname.split("·")[0].strip(), 0, "待开始", interview, now),
            )
            pid = cur.lastrowid
        cur.execute(
            "INSERT INTO milestones(project_id,name,status,progress,start_date,end_date,note) VALUES(?,?,?,?,?,?,?)",
            (pid, mname, status, prog, start, due, interview),
        )
    for q in BAGU:
        category, question, answer, tag, mastery = q
        cur.execute(
            "INSERT INTO bago_questions(category,question,standard_answer,tags,mastery,created_at)"
            " VALUES(?,?,?,?,?,?)",
            (category, question, answer, tag, mastery, now),
        )
    # 今日打卡占位（无则插入）
    cur.execute("INSERT OR IGNORE INTO daily_logs(log_date,created_at) VALUES(?,?)", (now, now))
    # 新库直接就是当前路线版本，避免 upgrade_route 再跑一遍
    cur.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('route_version',?)", (ROUTE_VERSION,))
    conn.commit()
    conn.close()
    return True


def upgrade_route() -> bool:
    """把已有库的学习路线幂等升级到 ROUTE_VERSION。返回 True 表示执行了升级。

    原则：只改内容不删数据——已有任务的 id / progress / spent_minutes / status 全部保留，
    只更新标题、阶段、说明、目标小时数、排期；路线里新增的能力项按标题补插。
    """
    conn = connect()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key='route_version'").fetchone()
        if row and row["value"] == ROUTE_VERSION:
            return False

        cur = conn.cursor()
        now = _today()

        # 1) 旧标题改名（保住 id 与进度）
        for old, new in RENAMES.items():
            cur.execute("UPDATE tasks SET title=? WHERE title=?", (new, old))

        # 2) 按当前路线逐条 upsert
        for t in TASKS:
            phase, category, title, desc, start, due, prio, status, prog, note, hours = t
            exist = cur.execute("SELECT id FROM tasks WHERE title=?", (title,)).fetchone()
            if exist:
                cur.execute(
                    "UPDATE tasks SET phase=?, category=?, description=?, start_date=?, due_date=?,"
                    " hours=?, note=? WHERE id=?",
                    (phase, category, desc, start, due, hours, note, exist[0]),
                )
            else:
                cur.execute(
                    "INSERT INTO tasks(phase,category,title,description,start_date,due_date,priority,status,progress,note,hours,created_at)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (phase, category, title, desc, start, due, prio, status, prog, note, hours, now),
                )

        # 3) 项目 2 改名（Research Agent → Agent 学习 OS）
        cur.execute(
            "UPDATE projects SET name=? WHERE name=?",
            ("项目 2：Agent 学习 OS（主力项目）", "项目 2：Research Agent"),
        )

        # 4) 里程碑改名 + 补 V4
        for old, new in MILESTONE_RENAMES.items():
            cur.execute("UPDATE milestones SET name=? WHERE name=?", (new, old))
        proj = cur.execute(
            "SELECT id FROM projects WHERE name='项目 2：Agent 学习 OS（主力项目）'"
        ).fetchone()
        if proj:
            pid = proj[0]
            for m in MILESTONES:
                pname, mname, status, prog, start, due, interview = m
                if pname != "项目 2：Agent 学习 OS（主力项目）":
                    continue
                if cur.execute("SELECT 1 FROM milestones WHERE project_id=? AND name=?", (pid, mname)).fetchone():
                    cur.execute(
                        "UPDATE milestones SET start_date=?, end_date=?, note=? WHERE project_id=? AND name=?",
                        (start, due, interview, pid, mname),
                    )
                else:
                    cur.execute(
                        "INSERT INTO milestones(project_id,name,status,progress,start_date,end_date,note)"
                        " VALUES(?,?,?,?,?,?,?)",
                        (pid, mname, status, prog, start, due, interview),
                    )

        # 5) 课程重新挂靠（按关键词，兼容用户改过课程名）
        task_ids = {r["title"]: r["id"] for r in cur.execute("SELECT id,title FROM tasks")}
        for keyword, task_title in COURSE_LINKS:
            tid = task_ids.get(task_title)
            if tid:
                cur.execute(
                    "UPDATE courses SET task_id=? WHERE name LIKE ?", (tid, f"%{keyword}%")
                )

        # 6) 补齐新增八股（按问题文本去重，用户自己加的不动）
        for q in BAGU:
            category, question, answer, tag, mastery = q
            if not cur.execute("SELECT 1 FROM bago_questions WHERE question=?", (question,)).fetchone():
                cur.execute(
                    "INSERT INTO bago_questions(category,question,standard_answer,tags,mastery,created_at)"
                    " VALUES(?,?,?,?,?,?)",
                    (category, question, answer, tag, mastery, now),
                )

        cur.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('route_version',?)", (ROUTE_VERSION,))
        conn.commit()
        return True
    finally:
        conn.close()
