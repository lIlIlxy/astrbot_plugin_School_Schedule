# -*- coding: utf-8 -*-
"""
AstrBot 插件：每日 7:30 自动运行 ics_parser.py，解析并记录今日课表。
"""

import asyncio
import importlib.util
from datetime import time
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
import sys


@register("daily_schedule_runner", "LitRainLee", "每天7:30自动解析课表文件", "1.0.0")
class DailySchedulePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.scheduler = AsyncIOScheduler()
        self.job = None

    async def initialize(self):
        """插件初始化时运行"""
        logger.info("📅 [每日课表插件] 初始化中...")

        # 确保 ics_parser.py 在当前目录可用
        script_path = os.path.join(os.path.dirname(__file__), "ics_parser.py")
        if not os.path.exists(script_path):
            logger.error(f"❌ 未找到脚本文件：{script_path}")
            return

        # 定义每日任务
        self.scheduler.add_job(
            self.run_script,
            "cron",
            hour=7,
            minute=30,
            id="daily_schedule_job",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("✅ [每日课表插件] 已设置每日 7:30 自动执行 ics_parser.py")

    async def run_script(self):
        """执行 ics_parser.py 中的 run_today_schedule()"""
        try:
            script_path = os.path.join(os.path.dirname(__file__), "ics_parser.py")

            # 动态加载模块
            spec = importlib.util.spec_from_file_location("ics_parser", script_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["ics_parser"] = module
            spec.loader.exec_module(module)

            # 调用其中的 run_today_schedule 函数
            if hasattr(module, "run_today_schedule"):
                logger.info("🕢 开始执行 ics_parser.run_today_schedule() ...")
                module.run_today_schedule()
                logger.info("✅ 今日课表解析完成")
            else:
                logger.error("❌ 脚本中未找到 run_today_schedule 函数")

        except Exception as e:
            logger.error(f"❌ 执行 ics_parser.py 时出错：{e}")

    @filter.command("run_schedule_now")
    async def run_now(self, event: AstrMessageEvent):
        """手动立即执行任务"""
        await self.run_script()
        yield event.plain_result("✅ 已手动执行今日课表解析任务。")

    async def terminate(self):
        """插件被卸载时停止任务"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        logger.info("🛑 [每日课表插件] 已停止调度器。")
