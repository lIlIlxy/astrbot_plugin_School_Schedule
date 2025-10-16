# -*- coding: utf-8 -*-
"""
AstrBot 插件：每日 7:30 自动运行 ics_parser.py，解析并发送今日课表到指定群。
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


@register("astrbot_plugin_school_schedule", "LitRainLee", "每天7:30自动解析课表并发送结果到指定群", "2.0.0")
class DailySchedulePlugin(Star):
    # 支持多群发送
    TARGET_GROUPS = [875059212, 705502243, 1030481229]

    def __init__(self, context: Context):
        super().__init__(context)
        self.scheduler = AsyncIOScheduler()
        self.script_path = os.path.join(os.path.dirname(__file__), "ics_parser.py")

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

    async def run_script(self) -> str:
        """执行 ics_parser.py 的 run_today_schedule() 并返回结果文本"""
        try:
            # 动态加载 ics_parser.py
            spec = importlib.util.spec_from_file_location("ics_parser", self.script_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["ics_parser"] = module
            spec.loader.exec_module(module)

            # 执行 run_today_schedule()
            if hasattr(module, "run_today_schedule"):
                events = module.run_today_schedule()  # ics_parser.py 返回课程信息列表
            else:
                return "❌ 错误：ics_parser.py 中未定义 run_today_schedule() 函数。"

            if not events:
                return "☕ 今天没有课程，记得休息！"

            # 构造输出文本
            lines = ["📚 今日课表更新："]
            for e in events:
                start = e['开始时间'].strftime("%H:%M")
                end = e['结束时间'].strftime("%H:%M")
                course = e['课程']
                location = e['地点']
                remark = e.get('备注', '')
                line = f"{start} ~ {end} | {course} | {location}"
                if remark:
                    line += f" | 备注: {remark}"
                lines.append(line)
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"[DailySchedule] 课表脚本错误：{e}")
            return f"❌ 执行课表脚本出错：{e}"

    async def auto_task(self):
        """每天 7:30 自动执行任务并发送到指定群"""
        result_text = await self.run_script()
        try:
            for group_id in self.TARGET_GROUPS:
                await self.bot.send_group_message(group_id, result_text)
                logger.info(f"[DailySchedule] ✅ 已发送今日课表到群 {group_id}")
        except Exception as e:
            logger.error(f"[DailySchedule] ❌ 发送群消息失败：{e}")

    @filter.command("run_schedule_now")
    async def run_now(self, event: AstrMessageEvent):
        """手动立即执行任务并发送到指定群"""
        result_text = await self.run_script()
        try:
            for group_id in self.TARGET_GROUPS:
                await self.bot.send_group_message(group_id, result_text)
        except Exception as e:
            logger.error(f"[DailySchedule] ❌ 手动发送群消息失败：{e}")
        # 将手动执行提示与课表内容一同发送
        yield event.plain_result(f"✅ 已手动执行课表解析，并发送到群 {self.TARGET_GROUPS}。\n\n{result_text}")

    async def terminate(self):
        """插件卸载时停止调度"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        logger.info("[DailySchedule] 🛑 调度器已停止。")
