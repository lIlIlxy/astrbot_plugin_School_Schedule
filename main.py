# -*- coding: utf-8 -*-
"""
AstrBot 插件：每日 7:30 自动运行 ics_parser.py，解析并发送今日课表到指定群。
v2.3 稳定修复版
✅ 修复 CQHttp 适配器参数错误 (call_action 参数数量不匹配)
✅ 支持 NapCat / OneBot / CQHttp 多平台
✅ Bot 自动缓存与安全发送
"""

import os
import sys
import importlib.util
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register("astrbot_plugin_school_schedule", "LitRainLee", "每天7:30自动解析课表并发送结果到群", "2.3")
class DailySchedulePlugin(Star):
    TARGET_GROUPS = [875059212, 705502243, 1030481229]

    def __init__(self, context: Context):
        super().__init__(context)
        self.scheduler = AsyncIOScheduler()
        self.script_path = os.path.join(os.path.dirname(__file__), "ics_parser.py")
        self.bot = None

    async def initialize(self):
        logger.info("[DailySchedule] 初始化中...")

        if not os.path.exists(self.script_path):
            logger.error(f"[DailySchedule] ❌ 未找到课表脚本文件：{self.script_path}")
            return

        # 每日定时任务
        self.scheduler.add_job(
            self.auto_task,
            "cron",
            hour=7,
            minute=30,
            id="daily_schedule_job",
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=300
        )
        self.scheduler.start()
        logger.info("✅ [DailySchedule] 已设置每日 7:30 自动运行课表解析任务。")

    async def get_bot_instance(self, event: AstrMessageEvent = None):
        """多方式获取 Bot 实例"""
        if self.bot:
            return self.bot

        ctx = self.context
        bot = None

        # event.get_bot()
        if event:
            try:
                if hasattr(event, "bot"):
                    bot = event.bot
                elif hasattr(event, "get_bot") and callable(event.get_bot):
                    maybe_bot = event.get_bot()
                    if asyncio.iscoroutine(maybe_bot):
                        maybe_bot = await maybe_bot
                    bot = maybe_bot
            except Exception as e:
                logger.debug(f"[DailySchedule] event 获取 bot 失败: {e}")

        # context.get_bot()
        if not bot:
            try:
                if hasattr(ctx, "get_bot") and callable(ctx.get_bot):
                    maybe_bot = ctx.get_bot()
                    if asyncio.iscoroutine(maybe_bot):
                        maybe_bot = await maybe_bot
                    bot = maybe_bot
            except Exception as e:
                logger.debug(f"[DailySchedule] context.get_bot() 获取失败: {e}")

        # context.bot
        if not bot:
            bot = getattr(ctx, "bot", None)

        # 全局
        if not bot:
            try:
                from astrbot.core.adapter import get_all_bots
                bots = get_all_bots()
                if bots:
                    bot = list(bots.values())[0]
            except Exception as e:
                logger.debug(f"[DailySchedule] 全局 bot 获取失败: {e}")

        if bot:
            self.bot = bot
            logger.info(f"[DailySchedule] ✅ Bot 实例已缓存：{type(bot).__name__}")
        else:
            logger.error("[DailySchedule] ❌ 无法获取 Bot 实例。")

        return bot

    async def run_script(self) -> str:
        """执行 ics_parser.py"""
        try:
            spec = importlib.util.spec_from_file_location("ics_parser", self.script_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["ics_parser"] = module
            spec.loader.exec_module(module)

            if hasattr(module, "run_today_schedule"):
                result = module.run_today_schedule()
                if asyncio.iscoroutine(result):
                    result = await result
            else:
                return "❌ 错误：ics_parser.py 中未定义 run_today_schedule()。"

            return result if result else "☕ 今天没有课程，记得休息！"

        except Exception as e:
            logger.error(f"[DailySchedule] 课表脚本执行错误：{e}")
            return f"❌ 执行课表脚本出错：{e}"

    async def send_to_groups(self, text: str, event: AstrMessageEvent = None):
        """兼容多平台发送群消息"""
        bot = await self.get_bot_instance(event)
        if not bot:
            logger.error("[DailySchedule] ❌ Bot 对象未初始化，发送中止。")
            return

        for group_id in self.TARGET_GROUPS:
            try:
                # 优先检查是否有标准 send_group_msg 方法
                if hasattr(bot, "send_group_msg"):
                    await bot.send_group_msg(group_id=group_id, message=text)

                # OneBot / Napcat 有时封装为 call_action
                elif hasattr(bot, "call_action"):
                    await bot.call_action("send_group_msg", {
                        "group_id": group_id,
                        "message": text
                    })

                else:
                    logger.error("[DailySchedule] ❌ 无可用的群发方法。")
                    continue

                logger.info(f"[DailySchedule] ✅ 已成功发送到群 {group_id}")

            except Exception as e:
                logger.error(f"[DailySchedule] ❌ 发送到群 {group_id} 失败：{e}")

    async def auto_task(self):
        """每日自动任务"""
        result_text = await self.run_script()
        logger.info(f"[DailySchedule] 自动任务执行结果：\n{result_text}")
        await self.send_to_groups(result_text)

    @filter.command("run_schedule_now")
    async def run_now(self, event: AstrMessageEvent):
        """手动触发任务"""
        await self.get_bot_instance(event)
        result_text = await self.run_script()
        await self.send_to_groups(result_text, event)
        yield event.plain_result(
            f"✅ 已手动执行课表解析，并发送到群 {self.TARGET_GROUPS}。\n\n{result_text}"
        )

    async def terminate(self):
        """停止任务"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        logger.info("[DailySchedule] 🛑 调度器已停止。")
