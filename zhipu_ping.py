#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智谱 AI Coding Plan 5小时定时预热/保活脚本 (支持多账号 & GitHub Actions)
"""
import os
import sys
import time
import json
import datetime
from openai import OpenAI

def log(msg):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")

def parse_accounts():
    """
    解析多账号环境变量
    优先解析 ZHIPU_ACCOUNTS (JSON 字符串)，降级解析 ZHIPU_API_KEY (单账号)
    """
    raw_accounts = os.environ.get("ZHIPU_ACCOUNTS", "").strip()
    accounts = []

    if raw_accounts:
        try:
            parsed = json.loads(raw_accounts)
            if isinstance(parsed, list):
                accounts = parsed
            elif isinstance(parsed, dict):
                accounts = [parsed]
        except json.JSONDecodeError as e:
            log(f"⚠️ ZHIPU_ACCOUNTS JSON 解析失败，尝试简单分隔符解析: {e}")
            for idx, item in enumerate(raw_accounts.split(",")):
                item = item.strip()
                if item:
                    parts = item.split("|")
                    key = parts[0].strip()
                    url = parts[1].strip() if len(parts) > 1 else "https://open.bigmodel.cn/api/paas/v4/"
                    model = parts[2].strip() if len(parts) > 2 else "glm-4-flash"
                    accounts.append({
                        "name": f"账号_{idx+1}",
                        "api_key": key,
                        "base_url": url,
                        "model": model
                    })

    # 单账号降级后备
    if not accounts:
        single_key = os.environ.get("ZHIPU_API_KEY", "").strip()
        if single_key:
            accounts.append({
                "name": "默认账号",
                "api_key": single_key,
                "base_url": os.environ.get("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"),
                "model": os.environ.get("ZHIPU_MODEL", "glm-4-flash")
            })

    return accounts

def ping_single_account(acc):
    name = acc.get("name", "未命名账号")
    api_key = acc.get("api_key", "")
    base_url = acc.get("base_url", "https://open.bigmodel.cn/api/paas/v4/")
    model = acc.get("model", "glm-4-flash")

    if not api_key:
        log(f"❌ [{name}] 未配置 api_key，跳过此账号。")
        return False

    masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "***"
    log(f"▶️ 开始处理 [{name}] (Key: {masked_key}, BaseURL: {base_url}, Model: {model})")

    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )

    max_retries = 3
    retry_delay = 20

    for attempt in range(1, max_retries + 1):
        try:
            log(f"  🚀 [{name}] 尝试第 {attempt} 次触发预热...")
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1
            )
            log(f"  ✅ [{name}] 预热成功！已激活该账号 5 小时刷新窗口。")
            return True

        except Exception as e:
            err_str = str(e)
            log(f"  ⚠️ [{name}] 第 {attempt} 次触发提示/失败: {err_str}")
            
            if "429" in err_str or "rate limit" in err_str.lower():
                log(f"  ℹ️ [{name}] 提示: 处于旧窗口内或已达额度上限。")
            
            if attempt < max_retries:
                log(f"  ⏳ [{name}] 等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
            else:
                log(f"  ⚠️ [{name}] 达到最大重试次数，该账号预热结束。")
                return False

def main():
    log("==========================================")
    log(" Starting Zhipu Coding Plan Warmer Task")
    log("==========================================")
    
    accounts = parse_accounts()
    if not accounts:
        log("❌ 错误: 未检测到任何可用的账号配置！请检查 ZHIPU_ACCOUNTS 或 ZHIPU_API_KEY。")
        sys.exit(1)

    log(f"📋 共检测到 {len(accounts)} 个账号配置，开始依次预热...")
    
    success_count = 0
    for idx, acc in enumerate(accounts, 1):
        log(f"\n--- [{idx}/{len(accounts)}] ---")
        if ping_single_account(acc):
            success_count += 1
        time.sleep(2)

    log("\n==========================================")
    log(f" 预热任务完成! 成功: {success_count}/{len(accounts)}")
    log("==========================================")

if __name__ == "__main__":
    main()
