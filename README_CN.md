<p align="center">
  <h1 align="center">MAARS</h1>
  <p align="center"><b>多智能体自动化研究系统</b></p>
  <p align="center">从研究想法到完整论文——全自动、端到端。</p>
  <p align="center">
    中文 · <a href="README.md">English</a>
  </p>
</p>

---

MAARS 接受一个模糊的研究想法（或 Kaggle 比赛链接），通过三阶段流水线 **Refine -> Research -> Write** 产出结构化研究产物和完整的 `paper.md`。

每个阶段由 Python runtime 编排，LLM Agent 执行开放性工作——文献调研、代码实验、论文撰写、同行评审——全程自主运行，迭代自我改进。

## 流水线

```mermaid
graph LR
    subgraph Refine
        E[Explorer] <--> C[Critic]
    end
    subgraph Research
        Cal[Calibrate] --> Str[Strategy] --> Dec[Decompose] --> Exec[Execute] <--> Ver[Verify] --> Eval[Evaluate]
        Eval -.->|strategy update| Str
    end
    subgraph Write
        W[Writer] <--> R[Reviewer]
    end
    Refine -->|refined_idea| Research -->|artifacts| Write -->|paper.md| Final((Done))
```

- **Refine**：Explorer 调研文献并起草提案；Critic 评审并推动更强的表述。迭代直到 Critic 满意。
- **Research**：将提案分解为原子任务，在 Docker 沙箱中并行执行，验证产出，评估结果——通过策略更新进行多轮迭代。
- **Write**：Writer 读取所有研究产出撰写完整论文；Reviewer 评审并驱动修订。

## 快速开始

**环境要求：** Python 3.10+、Docker 已运行、[Gemini API 密钥](https://aistudio.google.com/apikey)

```bash
git clone https://github.com/dozybot001/MAARS.git && cd MAARS
bash start.sh
```

首次运行时，`start.sh` 会：
1. 创建虚拟环境并安装依赖
2. 从 `.env.example` 生成 `.env`——填入你的 `MAARS_GOOGLE_API_KEY`
3. 构建 Docker 沙箱镜像
4. 在 **http://localhost:8000** 启动服务

然后在输入框粘贴你的研究想法或 Kaggle 链接，点击 Start。

## Kaggle 模式

粘贴 Kaggle 比赛链接——MAARS 自动提取比赛 ID、下载数据、跳过 Refine 阶段。

## 配置

所有变量使用 `MAARS_` 前缀，配置于 `.env`：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MAARS_GOOGLE_API_KEY` | — | **必填。** Gemini API 密钥 |
| `MAARS_GOOGLE_MODEL` | `gemini-3-flash-preview` | LLM 模型 ID |
| `MAARS_API_CONCURRENCY` | `1` | LLM 最大并发数 |
| `MAARS_OUTPUT_LANGUAGE` | `Chinese` | 提示词/输出语言（`Chinese` 或 `English`） |
| `MAARS_RESEARCH_MAX_ITERATIONS` | `3` | Research 最大评估轮数 |
| `MAARS_TEAM_MAX_DELEGATIONS` | `10` | Refine/Write 最大迭代轮数 |
| `MAARS_KAGGLE_API_TOKEN` | — | 可选；也可用 `~/.kaggle/kaggle.json` |
| `MAARS_DATASET_DIR` | `data/` | 沙箱挂载的数据集目录 |
| `MAARS_DOCKER_SANDBOX_IMAGE` | `maars-sandbox:latest` | 代码执行 Docker 镜像 |
| `MAARS_DOCKER_SANDBOX_TIMEOUT` | `600` | 单容器超时（秒） |
| `MAARS_DOCKER_SANDBOX_MEMORY` | `4g` | 容器内存上限 |
| `MAARS_DOCKER_SANDBOX_CPU` | `1.0` | 容器 CPU 配额 |
| `MAARS_DOCKER_SANDBOX_NETWORK` | `true` | 沙箱内是否联网 |

## 产出结构

每次运行生成一个 session 目录：

```
results/{session}/
+-- refined_idea.md          # Refine 产出
+-- proposals/               # Refine 各版提案
+-- critiques/               # Refine 各轮评审
+-- calibration.md           # Research：任务粒度定义
+-- strategy/                # Research：策略版本
+-- tasks/                   # Research：任务产出
+-- artifacts/               # Research：代码、图表、数据
+-- evaluations/             # Research：评估版本
+-- drafts/                  # Write 各版草稿
+-- reviews/                 # Write 各轮评审
+-- paper.md                 # 最终论文
+-- meta.json                # Token 用量、分数
```

## 文档

| 文档 | 内容 |
|------|------|
| [架构概览](docs/CN/architecture.md) | 系统概览、SSE 协议、存储结构 |
| [Refine & Write](docs/CN/refine-write.md) | IterationState 模式、双 Agent 循环详情 |
| [Research](docs/CN/research.md) | 任务分解、并行执行、评估循环 |

## 技术栈

- **后端**：Python、FastAPI、Agno（Agent 框架）、Gemini（内置 Google Search）
- **前端**：原生 JS、SSE 流式推送、marked.js 渲染 Markdown
- **执行**：Docker 沙箱，可配置资源限制
- **存储**：文件型 Session DB（JSON + Markdown）

## 社区

[贡献指南](.github/CONTRIBUTING.md) · [行为准则](.github/CODE_OF_CONDUCT.md) · [安全策略](.github/SECURITY.md)

## 许可证

MIT
