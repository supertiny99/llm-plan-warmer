# llm-plan-warmer (通用多供应商 LLM & Coding Plan 自动预热保活工具)

`llm-plan-warmer` 是一个轻量级、全自动的预热保活工具，通过 GitHub Actions 定时触发各类大模型供应商 (智谱 Coding Plan / 商汤 SenseNova Token Plan / DeepSeek / Kimi / 硅基流动 / 阿里云 DashScope / OpenAI 等) 的 API，以维持 5 小时（或自定义窗口）刷新周期的连续覆盖与最高利用率。

## 🌟 特性

- **通用 OpenAI 协议支持**：支持任何兼容 OpenAI 接口标准的 LLM 供应商。
- **多 Key & 多模型组合矩阵**：`api_key` 与 `model` 均支持配置字符串或字符串数组。配置数组时自动按 `Key ✖️ Model` 矩阵批量发送预热，完美支持一个供应商下挂载多个账号/多套套餐。
- **图像生成模型支持**：商汤 `sensenova-u1-fast` 等图像类模型经独立 `/images/generations` 接口预热（通过 `image_models` 标记），可与 Chat 模型混合配置于同一账号。
- **独立时间表配置（优先获取）**：每个供应商/账号/模型均可单独配置 `trigger_hours`（如 `[5, 10, 15, 20]`）或 `interval_hours`（间隔小时数）。
- **防止临界冲突**：自动添加 3 分钟缓冲与 429 Rate Limit 自动重试机制。
- **手动触发支持**：支持在 GitHub Actions 页面随时手动一键触发测试。

## 🚀 多供应商 & 多 Key 配置示例

在 GitHub 仓库 **Settings** -> **Secrets and variables** -> **Actions** 中添加 Secret **`LLM_ACCOUNTS`**：

```json
[
  {
    "name": "智谱 Coding Plan (多个 Key 批量预热)",
    "api_key": [
      "your-zhipu-api-key-1",
      "your-zhipu-api-key-2"
    ],
    "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
    "model": "glm-4.7",
    "trigger_hours": [5, 10, 15, 20]
  },
  {
    "name": "商汤 SenseNova Token Plan (多 Key ✖️ 多模型交叉组合)",
    "api_key": [
      "your-sensenova-key-1",
      "your-sensenova-key-2"
    ],
    "base_url": "https://token.sensenova.cn/v1",
    "model": [
      "sensenova-6.7-flash-lite",
      "sensenova-u1-fast",
      "deepseek-v4-flash",
      "gml-5.2"
    ],
    "image_models": ["sensenova-u1-fast"],
    "trigger_hours": [5, 10, 15, 20]
  },
  {
    "name": "DeepSeek API (3小时窗口)",
    "api_key": "your-deepseek-api-key",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "trigger_hours": [6, 9, 12, 15, 18, 21]
  }
]
```

### ⚙️ 参数配置说明

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| **`name`** | String | 供应商/账号配置标识名称 |
| **`api_key`** (或 `api_keys`) | String / Array[String] | **支持单 Key 或 Key 数组**。如果是数组，会自动对每个 Key 独立发起预热 |
| **`base_url`** | String | OpenAI 兼容接口地址 (例如商汤 `https://token.sensenova.cn/v1`) |
| **`model`** (或 `models`) | String / Array[String] | **支持单模型或模型数组**。如果是数组，会自动对每个模型触发一次请求开启冷却 |
| **`trigger_hours`** | Array[int] | **【最高优先级时间表】** 指定哪些点触发（北京时间 0~23h）。例如 `[5, 10, 15, 20]` |
| **`interval_hours`** | int | **【次高优先级时间表】** 设定固定间隔小时数。例如 `4` 代表每 4 小时触发一次 |
| **`enabled`** | bool | 开关控制（`true`/`false`），设为 `false` 可暂停该配置段预热 |
| **`image_models`** | Array[String] | 需要走 `/images/generations` 图像生成接口的模型名列表（如 `["sensenova-u1-fast"]`）。未列入的模型仍走 Chat Completions |
| **`image_prompt`** | String | 图像生成预热的 prompt（默认极简测试图，仅为刷新冷却窗口，无需消费生成结果） |
| **`image_size`** | String | 图像尺寸（如 `2752x1536`，需为供应商支持的合法尺寸） |
| **`image_n`** | int | 单次生成图片数量（默认 `1`） |
