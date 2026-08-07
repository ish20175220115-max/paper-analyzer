# 个人论文分析管理智能体

> AI 驱动的学术论文结构化分析工具 —— 输入 Markdown 格式论文，自动生成多维度分析报告。

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com/)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-purple)](https://www.deepseek.com/)

---

## 🎯 产品定位

**目标用户**：高校学生、教师、科研工作者

**核心场景**：将个人收集的优秀期刊论文（Markdown 格式）输入系统，AI 自动按照用户选择的分析维度生成结构化分析报告，帮助用户快速提取论文核心价值，积累个人学术知识库。

**MVP 核心链路**：
```
输入 Markdown 论文 → 选择分析维度 → AI 生成报告 → 逐段确认/编辑 → 保存
```

---

## 🚀 快速开始

## 1. 环境准备
```bash
# Python 3.11+
python --version
# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key
```

`.env` 文件内容：
```
DEEPSEEK_API_KEY=sk-your-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

### 3. 启动服务

```bash
uvicorn app.main:app --reload --port 8000
```

浏览器访问 `http://localhost:8000`

### 4. 使用流程

1. 打开 `http://localhost:8000/upload`
2. 粘贴或上传一篇 Markdown 格式论文（至少 200 字符）
3. 勾选分析维度（研究问题、方法论、创新点、局限性、可引用论点）
4. 点击「开始分析」，等待 AI 生成报告（10-30 秒）
5. 逐段查看/编辑分析结果
6. 保存报告

---

## 🧪 Badcase 测试

```bash
# 运行自动化边界测试
python tests/test_badcase.py
```

测试覆盖：
- ✅ 输入校验（空内容、长度限制、格式检测）
- ✅ JSON 解析（正常/异常/边界共 8 种情况）
- ✅ Prompt 构建（维度注入验证）
- ✅ 存储读写（增删查）
- 📋 8 项需手动执行的 AI 输出质量测试（见测试报告）

---

## 📁 项目结构

```
paper-analyzer/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置管理
│   ├── routers/
│   │   ├── analysis.py      # API 路由（分析、保存、查询）
│   │   └── pages.py         # 页面路由
│   ├── services/
│   │   ├── analyzer.py      # 🧠 核心：Prompt 工程 + DeepSeek 调用
│   │   ├── parser.py        # Markdown 校验
│   │   └── storage.py       # JSON 文件存储
│   ├── models/
│   │   ├── schemas.py       # Pydantic 数据模型
│   │   └── templates.py     # 分析维度模板
│   ├── templates/           # Jinja2 HTML 模板
│   └── static/              # 静态资源
├── data/                    # 用户数据（gitignore）
├── tests/
│   └── test_badcase.py      # Badcase 测试矩阵
└── requirements.txt
```

---

## 🔧 技术栈

| 层 | 选型 | 选择理由 |
|---|------|----------|
| Web 框架 | FastAPI | 异步高性能、自动 API 文档、类型安全 |
| 前端 | Jinja2 + 原生 JS | 零构建步骤、聚焦核心逻辑 |
| AI 引擎 | DeepSeek API | 中文能力强、OpenAI 兼容、性价比高 |
| 存储 | JSON 文件 | MVP 零依赖、数据结构透明 |

---

## 📋 分析维度模板

| 维度 | 分析内容 | 适用学科 |
|------|----------|----------|
| **研究问题** | 论文核心问题、研究目标、研究假设、问题重要性论证 | 全学科 |
| **方法论** | 研究方法、数据来源、样本量、实验/调查设计、方法合理性 | 理工/社科 |
| **创新点** | 相对于已有研究的突破、理论/方法/应用层的新贡献 | 全学科 |
| **局限性** | 作者自述局限 + 可观察到的潜在不足 | 全学科 |
| **可引用论点** | 可被其他研究引用的关键结论、数据或观点 | 全学科 |

---

## ⚠️ 当前局限

- 仅支持 Markdown 格式输入（PDF 需手动转换）
- 单次分析上限 10 万字符（约 50 页论文）
- 不支持流式输出（MVP 阶段简化处理）
- 单人单机，无协作功能

---

## 📄 License

MIT
