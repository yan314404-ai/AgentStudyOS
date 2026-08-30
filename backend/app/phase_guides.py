"""学习路线各阶段的讲解 + 目标岗位（AI Agent / LLM 应用开发实习）要求标注。

岗位要求检索自牛客网 JD、CSDN 面经/岗位分析（2026-08 检索），链接见各阶段 sources。
检索不到的（如 Boss 直聘需登录的细节）不编造，统一标注来源为「综合招聘信息」。
"""
PHASE_GUIDES = [
    {
        "phase": "1 · 基础",
        "title": "基础打牢 · Python / 工程 / 后端",
        "guide": (
            "Python 是目标岗位的**硬门槛**，几乎所有 JD 都要求熟练使用。本阶段三条线并进："
            "①Python 语言基础（函数/类/异常/文件/虚拟环境，够写到中等规模程序即可，别恋战）；"
            "②工程基础（Git + Linux + HTTP/JSON/API，能看懂并调用常见 AI API）；"
            "③后端入门（FastAPI + MySQL/Redis + Docker，做出一个简单的 AI API 服务）。"
            "目标：到 LLM 阶段时，你能把模型 API 真正跑起来、能 debug、能部署。"
        ),
        "job_reqs": [
            "Python 熟练使用是必备门槛（部分岗位要求“精通”）",
            "部分后端融合岗位要求 Java 基础扎实（多线程 / 集合 / IO / SpringBoot）",
            "会 Git 协作、熟悉 Linux 基本命令、理解 HTTP/API 调用",
            "能独立写中等规模 Python 程序（函数 / 面向对象 / 异常 / 文件）",
        ],
        "sources": [
            {"title": "牛客网 · AI Agent 应用开发工程师（实习）", "url": "https://www.nowcoder.com/jobs/detail/438214"},
            {"title": "牛客网 · AI agent 开发（实习）", "url": "https://www.nowcoder.com/jobs/detail/450135"},
        ],
    },
    {
        "phase": "2 · LLM",
        "title": "大模型原理与工程调用",
        "guide": (
            "你要做的是「大模型应用」而不是训练模型——**Transformer 只学到能解释基本工作机制**的程度"
            "（Attention / Token / Embedding 是什么、怎么工作的），不用手推论文。"
            "重点在工程侧：大模型 API 调用、Prompt 工程（写提示词让模型稳定输出）、"
            "Structured Output（用 JSON Schema 让模型输出结构化数据，这是做产品的关键）。"
            "产出：一个 LLM Demo。这一阶段为后面的 Tool Calling / Agent 打基础。"
        ),
        "job_reqs": [
            "熟悉大模型 API 调用（通义千问 / 讯飞 / 豆包 / OpenAI 等）",
            "Prompt Engineering 是高频考点",
            "结构化输出（JSON Schema）+ Function Call / Tool Calling 是 Agent 岗位核心能力",
            "面试常问：Attention 是什么？为什么需要它？",
        ],
        "sources": [
            {"title": "CSDN · AI 大模型应用开发实习｜找岗 + 面试真题 + 面经总结", "url": "https://blog.csdn.net/2401_82753448/article/details/161522566"},
        ],
    },
    {
        "phase": "3 · RAG",
        "title": "RAG 检索增强生成 · 知识库",
        "guide": (
            "RAG 是「企业级知识库问答」类岗位的**标配**（JD 出现率约 60%）。"
            "学完整链路：文档解析 → Chunk 切分 → Embedding → 向量库检索（可混合 BM25 关键词）"
            "→ 必要时 Rerank 重排 → 拼上下文生成。先做出 PDF 知识库问答 V1，"
            "再做检索质量优化实验（BM25/Hybrid/Rerank/Query Rewrite）。"
            "这一块几乎是面试必考：RAG 是什么、为什么需要 RAG、完整流程怎么讲。"
        ),
        "job_reqs": [
            "构建企业级知识库：向量数据库（Milvus / FAISS / Pinecone，JD 出现率约 40%）",
            "优化文档切分、向量检索、重排、上下文拼装，降低大模型幻觉",
            "面试高频：RAG 流程是什么？为什么需要 RAG？幻觉怎么解决？",
            "项目要有可演示的 RAG 应用（知识库问答），能讲清检索逻辑",
        ],
        "sources": [
            {"title": "牛客网 · AI Agent 应用开发工程师（实习）", "url": "https://www.nowcoder.com/jobs/detail/438214"},
            {"title": "CSDN · AI 大模型应用开发实习｜面经总结", "url": "https://blog.csdn.net/2401_82753448/article/details/161522566"},
        ],
    },
    {
        "phase": "4 · Agent",
        "title": "Agent 智能体 · 本岗位核心",
        "guide": (
            "Agent 是目标岗位的**核心方向**：LangChain 在 JD 出现率约 80%，LangGraph 约 25%。"
            "不要一上来就背框架 API——先从**手写最小 Agent Loop（ReAct）**理解本质："
            "模型生成 → 解析工具调用 → 执行 → 结果回填 → 再生成。然后学 Memory / Workflow / LangGraph"
            "做出多工具 Agent V1，最后掌握 MCP / Tool Registry / 权限与重试，做出**可控、可恢复**的 Agent。"
            "面试官主要看你能不能讲清「Agent 怎么调用工具」和「你的 Agent 是怎么写的」。"
        ),
        "job_reqs": [
            "基于 LangChain / LlamaIndex 搭建智能体架构：任务规划→对话管理→意图识别→工具调用→结果反馈闭环",
            "LangGraph 复杂工作流编排（约 25% 岗位要求）",
            "多智能体协作：任务编排、Agent 间通信、状态流转与上下文管理",
            "面试高频：Agent 是什么？Agent 如何调用工具？",
        ],
        "sources": [
            {"title": "牛客网 · AI Agent 应用开发工程师（实习）", "url": "https://www.nowcoder.com/jobs/detail/438214"},
            {"title": "牛客网 · AI agent 开发（实习）", "url": "https://www.nowcoder.com/jobs/detail/450135"},
        ],
    },
    {
        "phase": "5 · 工程化",
        "title": "工程化落地 · 可观测与评测",
        "guide": (
            "实习要求你能**落地**，不是只会 demo。本阶段学工程能力："
            "Tracing（链路追踪，看一次 Agent 调用到底卡在哪）、Eval（评测，改代码不退化）、"
            "Cost / Latency / Cache（成本与延迟优化）。产出 Agent 评测与可观测性。"
            "有了这一块，你在面试里讲项目时能聊「上线要踩的坑」，而不是只有「功能」。"
        ),
        "job_reqs": [
            "日志追踪、监控告警、MLOps（Kubernetes / OpenTelemetry / Prometheus 等）",
            "能分析 token 成本、延迟并给出优化方案",
            "理解生产环境 Agent 的可靠性问题：重试 / 超时 / 降级 / 缓存",
            "有平台化与运维意识（部分岗位明确要求）",
        ],
        "sources": [
            {"title": "CSDN · 2026 年 AI 应用开发正在疯狂招人（50+ 真实 JD 分析）", "url": "https://gitcode.csdn.net/6a181657662f9a54cb781b93.html"},
        ],
    },
    {
        "phase": "6 · 实习准备",
        "title": "实习冲刺 · 算法 / 八股 / 项目 / 投递",
        "guide": (
            "把前面的积累浓缩成「能过面试」的东西：①**算法** LeetCode Hot 100 + 高频题型"
            "（校招算法标配，目标 150~200 题，重点题二刷）；②**八股** OS/网络/MySQL/Redis/Python"
            "（形成自己的面试笔记）；③**项目** Research Agent / Coding Agent 二选一深挖，"
            "做到 GitHub + Demo + README + 指标齐全、**能被追问**；④**求职** 简历 / 投递 / 面经复盘。"
            "暑期实习 3-4 月集中投递，提前 2-3 个月准备简历。"
        ),
        "job_reqs": [
            "有完整可演示的项目经历：发现问题→设计方案→落地解决→复盘优化全闭环",
            "算法笔试：LeetCode 高频题型（Hot 100 为主）",
            "投递渠道：牛客 / Boss直聘 / 实习僧等；暑期实习 3-4 月集中投递",
            "面试高频：RAG 流程、Agent 工具调用、大模型幻觉、项目深挖",
            "实习薪资参考：AI Agent / 大模型应用开发实习约 200-500 元/天，部分有转正",
        ],
        "sources": [
            {"title": "牛客网 · 怎么找 Agent 开发工作/实习（渠道 + 投递策略）", "url": "https://api-cdn.nowcoder.com/feed/main/detail/6181b6f717024915a1d3056bf66c71c3"},
            {"title": "CSDN · AI 大模型应用开发实习｜找岗 + 面试真题 + 面经总结", "url": "https://blog.csdn.net/2401_82753448/article/details/161522566"},
        ],
    },
]
