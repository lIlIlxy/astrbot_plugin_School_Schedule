# -*- coding: utf-8 -*-
"""
ics_parser.py
解析 .ics 课表文件，输出课程名称、时间、地点、描述等信息。
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
    if not os.path.exists(ics_path):
        raise FileNotFoundError(f"未找到文件：{ics_path}")
    ...
