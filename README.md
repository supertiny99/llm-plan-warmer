# llm-plan-warmer (通用多供应商 LLM & Coding Plan 自动预热保活工具)

`llm-plan-warmer` 是一个轻量级、全自动的预热保活工具，通过 GitHub Actions 定时触发各类大模型供应商 (智谱 Coding Plan / DeepSeek / Kimi / 硅基流动 / 阿里云 DashScope / OpenAI 等) 的 API，以维持 5 小时刷新窗口的连续覆盖与最高利用率。

## 🌟 特性

- **通用 OpenAI 协议支持**：支持任何兼容 OpenAI 接口标准的 LLM 供应商。
- **独立时间表配置（优先获取）**：每个供应商/账号/模型均可单独配置 `trigger_hours`（如 `[5, 10, 15, 20]`）或 `interval_hours`（间隔小时数）。
- **多供应商 & 多账号**：可在 Secrets 中配置任意多个服务商/账号/模型组合，单次任务自动遍历评估与触发。
- **防止临界冲突**：自动添加 3 分钟缓冲与 429 Rate Limit 自动重试机制。
- **手动触发支持**：支持在 GitHub Actions 页面随时手动一键触发测试。

## 🚀 多供应商 & 独立时间表配置示例

在 GitHub 仓库 **Settings** -> **Secrets and variables** -> **Actions** 中添加 Secret **`LLM_ACCOUNTS`**：

```json
[
  {
    "name": "智谱 Coding Plan (5小时窗口)",
    "api_key": "your-zhipu-api-key",
    "base_url": "https://open.bigmodel.cn/api/paas/v4/",
    "model": "glm-4-flash",
    "trigger_hours": [5, 10, 15, 20]
  },
  {
    "name": "DeepSeek API (3小时窗口)",
    "api_key": "your-deepseek-api-key",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "trigger_hours": [6, 9, 12, 15, 18, 21]
  },
  {
    "name": "Kimi (Moonshot) (按间隔自动计算)",
    "api_key": "your-kimi-api-key",
    "base_url": "https://api.moonshot.cn/v1",
    "model": "moonshot-v1-8k",
    "interval_hours": 4
  },
  {
    "name": "硅基流动 (全时段每次均触发)",
    "api_key": "your-siliconflow-api-key",
    "base_url": "https://api.siliconflow.cn/v1",
    "model": "Qwen/Qwen2.5-7B-Instruct"
  }
]
```

### ⚙️ 时间参数配置说明

| 字段 | 类型 | 说明 | 优先级 |
| :--- | :--- | :--- | :--- |
| **`trigger_hours`** | Array[int] | **【最高优先级】** 指定哪些点触发（北京时间 0~23h）。例如 `[5, 10, 15, 20]` | 1 (最高) |
| **`interval_hours`** | int | **【次高优先级】** 设定固定间隔小时数。例如 `4` 代表每 4 小时触发一次 | 2 |
| *(未配置时间)* | - | 默认只要定时轮询任务运行（例如手动触发或每小时轮询）即进行预热 | 3 |
| **`enabled`** | bool | 开关控制（`true`/`false`），设为 `false` 可暂停该账号预热 | - |
