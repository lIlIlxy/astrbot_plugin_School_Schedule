# -*- coding: utf-8 -*-
"""
AstrBot 插件：每日 7:30 自动运行 ics_parser.py，解析并发送到多个指定群。
"""

import os
import sys
import importlib.util
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register("astrbot_plugin_school_schedule", "LitRainLee", "每天7:30自动解析课表并发送到多个群", "1.8.0")
class DailySchedulePlugin(Star):
    # 配置目标群号列表
    TARGET_GROUPS = [123456789, 987654321]  # 替换为你的群号

    def __init__(self, context: Context):
        super().__init__(context)
        self.scheduler = AsyncIOScheduler()
        self.script_path = os.path.join(os.path.dirname(__file__), "ics_parser.py")

    async def initialize(self):
        logger.info("[DailySchedule] 初始化中...")

        if not os.path.exists(self.script_path):
            logger.error(f"[DailySchedule] ❌ 未找到课表脚本文件：{self.script_path}")
            return

        # 每天早上 7:30 自动执行
        self.scheduler.add_job(
            self.auto_task,
            "cron",
            hour=7,
            minute=30,
            id="daily_schedule_job",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info(f"✅ [DailySchedule] 已设置每日 7:30 自动发送课表到群 {self.TARGET_GROUPS}。")

    async def run_script(self):
        """执行 ics_parser.py 并返回结果文本"""
        try:
            if "ics_parser" in sys.modules:
                del sys.modules["ics_parser"]
            spec = importlib.util.spec_from_file_location("ics_parser", self.script_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["ics_parser"] = module
            spec.loader.exec_module(module)

            if hasattr(module, "run_today_schedule"):
                result = module.run_today_schedule()
                if asyncio.iscoroutine(result):
                    result = await result
                return result
            else:
                return "❌ ics_parser.py 中未定义 run_today_schedule() 函数。"

        except Exception as e:
            logger.error(f"[DailySchedule] 课表脚本错误：{e}")
            return f"❌ 执行课表脚本出错：{e}"

    async def auto_task(self):
        """每天 7:30 自动执行并发送到所有目标群"""
        result_text = await self.run_script()
        logger.info(f"[DailySchedule] 自动执行结果：\n{result_text}")

        try:
            bot = await self.context.get_bot()
            for group_id in self.TARGET_GROUPS:
                await bot.send_group_message(group_id, result_text)
                logger.info(f"[DailySchedule] ✅ 已发送今日课表到群 {group_id}")
        except Exception as e:
            logger.error(f"[DailySchedule] ❌ 发送群消息失败：{e}")

    @filter.command("run_schedule_now")
    async def run_now(self, event: AstrMessageEvent):
        """手动立即执行任务"""
        result_text = await self.run_script()
        try:
            bot = await self.context.get_bot()
            for group_id in self.TARGET_GROUPS:
                await bot.send_group_message(group_id, result_text)
        except Exception as e:
            logger.error(f"[DailySchedule] ❌ 手动发送群消息失败：{e}")
        yield event.plain_result(f"✅ 已手动执行课表解析，并发送到群 {self.TARGET_GROUPS}。")

    async def terminate(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        logger.info("[DailySchedule] 🛑 调度器已停止。")
