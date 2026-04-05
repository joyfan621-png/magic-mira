# Gemma 4 E2B 本地部署设计

## 目标

在当前这台 Apple Silicon Mac 上部署一个可本地调用的 `Gemma 4 E2B` 服务，方便后续“镜子虾”项目通过本地 HTTP API 访问模型。

## 约束

- 机器为 macOS arm64
- 当前 Python 为 3.9.6，不适合作为本次部署核心依赖栈
- 需要一个稳定的本地服务接口，而不是一次性脚本

## 方案对比

### 方案 A：Transformers + PyTorch

优点：
- 接近官方 Hugging Face 用法
- 代码可控

缺点：
- 在 Mac 上部署和调优更重
- 额外要处理环境、设备映射和服务封装

### 方案 B：Ollama + `gemma4:e2b`（推荐）

优点：
- 对本地运行大模型最省心
- 自带本地 HTTP API
- 后续 Agent 集成成本最低

缺点：
- 不是最“原始官方”调用方式
- 依赖 Ollama 对模型的支持

### 方案 C：LM Studio

优点：
- UI 友好

缺点：
- 自动化和项目集成不如 Ollama 顺手

## 决策

采用 `Ollama + gemma4:e2b`。

## 交付

- 本机安装或确认 Ollama
- 拉取 `gemma4:e2b`
- 运行一次本地推理验证
- 给出后续项目调用方式说明
