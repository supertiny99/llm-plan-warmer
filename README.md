# llm-plan-warmer (通用多供应商 LLM & Coding Plan 自动预热保活工具)

`llm-plan-warmer` 是一个轻量级、全自动的预热保活工具，通过服务器 cron 一键部署或 GitHub Actions 定时触发各类大模型供应商 (智谱 Coding Plan / 商汤 SenseNova Token Plan / DeepSeek / Kimi / 硅基流动 / 阿里云 DashScope / OpenAI 等) 的 API，以维持 5 小时（或自定义窗口）刷新周期的连续覆盖与最高利用率，并自动避开工作日峰时三倍消耗时段。

## 🌟 特性

- **通用 OpenAI 协议支持**：支持任何兼容 OpenAI 接口标准的 LLM 供应商。
- **多 Key & 多模型组合矩阵**：`api_key` 与 `model` 均支持配置字符串或字符串数组。配置数组时自动按 `Key ✖️ Model` 矩阵批量发送预热，完美支持一个供应商下挂载多个账号/多套套餐。
- **图像生成模型支持**：商汤 `sensenova-u1-fast` 等图像类模型经独立 `/images/generations` 接口预热（通过 `image_models` 标记），可与 Chat 模型混合配置于同一账号。
- **独立时间表配置（优先获取）**：每个供应商/账号/模型均可单独配置 `trigger_hours`（如 `[8, 13, 18]`）或 `interval_hours`（间隔小时数）。
- **峰时三倍消耗避让**：默认调度锚点全部避开工作日 14:00-18:00 峰时；配合 `avoid_weekday_peak` 防呆兜底，即使 `trigger_hours` 误配进峰时也会拒发。
- **20 分钟错峰缓冲**：相邻锚点间隔 5h20m（而非整 5 小时），确保上一窗口已过期、锚点必定开出新窗口，消除"请求打进旧窗口"的整点竞态。
- **429 Rate Limit 自动重试**、`--dry-run` 配置校验、失败推送通知（`WARMER_NOTIFY_URL`）与手动触发支持。

## 📐 调度设计（5 小时窗口 × 峰时避让）

针对"5 小时滚动刷新窗口 + 工作日 14:00-18:00 三倍消耗"的套餐（如智谱 GLM Coding Plan），默认调度按以下推导设计：

**核心算术**：窗口 5 小时无法整除一天（24 ÷ 5 = 4.8），固定每日锚点下每天最多 4 个有效锚点 = 20 小时保活覆盖，必然留 4 小时的结构性空洞。按工作时间 8:30-11:30 / 13:30-17:30 对齐、用满 4 个锚点后的默认调度：

| 锚点（北京时间） | 开启窗口 | 覆盖场景 |
| :--- | :--- | :--- |
| 07:20 | 07:20 – 12:20 | 上午工作段 8:30-11:30（全 1x），午休前可清窗口余额 |
| 12:40 | 12:40 – 17:40 | 覆盖下午工作段 13:30-17:30；12:40-14:00 全 1x，午休挂批量任务做额度套利 |
| 18:00 | 18:00 – 23:00 | 出峰整点即满血（全 1x），晚间重度使用 |
| 23:20 | 23:20 – 04:20 | 接住晚间窗口 23:00 过期后的夜间刷新，深夜时段保活 |

设计要点：

- **相邻锚点间隔 5h20m**：窗口开于锚点时刻、5 小时后过期。若下一锚点恰好间隔整 5 小时，会因 GitHub Actions 调度抖动产生"打进未过期旧窗口"的竞态（锚点被吞、白白消耗额度）。20 分钟缓冲远大于常规调度抖动，每个锚点必定开出新窗口。
- **链式刚性**：锚点链环环相扣（每环 +5h20m），单独前移某一环会撞上未过期的旧窗口。晚间锚点的下限是出峰时刻 18:00，因此夜间锚点最早只能到 23:20——本调度已取该最早值。
- **结构性空洞仅剩 04:20 – 07:20**（清晨）：空洞期的第一个真实请求会自动开启全新满额窗口，近乎无害。
- **cron 使用 UTC**：北京时间 = UTC+8，`warmer.yml` 中 `40 4 * * *` 即北京 12:40。若配置了默认锚点之外的 `trigger_hours`，需在 workflow 中同步增加对应 cron 行，否则该小时永远不会被评估。
- **周一周日通用**：锚点不落峰时，周末同样有效，无需区分工作日/周末。

## 🖥️ 服务器一键部署（推荐）

部署到自有服务器的系统 cron 上，触发时刻精确到秒级，不受 GitHub Actions 调度延迟（实测 15-75 分钟）与偶发丢调度影响。安装器会自动：克隆仓库 → 创建 venv 并安装依赖 → 生成 `.env` → 按服务器时区换算锚点并写入 crontab → 运行 `--dry-run` 校验配置。

```bash
# 方式一：一行命令安装（随后编辑 ~/llm-plan-warmer/.env 填入真实 Key）
curl -fsSL https://raw.githubusercontent.com/supertiny99/llm-plan-warmer/master/install.sh | bash

# 方式二：带智谱 API Key 直装，装完即用
curl -fsSL https://raw.githubusercontent.com/supertiny99/llm-plan-warmer/master/install.sh | bash -s -- --key <你的智谱API Key>

# 方式三：手动克隆后安装
git clone https://github.com/supertiny99/llm-plan-warmer.git && cd llm-plan-warmer && bash install.sh
```

要求：Python ≥ 3.8 + `git` 或 `curl`（Linux/macOS 均可）；服务器需常开（睡眠/关机期间锚点会丢失）。

常用操作：

| 操作 | 命令 |
| :--- | :--- |
| 手动预热一次 | `~/llm-plan-warmer/run.sh`（日志在 `~/llm-plan-warmer/logs/warmer.log`） |
| 校验配置（不发请求） | `cd ~/llm-plan-warmer && venv/bin/python warmer.py --dry-run` |
| 更新到最新版 | 重新运行安装命令（`.env` 保持不动，crontab 幂等刷新） |
| 预览 cron 行 | `bash install.sh --print-cron` |
| 卸载 | `bash ~/llm-plan-warmer/install.sh --uninstall`（仅摘除 crontab，不删文件） |

说明与注意事项：

- **时区自动换算**：`warmer.py` 按北京时间整点匹配 `trigger_hours`，安装器读取服务器时区把锚点 07:20/12:40/18:00/23:20 (BJT) 换算成本地时间写入 crontab；国内服务器（UTC+8）写入的就是北京时间本身。
- **夏令时提醒**：服务器时区若使用夏令时（如欧美时区），换季后锚点会偏移 1 小时导致静默跳过，请重跑 `install.sh` 刷新 crontab。
- **失败通知（可选，服务器部署推荐）**：在 `.env` 中配置 `WARMER_NOTIFY_URL`（支持 Bark / Server酱 / 通用 webhook，见 `.env.example` 注释），预热请求失败或全部账号未触发（时区漂移信号）时推送一次。
- **国内加速**：依赖安装前可 `export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple` 走清华镜像。
- 自定义了默认之外的 `trigger_hours`？用 `bash install.sh --anchors "HH:MM,..."` 生成对应的 cron 行，并保持与 `trigger_hours` 小时一致。

## 🚀 GitHub Actions 部署（免服务器备选）

零服务器方案：cron 延迟实测 15-75 分钟（延迟跨锚点小时会被脚本静默跳过）且偶发丢调度，稳定性弱于服务器部署，胜在免运维。

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
    "trigger_hours": [7, 12, 18, 23],
    "avoid_weekday_peak": true
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
      "glm-5.2"
    ],
    "image_models": ["sensenova-u1-fast"],
    "trigger_hours": [7, 12, 18, 23]
  },
  {
    "name": "DeepSeek API (每日早晚各一次)",
    "api_key": "your-deepseek-api-key",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "trigger_hours": [8, 18]
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
| **`trigger_hours`** | Array[int] | **【最高优先级时间表】** 指定哪些小时触发（北京时间 0~23h）。推荐 `[7, 12, 18, 23]`（需与 workflow cron 行匹配） |
| **`interval_hours`** | int | **【次高优先级时间表】** 设定固定间隔小时数；`5` 会使用工作时段对齐锚点 `[7, 12, 18, 23]` |
| **`avoid_weekday_peak`** | bool | 峰时防呆兜底（默认 `false`）。设为 `true` 后，工作日 14:00-18:00 (北京时间) 内一律拒发，避免误触发三倍消耗 |
| **`enabled`** | bool | 开关控制（`true`/`false`），设为 `false` 可暂停该配置段预热 |
| **`image_models`** | Array[String] | 需要走 `/images/generations` 图像生成接口的模型名列表（如 `["sensenova-u1-fast"]`）。未列入的模型仍走 Chat Completions |
| **`image_prompt`** | String | 图像生成预热的 prompt（默认极简测试图，仅为刷新冷却窗口，无需消费生成结果） |
| **`image_size`** | String | 图像尺寸（如 `2752x1536`，需为供应商支持的合法尺寸） |
| **`image_n`** | int | 单次生成图片数量（默认 `1`） |
