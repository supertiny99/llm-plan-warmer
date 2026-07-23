# 通用多供应商 LLM & Coding Plan 自动预热工具 (GitHub Actions)

本项目用于通过 GitHub Actions 定时触发各类大模型供应商 (智谱 Coding Plan / DeepSeek / Kimi / 硅基流动 / 阿里云 DashScope / OpenAI 等) 的 API，以保持 5 小时刷新窗口的连续覆盖与保活。

## 🌟 特性

- **通用 OpenAI 协议支持**：支持任何兼容 OpenAI 接口标准的 LLM 供应商。
- **多供应商 & 多账号**：可在 Secrets 中配置任意多个服务商/账号/模型组合，单次任务自动遍历触发。
- **防止临界冲突**：自动添加 3 分钟缓冲与 429 Rate Limit 自动重试机制。
- **全自动打卡**：基于 GitHub Actions，按工作日（周一至周五）北京时间 `05:33`, `10:33`, `15:33`, `20:33` 自动触发。
- **手动触发支持**：支持在 GitHub Actions 页面随时手动一键触发测试。

## 🚀 多供应商配置示例

在 GitHub 仓库 **Settings** -> **Secrets and variables** -> **Actions** 中添加 Secret **`LLM_ACCOUNTS`**：

```json
[
  {
    "name": "智谱 Coding Plan 主账号",
    "api_key": "your-zhipu-api-key",
    "base_url": "https://open.bigmodel.cn/api/paas/v4/",
    "model": "glm-4-flash"
  },
  {
    "name": "DeepSeek API",
    "api_key": "your-deepseek-api-key",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat"
  },
  {
    "name": "Kimi (Moonshot)",
    "api_key": "your-kimi-api-key",
    "base_url": "https://api.moonshot.cn/v1",
    "model": "moonshot-v1-8k"
  },
  {
    "name": "硅基流动 SiliconFlow",
    "api_key": "your-siliconflow-api-key",
    "base_url": "https://api.siliconflow.cn/v1",
    "model": "Qwen/Qwen2.5-7B-Instruct"
  }
]
```

## ⏱️ 执行时间表 (北京时间 BJT)

| 节点 | 北京时间 | UTC 时间 (Cron) | 说明 |
| :--- | :--- | :--- | :--- |
| **预热 1** | **05:33** | `33 21 * * 0-4` | 09:00 上班开工预热 |
| **预热 2** | **10:33** | `33 2 * * 1-5` | 10:33 上午刷新 |
| **预热 3** | **15:33** | `33 7 * * 1-5` | 15:33 下午刷新 |
| **预热 4** | **20:33** | `33 12 * * 1-5` | 20:33 晚间/下班刷新 |
