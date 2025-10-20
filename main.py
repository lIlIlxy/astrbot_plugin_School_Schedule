# -*- coding: utf-8 -*-
"""
AstrBot 插件：每日 7:30 自动运行 ics_parser.py，解析并发送今日课表到指定群。
v2.2 修复版：
✅ 兼容不同 AstrBot 版本的 Bot 获取机制（context / event / 全局）
✅ 自动缓存 Bot 对象，防止发送中断
✅ 优化日志输出与异常处理
"""

import os
import sys
import importlib.util
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("astrbot_plugin_school_schedule", "LitRainLee", "每天7:30自动解析课表并发送结果到群", "2.2")
class DailySchedulePlugin(Star):
    # 多群号列表（可自行修改）
    TARGET_GROUPS = [875059212, 705502243, 1030481229]

    def __init__(self, context: Context):
        super().__init__(context)
        self.scheduler = AsyncIOScheduler()
        self.script_path = os.path.join(os.path.dirname(__file__), "ics_parser.py")
        self.bot = None  # 延迟获取 Bot 实例

    async def initialize(self):
        """插件初始化"""
        logger.info("[DailySchedule] 初始化中...")

        if not os.path.exists(self.script_path):
            logger.error(f"[DailySchedule] ❌ 未找到课表脚本文件：{self.script_path}")
            return

        # 设置每日定时任务
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
        logger.info("[DailySchedule] Bot 对象将在首次发送时自动捕获。")

    async def get_bot_instance(self, event: AstrMessageEvent = None):
        """尝试多种方式获取 Bot 对象"""
        if self.bot:
            return self.bot

        ctx = self.context
        bot = None

        # 1️⃣ 优先通过 event 获取
        if event:
            bot = getattr(event, "bot", None)
            if not bot:
                get_bot_evt = getattr(event, "get_bot", None)
                if callable(get_bot_evt):
                    try:
                        maybe_bot = get_bot_evt()
                        if asyncio.iscoroutine(maybe_bot):
                            maybe_bot = await maybe_bot
                        bot = maybe_bot
                    except Exception as e:
                        logger.debug(f"[DailySchedule] event.get_bot() 获取失败: {e}")

        # 2️⃣ 其次通过 context 获取
        if not bot:
            get_bot_ctx = getattr(ctx, "get_bot", None)
            if callable(get_bot_ctx):
                try:
                    maybe_bot = get_bot_ctx()
                    if asyncio.iscoroutine(maybe_bot):
                        maybe_bot = await maybe_bot
                    bot = maybe_bot
                except Exception as e:
                    logger.debug(f"[DailySchedule] context.get_bot() 获取失败: {e}")

        # 3️⃣ 兼容 context.bot
        if not bot:
            bot = getattr(ctx, "bot", None)

        # 4️⃣ 最后尝试全局注册表
        if not bot:
            try:
                from astrbot.core.adapter import get_all_bots
                bots = get_all_bots()
                if bots:
                    bot = list(bots.values())[0]
                    logger.info(f"[DailySchedule] ✅ 已通过全局注册表获取 Bot：{bot}")
            except Exception as e:
                logger.debug(f"[DailySchedule] get_all_bots() 获取失败: {e}")

        # 结果
        if bot:
            self.bot = bot
            logger.info(f"[DailySchedule] ✅ Bot 实例已缓存：{type(bot).__name__}")
            return bot
        else:
            logger.error("[DailySchedule] ❌ 无法获取 Bot 对象，请检查适配器连接或授权状态。")
            return None

    async def run_script(self) -> str:
        """执行 ics_parser.py 的 run_today_schedule() 并返回结果"""
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
                return "❌ 错误：ics_parser.py 中未定义 run_today_schedule() 函数。"

            return result if result else "☕ 今天没有课程，记得休息！"

        except Exception as e:
            logger.error(f"[DailySchedule] 课表脚本执行错误：{e}")
            return f"❌ 执行课表脚本出错：{e}"

    async def send_to_groups(self, text: str, event: AstrMessageEvent = None):
        """将课表信息发送到多个群聊"""
        bot = await self.get_bot_instance(event)
        if not bot:
            logger.error("[DailySchedule] ❌ Bot 对象未初始化，发送中止。")
            return

        for group_id in self.TARGET_GROUPS:
            try:
                if hasattr(bot, "send_group_msg"):
                    await bot.send_group_msg(group_id, text)
                elif hasattr(bot, "send_group_message"):
                    await bot.send_group_message(group_id, text)
                elif hasattr(bot, "send_group"):
                    await bot.send_group(group_id, text)
                else:
                    logger.error("[DailySchedule] ❌ Bot 对象缺少群发方法（send_group_msg / send_group_message / send_group）")
                    return
                logger.info(f"[DailySchedule] ✅ 已成功发送到群 {group_id}")
            except Exception as e:
                logger.error(f"[DailySchedule] ❌ 发送到群 {group_id} 失败：{e}")

    async def auto_task(self):
        """每日定时自动执行"""
        result_text = await self.run_script()
        logger.info(f"[DailySchedule] 自动任务执行结果：\n{result_text}")
        await self.send_to_groups(result_text)

    @filter.command("run_schedule_now")
    async def run_now(self, event: AstrMessageEvent):
        """手动立即执行课表任务"""
        # 🔧 触发时会缓存 Bot
        await self.get_bot_instance(event)

        result_text = await self.run_script()
        await self.send_to_groups(result_text, event)

        yield event.plain_result(
            f"✅ 已手动执行课表解析，并发送到群 {self.TARGET_GROUPS}。\n\n{result_text}"
        )

    async def terminate(self):
        """插件卸载时停止调度"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        logger.info("[DailySchedule] 🛑 调度器已停止。")
