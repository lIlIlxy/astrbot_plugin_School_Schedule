# -*- coding: utf-8 -*-
"""
AstrBot 插件：每日 7:30 自动运行 ics_parser.py，解析并返回今日课表。
"""

import os
import sys
import importlib.util
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register("astrbot_plugin_school_schedule", "LitRainLee", "每天7:30自动解析课表并发送结果", "1.5.0")
class DailySchedulePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.scheduler = AsyncIOScheduler()
        self.script_path = os.path.join(os.path.dirname(__file__), "ics_parser.py")
        self.log_file = os.path.join(os.path.dirname(self.script_path), "schedule.log")

    async def initialize(self):
        """插件初始化时自动调用"""
        logger.info("[DailySchedule] 初始化中...")

        if not os.path.exists(self.script_path):
            logger.error(f"[DailySchedule] ❌ 未找到课表脚本文件：{self.script_path}")
            return

        # 定时任务：每天早上 7:30 执行
        self.scheduler.add_job(
            self.auto_task,
            "cron",
            hour=7,
            minute=30,
            id="daily_schedule_job",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("✅ [DailySchedule] 已设置每日 7:30 自动运行课表解析脚本。")

    async def run_script(self):
        """执行 ics_parser.py 的 run_today_schedule() 并返回结果文本"""
        try:
            logger.info("[DailySchedule] 🕢 正在执行课表脚本...")

            # 动态加载 ics_parser.py
            spec = importlib.util.spec_from_file_location("ics_parser", self.script_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["ics_parser"] = module
            spec.loader.exec_module(module)

            # 执行 run_today_schedule()
            if hasattr(module, "run_today_schedule"):
                result = module.run_today_schedule()
                if asyncio.iscoroutine(result):
                    await result
            else:
                return "❌ 错误：ics_parser.py 中未定义 run_today_schedule() 函数。"

            # 读取今日日志内容
            today = datetime.now().strftime("%Y-%m-%d")
            today_lines = []
            if os.path.exists(self.log_file):
                with open(self.log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if today in line:
                            today_lines.append(line)

            if today_lines:
                return "📚 今日课表更新：\n" + "".join(today_lines).strip()
            else:
                return "☕ 今天没有课程，记得休息！"

        except Exception as e:
            logger.error(f"[DailySchedule] 课表脚本错误：{e}")
            return f"❌ 执行课表脚本出错：{e}"

    async def auto_task(self):
        """每天 7:30 自动执行任务（控制台输出即可）"""
        result_text = await self.run_script()
        logger.info(f"[DailySchedule] 自动执行结果：\n{result_text}")

    @filter.command("run_schedule_now")
    async def run_now(self, event: AstrMessageEvent):
        """手动立即执行课表任务"""
        result_text = await self.run_script()
        # ✅ 将课表结果与命令提示一同发送
        yield event.plain_result(f"✅ 已手动执行课表解析。\n\n{result_text}")

    async def terminate(self):
        """插件卸载时停止调度"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        logger.info("[DailySchedule] 🛑 调度器已停止。")
