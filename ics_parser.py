# -*- coding: utf-8 -*-
"""
课表解析脚本：解析 .ics 文件，生成今日课程信息。
仅输出课程信息，不输出日志。
"""

import os
from datetime import datetime, date
from icalendar import Calendar
import recurring_ical_events

# ========== 配置 ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICS_FILE = os.path.join(BASE_DIR, "schedule.ics")

# ====== 节次映射 ======
def get_section_range(start_time_str: str) -> str:
    mapping = {
        "08:00": "1 - 2",
        "10:05": "3 - 4",
        "13:30": "5 - 6",
        "15:35": "7 - 8",
        "18:10": "9 - 10",
    }
    return mapping.get(start_time_str, "?")

# ====== 主函数 ======
def run_today_schedule() -> str:
    """解析今日课程，返回格式化文本"""
    if not os.path.exists(ICS_FILE):
        return "❌ 未找到课表文件，请确认路径。"

    with open(ICS_FILE, "r", encoding="utf-8") as f:
        cal = Calendar.from_ical(f.read())

    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

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

    if not courses:
        return f"☕ 今天（{today.strftime('%Y-%m-%d')}）没有课程，放松一下吧！"

    # 生成输出文本
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
    return output_text

# ====== 独立运行 ======
if __name__ == "__main__":
    print(run_today_schedule())
