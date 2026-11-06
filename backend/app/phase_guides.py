"""学习路线各阶段的讲解 + 目标岗位（AI Agent / LLM 应用开发）要求标注。

岗位要求来源（2026-11 检索，见各阶段 sources）：
- BOSS直聘 AI Agent 开发工程师 / AI Agent 工程师(LLM/RAG) / AI 应用开发实习 岗位 JD 摘要
- 牛客网 AI Agent 应用开发工程师（实习）JD
- 面经与技术社区对 2026 Agent 岗位能力要求的归纳
检索不到的细节（如需要登录才能看的 JD 正文）不编造，统一标注来源为「综合招聘信息」。
"""
PHASE_GUIDES = [
    {
        "phase": "1 · 基础",
        "title": "基础打牢 · Python / 工程 / 后端（70h）",
        "guide": (
            "Python 是所有 JD 的**硬门槛**，几乎每条都写「熟练掌握」。本阶段三条线并进："
            "①Python 语言基础（函数/类/异常/文件/venv/typing，够写到中等规模程序即可，别恋战）；"
            "②工程基本功（Git 分支协作 + Linux 常用命令 + HTTP/JSON + Docker 打包，"
            "JD 里通常和 Python 写在同一句）；"
            "③FastAPI 后端（路由/依赖注入/SQLite/部署）——**你手上的 Agent 学习 OS 就是现成的练习场**，"
            "改造它比另起一个 demo 划算得多。"
            "目标：到 LLM 阶段时，你能把模型 API 真正跑起来、能 debug、能部署成服务。"
        ),
        "job_reqs": [
            "Python 熟练使用是必备门槛，多数 JD 与 Node.js/Java 并列要求后端能力",
            "会 Git 协作、熟悉 Linux 常用命令、理解 HTTP/API 调用",
            "Docker 部署能力在多条 JD 中明确列出（不是加分项，是基本项）",
            "能独立写中等规模 Python 程序（函数 / 面向对象 / 异常 / 文件 / 类型标注）",
            "后端融合岗位会额外要求 MySQL/PostgreSQL + Redis",
        ],
        "sources": [
            {"title": "BOSS直聘 · AI Agent 开发工程师（无界AI）", "url": "https://www.zhipin.com/job_detail/61a00e0cd3e3f5d603J92N-4EFdT.html"},
            {"title": "牛客网 · AI Agent 应用开发工程师（实习）", "url": "https://www.nowcoder.com/jobs/detail/438214"},
            {"title": "牛客网 · AI agent 开发（实习）", "url": "https://www.nowcoder.com/jobs/detail/450135"},
        ],
    },
    {
        "phase": "2 · LLM",
        "title": "大模型原理与工程调用（38h）",
        "guide": (
            "你要做的是「大模型应用」而不是训练模型——**原理只学到能解释工作机制**的程度"
            "（Attention / Token / Embedding / 上下文窗口是什么、怎么影响成本与效果），不用手推论文。"
            "重点在工程侧三块：①**Prompt + Context Engineering**——不只是「提示词怎么写」，"
            "而是「有限上下文里放什么、放多少、怎么压缩」，2026 年 JD 已把它当独立能力；"
            "②**Structured Output**——用 JSON Schema / 原生 function calling 让模型稳定输出结构化数据，"
            "这是后面 Tool Calling 的地基；③**多 provider 接入 + 流式 + 错误重试**，"
            "真实项目不可能只接一家模型。产出：一个能切换模型、能稳定输出 JSON 的 LLM 服务。"
        ),
        "job_reqs": [
            "熟悉大模型 API 接入（OpenAI / Claude / DeepSeek / 通义千问 等），多 provider 是常态",
            "Prompt Engineering 是高频考点；Context Engineering 是 2026 新增高频词",
            "结构化输出（JSON Schema）+ Function Call / Tool Calling 是 Agent 岗位核心能力",
            "面试常问：Attention 是什么？上下文窗口怎么影响成本？结构化输出失败怎么兜底？",
        ],
        "sources": [
            {"title": "BOSS直聘 · AI Agent 工程师（LLM/RAG 方向）", "url": "https://www.zhipin.com/job_detail/2a79bc50e4ecc3740nZ_3Nu6GFVZ.html"},
            {"title": "CSDN · AI 大模型应用开发实习｜找岗 + 面试真题 + 面经总结", "url": "https://blog.csdn.net/2401_82753448/article/details/161522566"},
        ],
    },
    {
        "phase": "3 · RAG",
        "title": "RAG 检索增强生成 · 知识库（55h）",
        "guide": (
            "RAG 是「企业级知识库问答」类岗位的**标配**，JD 里通常写成「设计和实现 RAG 架构，"
            "构建企业级知识库系统，**优化检索准确率与生成质量**」。学完整链路："
            "文档解析 → Chunk 切分 → Embedding → 向量库检索（FAISS/Chroma 起步，了解 Milvus/Pinecone）"
            "→ 混合 BM25 → Rerank 重排 → 拼上下文生成。先做出 PDF 知识库问答 V1，"
            "再做检索质量优化实验（Hybrid / Rerank / Query Rewrite）。"
            "**关键区别**：JD 说的是「优化准确率」，所以必须补第三块——评测集 + Recall@K/MRR + 失败案例，"
            "否则你无法证明优化有效，面试也讲不出数字。"
        ),
        "job_reqs": [
            "设计实现 RAG 架构、构建企业级知识库（JD 明确职责，非加分项）",
            "向量数据库：FAISS / Chroma / Milvus / Pinecone（出现率约 40%）",
            "优化文档切分、向量检索、重排、上下文拼装，降低幻觉",
            "要有可量化指标：Recall@K / MRR / 忠实度，能讲清「优化前后差多少」",
            "面试高频：RAG 流程？为什么需要 RAG？幻觉怎么解决？检索差还是生成差怎么定位？",
        ],
        "sources": [
            {"title": "BOSS直聘 · AI Agent 工程师（LLM/RAG 方向）", "url": "https://www.zhipin.com/job_detail/2a79bc50e4ecc3740nZ_3Nu6GFVZ.html"},
            {"title": "BOSS直聘 · AI 应用开发实习生（新旦智能）", "url": "https://www.zhipin.com/job_detail/32941e93e18c3e191HF52dm0GFtS.html"},
            {"title": "牛客网 · AI Agent 应用开发工程师（实习）", "url": "https://www.nowcoder.com/jobs/detail/438214"},
        ],
    },
    {
        "phase": "4 · Agent",
        "title": "Agent 智能体 · 本岗位核心（90h）",
        "guide": (
            "这是**岗位核心**。JD 原文基本是这一串：「构建具备**规划、记忆、工具调用**能力的智能体核心；"
            "设计和实现智能体核心架构，包括**任务规划、对话管理、意图识别和流程工程**」。"
            "所以本阶段按这条链拆开学，而不是笼统「学个 LangChain」："
            "①**先手写最小 Agent Loop**（ReAct / Tool Calling / JSON 容错 / 终止条件）理解本质——"
            "不套框架，面试问的从来是原理；"
            "②**记忆机制**（短期上下文 / 长期记忆 / 结构化记忆 / 写入-确认-注入闭环）；"
            "③**任务规划与分解**（Plan-Execute / 子任务拆解 / 依赖编排 / 重规划）；"
            "④**意图识别与对话管理**（意图路由 / 多轮状态 / 槽位填充）；"
            "⑤**工作流编排**（状态机 / LangGraph 的图、条件边、checkpoint、human-in-the-loop）。"
            "你的项目已经跑通了①②，重点是把③④补上，⑤讲清「为什么用图而不是链」。"
        ),
        "job_reqs": [
            "智能体核心架构：任务规划 → 对话管理 → 意图识别 → 工具调用 → 结果反馈闭环",
            "记忆机制：短期上下文 + 长期记忆（结构化或向量），能讲清失效场景",
            "任务规划与任务分解：把复杂目标拆成可执行子任务，失败能重规划",
            "工作流编排：LangGraph / 状态机 / checkpoint / human-in-the-loop（约 25% 岗位要求）",
            "面试高频：Agent 是什么？怎么调用工具？ReAct 什么时候会失效？JSON 解析失败怎么办？",
        ],
        "sources": [
            {"title": "BOSS直聘 · AI Agent 开发工程师（无界AI）", "url": "https://www.zhipin.com/job_detail/61a00e0cd3e3f5d603J92N-4EFdT.html"},
            {"title": "BOSS直聘 · AI Agent 工程师（LLM/RAG 方向）", "url": "https://www.zhipin.com/job_detail/2a79bc50e4ecc3740nZ_3Nu6GFVZ.html"},
            {"title": "CSDN · 2026 AI Agent 面试高频考点（工具调用 / ReAct / 系统设计）", "url": "https://blog.csdn.net/weixin_29038537/article/details/168837772"},
        ],
    },
    {
        "phase": "5 · 工程化",
        "title": "工程化落地 · MCP / 多智能体 / 可观测与评测（65h）",
        "guide": (
            "实习要求你能**落地**，不是只会 demo。这一阶段四块，都是 2026 JD 的明确要求："
            "①**MCP 协议**——把工具按 Model Context Protocol 暴露给任意客户端，"
            "这是今年的招聘热点，写到简历上辨识度很高；"
            "②**多智能体协作**——Supervisor-Worker / 任务分派 / Agent 间通信 / 共享状态，"
            "JD 原文「实现多 Agent 协作机制、任务分解」；"
            "③**可观测性**——Trace、结构化日志、审计快照，出问题能一眼看出卡在哪一步；"
            "④**评测与成本**——离线评测集、LLM-as-Judge、回归测试、token 成本与缓存。"
            "Gartner 的说法是：缺乏可观测性与科学评估的 Agent 试点，88% 跨不过生产环境的鸿沟。"
            "有了这块，面试讲项目才能聊「上线要踩的坑」，而不是只有「功能」。"
        ),
        "job_reqs": [
            "MCP（Model Context Protocol）部署与工具封装；了解 A2A 智能体通信协议",
            "多 Agent 协作机制：任务编排、Agent 间通信、状态流转与上下文管理",
            "可观测性：Trace / 日志追踪 / 监控告警（部分岗位提 OpenTelemetry / Prometheus）",
            "能分析 token 成本、延迟并给出优化方案（缓存 / 模型降级 / 上下文压缩）",
            "评测体系：离线评测集 + LLM-as-Judge + 回归测试，改代码不退化",
        ],
        "sources": [
            {"title": "BOSS直聘 · AI Agent 工程师（LLM/RAG 方向）", "url": "https://www.zhipin.com/job_detail/2a79bc50e4ecc3740nZ_3Nu6GFVZ.html"},
            {"title": "BOSS直聘 · AI Agent 开发工程师（无界AI）", "url": "https://www.zhipin.com/job_detail/61a00e0cd3e3f5d603J92N-4EFdT.html"},
            {"title": "腾讯云 · Agent 可观测性、自动化评估与 LLMOps 工程化实战", "url": "https://cloud.tencent.com/developer/article/2707872"},
            {"title": "CSDN · 从工程到 Multi-Agent 构建（Agent 岗位 JD 拆解）", "url": "https://blog.csdn.net/m0_71271763/article/details/167806760"},
        ],
    },
    {
        "phase": "6 · 实习准备",
        "title": "实习冲刺 · 算法 / 八股 / 项目 / 投递（175h）",
        "guide": (
            "把前面的积累浓缩成「能过面试」的东西：①**算法** LeetCode Hot 100 精刷 + 高频 50"
            "（校招标配，重点题二刷，**贯穿全程不要堆到最后**）；"
            "②**八股** OS/网络/MySQL/Redis/Python + LLM/Agent 专项"
            "（后者是差异化优势，面试官会重点问）；"
            "③**项目**——**不要再从零造 Research Agent**，你手上已经有 Agent 学习 OS 这个真实项目，"
            "把它打磨成作品集：README + 架构图 + 指标 + Demo，做到能被追问 30 分钟；"
            "④**求职** 简历 / 投递 / 牛客面经复盘。暑期实习 3-4 月集中投递，提前 2 周备好简历。"
        ),
        "job_reqs": [
            "有完整可演示的项目经历：发现问题 → 设计方案 → 落地解决 → 复盘优化全闭环",
            "算法笔试：LeetCode 高频题型（Hot 100 为主）",
            "投递渠道：BOSS直聘 / 牛客 / 实习僧；暑期实习 3-4 月集中投递",
            "面试高频：RAG 流程、Agent 工具调用、多智能体协作、幻觉、项目深挖",
            "实习薪资参考：AI Agent / 大模型应用开发实习约 200-500 元/天，部分有转正",
        ],
        "sources": [
            {"title": "牛客网 · 怎么找 Agent 开发工作/实习（渠道 + 投递策略）", "url": "https://api-cdn.nowcoder.com/feed/main/detail/6181b6f717024915a1d3056bf66c71c3"},
            {"title": "CSDN · AI 大模型应用开发实习｜找岗 + 面试真题 + 面经总结", "url": "https://blog.csdn.net/2401_82753448/article/details/161522566"},
            {"title": "百度百科 · 智能体开发工程师（岗位定义与能力要求）", "url": "https://baike.baidu.com/item/%E6%99%BA%E8%83%BD%E4%BD%93%E5%BC%80%E5%8F%91%E5%B7%A5%E7%A8%8B%E5%B8%88/67572146"},
        ],
    },
]
