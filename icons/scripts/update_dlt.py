import json
import os
import re
import sys
from datetime import datetime, timezone

import requests

API_URL = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry"
DATA_FILE = "data/dlt-history.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.sporttery.cn/"
}


def get_api_draws():
    """从中国体育彩票公开接口获取大乐透历史开奖数据。"""
    params = {
        "gameNo": "85",
        "provinceId": "0",
        "pageSize": "200",
        "pageNo": "1"
    }

    response = requests.get(
        API_URL,
        params=params,
        headers=HEADERS,
        timeout=25
    )
    response.raise_for_status()
    result = response.json()

    value = result.get("value") or {}
    rows = value.get("list") or []

    if not rows:
        raise RuntimeError("官方接口没有返回开奖列表，停止更新。")

    draws = []

    for row in rows:
        issue = str(row.get("lotteryDrawNum", "")).strip()
        date = str(row.get("lotteryDrawTime", "")).strip()
        result_text = str(row.get("lotteryDrawResult", "")).strip()

        if not issue or not date or not result_text:
            continue

        # 官方开奖结果通常为：01 02 03 04 05 + 01 02
        parts = re.split(r"\s*\+\s*", result_text)

        if len(parts) != 2:
            continue

        front = [int(x) for x in re.findall(r"\d+", parts[0])]
        back = [int(x) for x in re.findall(r"\d+", parts[1])]

        # 严格检查号码数量、范围和重复情况
        if len(front) != 5 or len(back) != 2:
            continue
        if len(set(front)) != 5 or len(set(back)) != 2:
            continue
        if any(x < 1 or x > 35 for x in front):
            continue
        if any(x < 1 or x > 12 for x in back):
            continue

        draws.append({
            "issue": issue,
            "date": date,
            "front": sorted(front),
            "back": sorted(back)
        })

    if not draws:
        raise RuntimeError("接口数据未通过格式校验，停止更新。")

    # 按期号排序，并去除重复期号
    unique = {item["issue"]: item for item in draws}
    return sorted(unique.values(), key=lambda x: int(x["issue"]))


def load_old_data():
    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        old_data = json.load(file)

    return old_data.get("draws", [])


def main():
    print("开始获取大乐透开奖数据……")

    new_draws = get_api_draws()
    old_draws = load_old_data()

    old_map = {str(x["issue"]): x for x in old_draws}
    new_map = {str(x["issue"]): x for x in new_draws}

    # 保留已有数据，并合并接口返回的新期号
    merged = dict(old_map)
    merged.update(new_map)

    merged_draws = sorted(
        merged.values(),
        key=lambda x: int(x["issue"])
    )

    latest_issue = merged_draws[-1]["issue"]

    if old_draws and set(new_map).issubset(set(old_map)):
        print("没有发现新一期数据，无需更新文件。")
        print("当前最新期号：", latest_issue)
        return

    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

    output = {
        "source": "中国体育彩票公开开奖数据接口",
        "gameNo": "85",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "latestIssue": latest_issue,
        "totalDraws": len(merged_draws),
        "draws": merged_draws
    }

    # 先写临时文件，再替换正式文件，避免写入中断造成文件损坏
    temp_file = DATA_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    os.replace(temp_file, DATA_FILE)

    print("更新成功！")
    print("最新期号：", latest_issue)
    print("累计期数：", len(merged_draws))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("更新失败：", error)
        sys.exit(1)
