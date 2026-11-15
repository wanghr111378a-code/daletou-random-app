import json
import os
import re
import sys
from datetime import datetime, timezone

import requests

API_URL = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry"
DATA_FILE = "data/dlt-history.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 14) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://m.lottery.gov.cn/",
    "Connection": "keep-alive"
}



 def get_api_draws():
    """从公开维护的500彩票网历史数据JSON获取大乐透开奖数据。"""

    url = (
        "https://raw.githubusercontent.com/"
        "yangxb919/lottery-data/main/data/dlt.json"
    )

    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=40
    )
    response.raise_for_status()

    rows = response.json()

    if not isinstance(rows, list) or not rows:
        raise RuntimeError("备用数据源没有返回有效开奖列表。")

    draws = []

    for row in rows[:200]:
        try:
            issue = str(row["issue"]).strip()
            date = str(row["date"]).strip()

            front = sorted(int(x) for x in row["front"])
            back = sorted(int(x) for x in row["back"])

            if len(issue) != 5:
                continue

            if len(front) != 5 or len(set(front)) != 5:
                continue

            if len(back) != 2 or len(set(back)) != 2:
                continue

            if any(x < 1 or x > 35 for x in front):
                continue

            if any(x < 1 or x > 12 for x in back):
                continue

            draws.append({
                "issue": issue,
                "date": date,
                "front": front,
                "back": back
            })

        except (KeyError, TypeError, ValueError):
            continue

    if not draws:
        raise RuntimeError("备用数据源数据格式校验失败。")

    unique = {item["issue"]: item for item in draws}

    return sorted(
        unique.values(),
        key=lambda x: int(x["issue"])
    )


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
