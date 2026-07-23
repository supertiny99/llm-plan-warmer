# 智谱 AI Coding Plan 多账号自动预热工具 (GitHub Actions)

本项目用于通过 GitHub Actions 定时触发智谱 AI Coding Plan，保持 5 小时刷新窗口的连续覆盖与高效利用。

## 🌟 特性

- **支持多账号**：可在 Secrets 中配置多个账号，一次运行自动依次预热所有账号。
- **防止临界冲突**：自动添加 3 分钟延迟与 429 自动重试逻辑。
- **全自动打卡**：基于 GitHub Actions，按工作日（周一至周五）北京时间 `05:33`, `10:33`, `15:33`, `20:33` 自动触发。
- **手动触发支持**：支持在 GitHub Actions 页面随时手动一键触发测试。

## 🚀 配置说明

### 1. 将本项目推送到 GitHub

把当前仓库推送到你的 GitHub **私有仓库 (Private Repository)**。

### 2. 配置 GitHub Secrets

在你的 GitHub 仓库页面，点击 **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**：

#### 单账号配置（简单）：
- **`ZHIPU_API_KEY`**: 你的智谱 Coding Plan API Key。
- *(可选)* **`ZHIPU_BASE_URL`**: 默认 `https://open.bigmodel.cn/api/paas/v4/`。
- *(可选)* **`ZHIPU_MODEL`**: 默认 `glm-4-flash`。

#### 多账号配置（推荐）：
新增一个名为 **`ZHIPU_ACCOUNTS`** 的 Secret，内容为 JSON 数组字符串：

```json
[
  {
    "name": "工作主账号",
    "api_key": "your-zhipu-api-key-1",
    "base_url": "https://open.bigmodel.cn/api/paas/v4/",
    "model": "glm-4-flash"
  },
  {
    "name": "个人副账号",
    "api_key": "your-zhipu-api-key-2",
    "base_url": "https://open.bigmodel.cn/api/paas/v4/",
    "model": "glm-4-flash"
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
