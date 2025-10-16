# -*- coding: utf-8 -*-
"""
ics_parser.py
解析 .ics 课表文件，输出课程名称、时间、地点、描述等信息。
支持重复课程（RRULE），并将结果写入日志文件。
"""

import os
import logging
from datetime import datetime, timedelta, date
from icalendar import Calendar
import recurring_ical_events

# ========== 配置部分 ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # ✅ 获取当前脚本目录
ICS_FILE = os.path.join(BASE_DIR, "schedule.ics")      # ✅ 自动拼接路径
LOG_FILE = os.path.join(BASE_DIR, "schedule.log")      # ✅ 日志也放同目录
START_DATE = datetime(2025, 1, 1)
END_DATE = datetime(2025, 12, 31)
# =============================

# 初始化日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def parse_ics_schedule(ics_path, start, end):
    """解析 .ics 文件，展开课程并返回事件列表"""
    if not os.path.exists(ics_path):
        raise FileNotFoundError(f"未找到文件：{ics_path}")

    with open(ics_path, 'rb') as f:
        cal = Calendar.from_ical(f.read())

    # 展开所有重复事件
    events = recurring_ical_events.of(cal).between(start, end)

    result = []
    for event in events:
        summary = str(event.get('summary'))
        location = str(event.get('location', '无地点'))
        description = str(event.get('description', ''))
        start_time = event.get('dtstart').dt
        end_time = event.get('dtend').dt

        result.append({
            '课程': summary,
            '开始时间': start_time,
            '结束时间': end_time,
            '地点': location,
            '备注': description,
        })
    return result


def log_today_schedule(events):
    """输出今日课程到日志"""
    today = date.today()
    today_events = [e for e in events if e['开始时间'].date() == today]

    logger.info(f"今日课程（{today.strftime('%Y-%m-%d')}）：")
    if not today_events:
        logger.info("今天没有课程 ✅")
        return

    for e in sorted(today_events, key=lambda x: x['开始时间']):
        start_str = e['开始时间'].strftime("%H:%M")
        end_str = e['结束时间'].strftime("%H:%M")
        msg = f"{start_str} ~ {end_str} | {e['课程']} | {e['地点']}"
        if e['备注'] and e['备注'] != "None":
            msg += f" | 备注: {e['备注']}"
        logger.info(msg)

    logger.info(f"今日共有 {len(today_events)} 门课程 ✅\n")


def run_today_schedule():
    """对外提供的主入口函数，可供 AstrBot 插件调用"""
    events = parse_ics_schedule(ICS_FILE, START_DATE, END_DATE)
    log_today_schedule(events)
    logger.info(f"日志已写入文件：{os.path.abspath(LOG_FILE)}")


# ============================
# 当独立运行脚本时执行
# ============================
if __name__ == "__main__":
    try:
        run_today_schedule()
    except Exception as e:
        logger.error(f"❌ 解析失败：{e}")
