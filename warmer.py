#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm-plan-warmer: 通用多供应商 & 多账号 LLM / Coding Plan 定时预热保活脚本
支持: 智谱 Zhipu, 商汤 SenseNova Token Plan, DeepSeek, Kimi, 硅基流动等
支持: 单/多 API Key (api_key 数组)、单/多模型 (model 数组)、自定义 trigger_hours / interval_hours
支持: 图像生成类模型 (如商汤 sensenova-u1-fast) 经 /images/generations 接口预热
"""
import os
import sys
import time
import json
import datetime

import httpx
from openai import OpenAI

# 尝试自动加载 .env 文件 (方便本地调试测试)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 默认时区 (UTC+8 北京时间)
TZ_BEIJING = datetime.timezone(datetime.timedelta(hours=8))

def log(msg):
    timestamp = datetime.datetime.now(TZ_BEIJING).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")

def parse_accounts():
    """
    解析多供应商 & 多账号配置
    优先顺序: LLM_ACCOUNTS (JSON) -> ZHIPU_ACCOUNTS (JSON) -> ZHIPU_API_KEY (单账号降级)
    """
    raw_accounts = (
        os.environ.get("LLM_ACCOUNTS", "").strip() or 
        os.environ.get("ZHIPU_ACCOUNTS", "").strip()
    )
    accounts = []

    if raw_accounts:
        try:
            parsed = json.loads(raw_accounts)
            if isinstance(parsed, list):
                accounts = parsed
            elif isinstance(parsed, dict):
                accounts = [parsed]
        except json.JSONDecodeError as e:
            log(f"⚠️ 环境变量 JSON 解析失败，尝试以逗号/管道符解析: {e}")
            for idx, item in enumerate(raw_accounts.split(",")):
                item = item.strip()
                if item:
                    parts = item.split("|")
                    key = parts[0].strip()
                    url = parts[1].strip() if len(parts) > 1 else "https://open.bigmodel.cn/api/coding/paas/v4"
                    model = parts[2].strip() if len(parts) > 2 else "glm-4-flash"
                    accounts.append({
                        "name": f"供应商_{idx+1}",
                        "api_key": key,
                        "base_url": url,
                        "model": model
                    })

    # 单账号降级后备
    if not accounts:
        single_key = os.environ.get("ZHIPU_API_KEY", "").strip()
        if single_key:
            accounts.append({
                "name": "智谱默认账号",
                "api_key": single_key,
                "base_url": os.environ.get("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/coding/paas/v4"),
                "model": os.environ.get("ZHIPU_MODEL", "glm-4-flash"),
                "trigger_hours": [5, 10, 15, 20]
            })

    return accounts

def should_run_acc(acc, now_bjt):
    """
    判断该供应商/账号在当前小时是否需要执行
    优先获取账号自定义的 trigger_hours -> interval_hours -> 默认全匹配
    """
    name = acc.get("name", "未命名账号")
    if not acc.get("enabled", True):
        log(f"⏩ [{name}] 账号处于禁用状态 (enabled: false)，跳过。")
        return False

    current_hour = now_bjt.hour

    # 1. 最高优先级: 获取自定义 trigger_hours (例如: [5, 10, 15, 20])
    trigger_hours = acc.get("trigger_hours")
    if trigger_hours is not None and isinstance(trigger_hours, list):
        if current_hour in trigger_hours:
            log(f"🎯 [{name}] 匹配自定义触发时间段 trigger_hours: {trigger_hours} (当前: {current_hour}点)")
            return True
        else:
            log(f"⏩ [{name}] 当前时间 ({current_hour}点) 不在设定的 trigger_hours {trigger_hours} 内，跳过。")
            return False

    # 2. 次高优先级: 获取 interval_hours (例如: 5 -> [5, 10, 15, 20], 3 -> [0, 3, 6, 9, 12, 15, 18, 21])
    interval_hours = acc.get("interval_hours")
    if interval_hours is not None and isinstance(interval_hours, (int, float)) and interval_hours > 0:
        interval_hours = int(interval_hours)
        computed_hours = list(range(current_hour % interval_hours, 24, interval_hours))
        if interval_hours == 5:
            computed_hours = [5, 10, 15, 20]
        
        if current_hour in computed_hours:
            log(f"🎯 [{name}] 匹配间隔触发点 interval_hours={interval_hours}h (时间点: {computed_hours}, 当前: {current_hour}点)")
            return True
        else:
            log(f"⏩ [{name}] 当前时间 ({current_hour}点) 不在间隔触发点 {computed_hours} 内，跳过。")
            return False

    # 3. 未显式配置独立时间，默认每次任务均触发
    log(f"ℹ️ [{name}] 未显式配置独立时间段，默认本次触发。")
    return True

def send_image_generation(base_url, api_key, model, prompt, size, n):
    """
    调用图像生成类接口 (如商汤 SenseNova sensenova-u1-fast)。
    与 Chat Completions 不同，此类模型走 /images/generations，仅依据 prompt 生成图片，
    不接受图像输入；返回的图片 URL 为 1 小时有效临时链接，预热时无需消费。
    非 2xx 抛出 RuntimeError，交由上层重试逻辑处理。
    """
    url = base_url.rstrip("/") + "/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "prompt": prompt, "n": n}
    if size:
        payload["size"] = size
    # 图像生成通常较慢，给予较长超时 (秒)
    with httpx.Client(timeout=300.0) as http_client:
        resp = http_client.post(url, headers=headers, json=payload)
    if resp.status_code >= 400:
        raise RuntimeError(f"Error code: {resp.status_code} - {resp.text[:300]}")


def ping_single_account(acc):
    name = acc.get("name", "未命名服务商")
    
    # 1. 支持单 API Key 字符串或多 API Key 数组 (api_key 或 api_keys)
    keys_val = acc.get("api_keys") or acc.get("api_key", "")
    if isinstance(keys_val, str):
        keys = [keys_val] if keys_val.strip() else []
    elif isinstance(keys_val, list):
        keys = [k for k in keys_val if isinstance(k, str) and k.strip()]
    else:
        keys = [str(keys_val)] if keys_val else []

    if not keys:
        log(f"❌ [{name}] 未配置有效的 api_key，跳过。")
        return False

    base_url = acc.get("base_url", "https://open.bigmodel.cn/api/coding/paas/v4")
    
    # 2. 支持单模型字符串或多模型数组 (model 或 models)
    models_val = acc.get("models") or acc.get("model", "glm-4-flash")
    if isinstance(models_val, str):
        models = [models_val]
    elif isinstance(models_val, list):
        models = models_val
    else:
        models = [str(models_val)]

    prompt = acc.get("prompt", "hi")

    # 图像生成类模型 (如商汤 SenseNova sensenova-u1-fast) 走独立的 /images/generations 接口，
    # 而非 Chat Completions。此类模型不支持图像输入，仅按 prompt 生成图片。
    image_models_val = acc.get("image_models") or []
    if isinstance(image_models_val, str):
        image_models = [image_models_val]
    elif isinstance(image_models_val, list):
        image_models = [m for m in image_models_val if isinstance(m, str)]
    else:
        image_models = []
    image_prompt = acc.get("image_prompt", "a simple keep-alive test image")
    image_size = acc.get("image_size", "2752x1536")
    image_n = int(acc.get("image_n", 1))

    total_tasks = len(keys) * len(models)
    log(f"▶️ 开始预热 [{name}] (Key 数量: {len(keys)}, 模型数量: {len(models)}, 总预热任务数: {total_tasks}, BaseURL: {base_url})")

    account_success = True

    for key_idx, api_key in enumerate(keys, 1):
        masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "***"
        
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
        except Exception as e:
            log(f"❌ [{name}] (Key {key_idx}/{len(keys)}: {masked_key}) 客户端初始化失败: {e}")
            account_success = False
            continue

        for model_name in models:
            max_retries = 3
            retry_delay = 20
            model_success = False

            for attempt in range(1, max_retries + 1):
                try:
                    if model_name in image_models:
                        log(f"  🚀 [{name}] (Key {key_idx}/{len(keys)}: {masked_key} | 图像模型: {model_name}) 第 {attempt} 次发送图像生成预热请求 (接口: /images/generations)...")
                        send_image_generation(base_url, api_key, model_name, image_prompt, image_size, image_n)
                    else:
                        log(f"  🚀 [{name}] (Key {key_idx}/{len(keys)}: {masked_key} | 模型: {model_name}) 第 {attempt} 次发送预热请求...")
                        client.chat.completions.create(
                            model=model_name,
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=1
                        )
                    log(f"  ✅ [{name}] (Key {key_idx}/{len(keys)}: {masked_key} | 模型: {model_name}) 预热成功！已激活刷新/冷却窗口。")
                    model_success = True
                    break

                except Exception as e:
                    err_str = str(e)
                    log(f"  ⚠️ [{name}] (Key {key_idx}/{len(keys)}: {masked_key} | 模型: {model_name}) 第 {attempt} 次反馈: {err_str}")
                    
                    if "429" in err_str or "rate limit" in err_str.lower():
                        log(f"  ℹ️ [{name}] (Key {key_idx}/{len(keys)} | 模型: {model_name}) 提示: 触发 Rate Limit，可能处于旧窗口或超额中。")
                    
                    if attempt < max_retries:
                        log(f"  ⏳ [{name}] (Key {key_idx}/{len(keys)} | 模型: {model_name}) 等待 {retry_delay} 秒后重试...")
                        time.sleep(retry_delay)
                    else:
                        log(f"  ⚠️ [{name}] (Key {key_idx}/{len(keys)} | 模型: {model_name}) 达到最大重试次数，该任务流程结束。")

            if not model_success:
                account_success = False

            time.sleep(1) # 请求间的微小间隔

    return account_success

def main():
    now_bjt = datetime.datetime.now(TZ_BEIJING)
    log("==================================================")
    log(f" Starting Universal LLM Warmer Task ({now_bjt.strftime('%Y-%m-%d %H:%M:%S')} BJT)")
    log("==================================================")
    
    accounts = parse_accounts()
    if not accounts:
        log("❌ 错误: 未检测到任何服务商配置！请在 .env 或 Secrets 中配置 LLM_ACCOUNTS。")
        sys.exit(1)

    log(f"📋 共检测到 {len(accounts)} 个服务商/账号配置，正在评估各自的时间表...\n")
    
    success_count = 0
    executed_count = 0

    for idx, acc in enumerate(accounts, 1):
        log(f"--- [账号配置 {idx}/{len(accounts)}: {acc.get('name', '未命名')}] ---")
        if should_run_acc(acc, now_bjt):
            executed_count += 1
            if ping_single_account(acc):
                success_count += 1
            time.sleep(2)

    log("\n==================================================")
    log(f" 本轮调度结束! 实际触发配置数: {executed_count}/{len(accounts)}, 成功: {success_count}/{executed_count if executed_count > 0 else 1}")
    log("==================================================")

if __name__ == "__main__":
    main()
