# -*- coding: utf-8 -*-
"""
课表解析脚本：解析 .ics 文件，生成今日课程信息。
输出格式化后的文本并写入 schedule.log。
"""

import os
import logging
from datetime import datetime, date, timedelta
from icalendar import Calendar
import recurring_ical_events

# ========== 配置 ==========
ICS_FILE = os.path.join(os.path.dirname(__file__), "schedule.ics")
LOG_FILE = os.path.join(os.path.dirname(__file__), "schedule.log")

# ========== 日志配置 ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()]
)


def get_section_range(start_time_str: str) -> str:
    """根据课程开始时间判断节次"""
    mapping = {
        "08:00": "1 - 2",
        "10:05": "3 - 4",
        "13:30": "5 - 6",
        "15:35": "7 - 8",
        "18:10": "9 - 10",
    }
    return mapping.get(start_time_str, "?")


def run_today_schedule():
    """解析今日课程并输出结果"""
    if not os.path.exists(ICS_FILE):
        logging.error(f"❌ 未找到课表文件：{ICS_FILE}")
        return "❌ 未找到课表文件，请确认文件路径。"

    with open(ICS_FILE, "r", encoding="utf-8") as f:
        cal = Calendar.from_ical(f.read())

    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    # 解析当天课程（包括重复事件）
    events_today = recurring_ical_events.of(cal).between(today_start, today_end)
    courses = []

    for event in events_today:
        start = event.get("dtstart").dt
        end = event.get("dtend").dt
        summary = str(event.get("summary", "无标题课程"))
        location = str(event.get("location", "未知地点"))
        description = str(event.get("description", ""))
        teacher = "，".join([s for s in description.split() if s]) if description else "未知教师"

        courses.append({
            "start": start.strftime("%H:%M"),
            "end": end.strftime("%H:%M"),
            "name": summary,
            "location": location,
            "teacher": teacher,
        })

    # ====== 生成输出文本 ======
    if not courses:
        output_text = f"☕ 今天（{today.strftime('%Y-%m-%d')}）没有课程，放松一下吧！"
    else:
        header = f"📚 今日课表（{today.strftime('%Y-%m-%d')}）\n" + "─" * 22
        lines = []
        for c in courses:
            lines.append(
                f"🕗 {c['start']} ~ {c['end']}\n"
                f"📘 {c['name']}\n"
                f"🏫 {c['location']}\n"
                f"👨‍🏫 {c['teacher']}\n"
                f"💬 第{get_section_range(c['start'])}节\n"
            )
        footer = f"📊 今日共有 {len(courses)} 门课程 ✅"
        output_text = "\n\n".join([header, "\n".join(lines), footer])

    # ====== 写入日志文件 ======
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(output_text + "\n\n")

    logging.info("✅ 今日课程解析完成并写入日志。")
    print(output_text)
    return output_text


if __name__ == "__main__":
    run_today_schedule()
