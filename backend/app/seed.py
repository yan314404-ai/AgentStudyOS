"""首次启动时写入种子数据：12 个月学习路线 / 课程 / 项目 + 里程碑 / 今日打卡。

数据来自用户桌面《Agent_大三学习计划_追踪表.xlsx》，幂等：只在对应表为空时写入。
"""
from datetime import date
from .db import connect

# 元组结构：(阶段, 分类, 标题, 说明, 开始, 截止, 优先级, 状态, 进度, 备注, 目标小时数)
TASKS = [
    ("1 · 基础", "编程", "Python 基础：函数/类/异常/文件/虚拟环境", "能独立写中等规模 Python 程序",
     "2026-08-24", "2026-09-13", "高", "待开始", 0, "先过基础，不要停留太久", 60),
    ("1 · 基础", "工程", "Git + Linux + HTTP/JSON/API", "能看懂并调用常见 AI API",
     "2026-09-07", "2026-09-23", "高", "待开始", 0, "", 30),
    ("1 · 基础", "后端", "FastAPI + MySQL/Redis + Docker 入门", "做一个简单 AI API 服务",
     "2026-09-17", "2026-10-18", "中", "待开始", 0, "", 40),
    ("2 · LLM", "原理", "Transformer / Attention / Token / Embedding", "能解释 LLM 基本工作机制",
     "2026-10-08", "2026-11-07", "高", "待开始", 0, "理解原理即可", 40),
    ("2 · LLM", "LLM", "大模型 API / Prompt / Structured Output", "做一个 LLM Demo",
     "2026-10-23", "2026-11-17", "高", "待开始", 0, "", 30),
    ("3 · RAG", "RAG", "文档解析 / Chunk / Embedding / 检索", "PDF 知识库问答 V1",
     "2026-11-12", "2026-12-22", "高", "待开始", 0, "", 50),
    ("3 · RAG", "RAG", "BM25 / Hybrid / Rerank / Query Rewrite", "完成检索质量优化实验",
     "2026-12-12", "2027-01-16", "高", "待开始", 0, "", 40),
    ("4 · Agent", "Agent", "Tool Calling / Function Calling / ReAct", "手写最小 Agent Loop",
     "2027-01-06", "2027-02-10", "高", "待开始", 0, "", 40),
    ("4 · Agent", "Agent", "Memory / Workflow / LangGraph", "多工具 Agent V1",
     "2027-01-31", "2027-03-17", "高", "待开始", 0, "", 50),
    ("4 · Agent", "Agent", "MCP / Tool Registry / 权限与重试", "可控、可恢复的 Agent",
     "2027-03-07", "2027-04-21", "中", "待开始", 0, "", 30),
    ("5 · 工程化", "工程", "Tracing / Eval / Cost / Latency / Cache", "Agent 评测与可观测性",
     "2027-04-01", "2027-06-05", "高", "待开始", 0, "", 50),
    ("6 · 实习准备", "算法", "LeetCode Hot 100 + 高频题型", "150~200 题，重点题二刷",
     "2026-08-25", "2027-06-20", "高", "待开始", 0, "每天 1~2 题", 200),
    ("6 · 实习准备", "八股", "OS / 网络 / MySQL / Redis / Java·Python", "形成自己的面试笔记",
     "2026-11-12", "2027-06-20", "高", "待开始", 0, "每天 30~45 分钟", 80),
    ("6 · 实习准备", "项目", "Research Agent / Coding Agent 二选一深挖", "GitHub + Demo + README + 指标",
     "2027-03-22", "2027-07-20", "高", "待开始", 0, "项目必须能被追问", 120),
    ("6 · 实习准备", "求职", "简历 / 面试 / 牛客面经复盘", "开始投递 Agent / LLM / AI 应用实习",
     "2027-05-21", "2027-08-24", "高", "待开始", 0, "", 40),
]

# 元组结构：(名称, 阶段/主题, 平台, 链接, 老师, 备注, 状态, 进度, 评价, 归属任务标题)
COURSES = [
    ("黑马程序员 Python 基础", "Python", "B站", "https://www.bilibili.com/video/BV1o4411M71o/", "",
     "补 Python 基础", "待开始", 0, "重点语法/面向对象/文件/异常", "Python 基础：函数/类/异常/文件/虚拟环境"),
    ("李沐《动手学深度学习》", "深度学习", "B站", "https://www.bilibili.com/video/BV1gj2CBsETB/", "",
     "理解 Transformer/Attention", "待开始", 0, "选看相关章节即可", "Transformer / Attention / Token / Embedding"),
    ("AI 大模型 RAG 项目实战", "RAG", "B站", "https://www.bilibili.com/video/BV1LHn3z8EZm/", "",
     "从 0 做 RAG", "待开始", 0, "重点文档解析/Chunk/检索/Rerank", "文档解析 / Chunk / Embedding / 检索"),
    ("LangChain + RAG + Agent + LangGraph", "Agent", "B站", "https://www.bilibili.com/video/BV1w8ozBxEAU/", "",
     "Agent 主线课程", "待开始", 0, "理解组件，不要死背 API", "Memory / Workflow / LangGraph"),
    ("LLM + RAG + Agent + LangChain + MCP", "Agent", "B站", "https://www.bilibili.com/video/BV12Vshz3EtQ/", "",
     "专题资料库", "待开始", 0, "查缺补漏，不建议从头刷完", "MCP / Tool Registry / 权限与重试"),
    ("Agent / RAG / LangChain / LangGraph 面试", "面试", "B站", "https://www.bilibili.com/video/BV1iBEq62Em4/", "",
     "后期面试复习", "待开始", 0, "大三后期再重点看", "简历 / 面试 / 牛客面经复盘"),
    ("LeetCode Hot 100", "算法", "LeetCode", "https://leetcode.cn/studyplan/top-100-liked/", "",
     "校招算法", "进行中", 20, "每天 1~2 题，重点题二刷", "LeetCode Hot 100 + 高频题型"),
]

# (项目, 里程碑, 状态, 进度, 开始, 截止, 面试素材)
MILESTONES = [
    ("项目 1：PDF RAG 知识库", "V1 · 文档解析 + Chunk + Embedding + 检索", "待开始", 0, "2026-11-12", "2026-12-22", "RAG 原理"),
    ("项目 1：PDF RAG 知识库", "V2 · BM25 + Hybrid + Rerank", "待开始", 0, "2026-12-12", "2027-01-16", "召回优化"),
    ("项目 1：PDF RAG 知识库", "V3 · 评测集 + Recall/MRR + 失败案例", "待开始", 0, "2027-01-11", "2027-02-05", "指标设计"),
    ("项目 2：Research Agent", "V1 · Search + RAG + Report", "待开始", 0, "2027-02-10", "2027-03-22", "Agent Loop"),
    ("项目 2：Research Agent", "V2 · Retry + Timeout + Memory + Tracing", "待开始", 0, "2027-03-17", "2027-05-01", "工程化"),
    ("项目 2：Research Agent", "V3 · 100 条任务评测 + 成本/延迟分析", "待开始", 0, "2027-04-21", "2027-06-05", "项目深挖"),
    ("项目 3：Coding Agent（加分项）", "V1 · 读取仓库 + 搜索代码 + 运行测试", "待开始", 0, "2027-05-11", "2027-07-20", "代码执行安全"),
]

# 精选八股种子：覆盖 Python / MySQL / Redis / 网络 / OS / LLM / RAG / Agent
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
    ("RAG", "什么是 RAG？主要流程是什么？",
     "RAG（检索增强生成）：先用检索系统从知识库找出相关内容，再拼进 Prompt 让 LLM 基于证据回答，降低幻觉。流程：文档解析 → Chunking → Embedding → 写入向量库；查询时 Embedding 后相似度检索（可混合 BM25），必要时 Rerank，最后生成并附引用。",
     "RAG 流程", 0),
    ("Agent", "什么是 ReAct？Agent Loop 的基本流程？",
     "ReAct 是 Reasoning + Acting：模型交替输出思考（thought）和动作（tool call），观察工具结果（observation）后再思考，直到得到答案。Agent Loop = 模型生成 → 解析工具调用 → 执行 → 把结果回填上下文 → 再生成，直到模型输出最终答案或达到最大步数。",
     "ReAct", 0),
    ("Agent", "LangGraph 相对普通链式调用，核心优势是什么？",
     "LangGraph 把 Agent 建模为图：节点（执行逻辑）+ 边（状态流转）+ 共享 State，支持条件分支、循环、并行、持久化 checkpoint，可精确控制何时调用工具、失败重试、人工介入（human-in-the-loop）。",
     "LangGraph", 0),
    ("工程", "Agent 在生产环境要关注哪些可靠性问题？",
     "Retry（幂等重试）、Timeout（单步超时）、Fallback（模型/工具降级）、缓存（减少重复调用）、日志与 Tracing（链路可观测）、Cost 追踪（token/延迟）、Eval（回归评测）、权限与沙箱（工具调用安全）、Prompt 注入防护、Human-in-the-loop（高风险操作人工确认）。",
     "Agent 工程化", 0),
]


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
    conn.commit()
    conn.close()
    return True
