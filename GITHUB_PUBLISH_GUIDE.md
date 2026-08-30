# ==========================================
# Agent学习OS_Web版 - GitHub 部署与开源准备清单
# ==========================================

本文件用于指导并记录将 **「Agent学习OS Web版」** 完整、安全地发布到 GitHub 仓库的操作步骤与修改细节。

---

## 1. 桌面与项目路径识别情况

- **桌面快捷方式**：
  - `C:\Users\lenovo\Desktop\Agent学习OS.lnk`
  - 指向：`C:\Users\lenovo\Desktop\Learn\Agent学习OS_Web版\.venv\Scripts\pythonw.exe` 启动后台无窗口服务（`tools/launch_hidden.py`）
- **核心项目源码目录**：
  - `C:\Users\lenovo\Desktop\Learn\Agent学习OS_Web版`

---

## 2. 重点识别的 Markdown 文档与状态

| 文件路径 | 说明与当前状态 | 建议操作 |
|---|---|---|
| `README.md` | 项目主文档，包含功能介绍、架构、启动指南、多模型配置、技术栈等，结构清晰。 | ✅ 补充 GitHub 徽章、开源协议与一键部署说明，保留。 |
| `CLAUDE.md` | 本地 AI Agent 开发指南、开发进度与架构设计断点记录。 | ⚠️ 建议保留供开源开发者或继续使用 Claude Code 时参考。 |
| `课程验证报告.md` | 记录 7 门配套课程（B站/LeetCode）通过官方 API 核验真实播放量与替换过程的报告。 | ✅ 极佳的技术与真实性佐证，建议保留。 |

---

## 3. 🚨 开源前安全与脱敏检查（必须处理）

1. **API Key 泄露防护**：
   - 检查发现 `backend/config.json` 中包含真实的私有 API Key。
   - **操作**：
     - 将 `backend/config.json` 添加到 `.gitignore`。
     - 提供 `backend/config.example.json` 作为开源模板，去除真实 Key。
2. **敏感与临时数据脱敏**：
   - `backend/data/*.db`（用户个人学习数据库与打卡记录）
   - `backend/data/*.log`（运行日志）
   - `backups/*.db`（历史数据库备份）
   - `backend/server_8001.log`
   - `.venv/` 与 `frontend/node_modules/`、`frontend/dist/`
   - 以上均需加入 `.gitignore`，防止个人数据与庞大二进制包上传。

---

## 4. 新增与优化的文件规范

### 4.1 `.gitignore` 规则（推荐新建）
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
env/
venv/
*.log

# Node & Frontend
node_modules/
frontend/dist/
.npm
.vite/

# 敏感与本地配置
backend/config.json
!backend/config.example.json

# 本地数据与备份
backend/data/*.db
backend/data/*.log
backend/server_8001.log
backups/
.pytest_cache/

# 操作系统/编辑器
.DS_Store
Thumbs.db
.vscode/
.idea/
```

### 4.2 配置模板 `backend/config.example.json`
```json
{
  "provider": "deepseek",
  "deepseek_base_url": "https://api.deepseek.com",
  "deepseek_model": "deepseek-chat",
  "deepseek_api_key": "",
  "openai_base_url": "https://api.openai.com/v1",
  "openai_model": "gpt-4o-mini",
  "openai_api_key": "",
  "anthropic_base_url": "https://api.anthropic.com/v1",
  "anthropic_model": "claude-sonnet-5",
  "anthropic_api_key": ""
}
```

---

## 5. 上传到 GitHub 的标准步骤

1. 在项目根目录 `C:\Users\lenovo\Desktop\Learn\Agent学习OS_Web版` 下初始化 Git：
   ```bash
   git init
   ```
2. 创建 `.gitignore` 并确保 `backend/config.json` 不被追踪。
3. 添加并提交文件：
   ```bash
   git add .
   git commit -m "feat: Initial commit for Agent Study OS Web"
   ```
4. 关联远程 GitHub 仓库并推送：
   ```bash
   git branch -M main
   git remote add origin <你的GitHub仓库URL>
   git push -u origin main
   ```
