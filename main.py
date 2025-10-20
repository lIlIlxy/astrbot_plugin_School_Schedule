# -*- coding: utf-8 -*-
"""
AstrBot 插件：每日 7:30 自动运行 ics_parser.py，解析并发送今日课表到指定群。
兼容多种 AstrBot 版本（包括 napcat / aiocqhttp 等），
采用延迟获取 Bot 对象，避免初始化时报错。
"""

import os
import sys
import importlib.util
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register("astrbot_plugin_school_schedule", "LitRainLee", "每天7:30自动解析课表并发送结果到群", "2.1.0")
class DailySchedulePlugin(Star):
    # 需要自动推送的目标群号
    TARGET_GROUPS = [875059212, 705502243, 1030481229]

    def __init__(self, context: Context):
        super().__init__(context)
        self.scheduler = AsyncIOScheduler()
        self.script_path = os.path.join(os.path.dirname(__file__), "ics_parser.py")
        self.bot = None  # 延迟获取

    # ==================================================
    # 初始化部分
    # ==================================================
    async def initialize(self):
        """插件加载时自动执行"""
        logger.info("[DailySchedule] 插件初始化中...")

        if not os.path.exists(self.script_path):
            logger.error(f"[DailySchedule] ❌ 未找到课表脚本文件：{self.script_path}")
            return

        # 定时任务：每天 7:30 执行
        self.scheduler.add_job(
            self.auto_task,
            "cron",
            hour=7,
            minute=30,
            id="daily_schedule_job",
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=60 * 5
        )
        self.scheduler.start()
        logger.info("[DailySchedule] ✅ 插件初始化完成，Bot 对象将在发送消息时动态获取。")
        logger.info("[DailySchedule] ✅ 已设置每日 7:30 自动运行课表解析脚本。")

    # ==================================================
    # Bot 获取逻辑
    # ==================================================
    async def get_bot_instance(self):
        """安全地获取并缓存 Bot 对象，兼容多版本 AstrBot"""
        if self.bot:
            return self.bot

        ctx = self.context
        bot = None

        # 优先尝试 context.get_bot()
        get_bot = getattr(ctx, "get_bot", None)
        if callable(get_bot):
            try:
                result = get_bot()
                if asyncio.iscoroutine(result):
                    result = await result
                bot = result
                logger.debug("[DailySchedule] 成功通过 context.get_bot() 获取 Bot。")
            except Exception as e:
                logger.debug(f"[DailySchedule] context.get_bot() 调用失败：{e}")

        # 尝试 context.bot
        if not bot:
            bot = getattr(ctx, "bot", None)
            if bot:
                logger.debug("[DailySchedule] 成功通过 context.bot 获取 Bot。")

        # 尝试 event.get_bot()（某些 AstrBot 新版本中有效）
        if not bot and hasattr(ctx, "event"):
            event = getattr(ctx, "event")
            get_bot_evt = getattr(event, "get_bot", None)
            if callable(get_bot_evt):
                try:
                    result = get_bot_evt()
                    if asyncio.iscoroutine(result):
                        result = await result
                    bot = result
                    logger.debug("[DailySchedule] 成功通过 event.get_bot() 获取 Bot。")
                except Exception as e:
                    logger.debug(f"[DailySchedule] event.get_bot() 调用失败：{e}")

        if not bot:
            logger.error("[DailySchedule] ❌ 无法获取 Bot 对象，请检查适配器连接或授权状态。")
            return None

        self.bot = bot
        logger.info(f"[DailySchedule] ✅ 成功获取 Bot 实例：{type(bot).__name__}")
        return bot

    # ==================================================
    # 脚本执行逻辑
    # ==================================================
    async def run_script(self) -> str:
        """执行 ics_parser.py 的 run_today_schedule() 并返回课程文本"""
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
            logger.error(f"[DailySchedule] 课表脚本执行出错：{e}")
            return f"❌ 执行课表脚本出错：{e}"

    # ==================================================
    # 群消息发送逻辑
    # ==================================================
    async def send_to_groups(self, text: str):
        """将课程信息发送到所有指定群"""
        bot = await self.get_bot_instance()
        if not bot:
            logger.error("[DailySchedule] ❌ Bot 对象未初始化，发送中止。")
            return

        for group_id in self.TARGET_GROUPS:
            try:
                # 自动检测 Bot 可用方法
                if hasattr(bot, "send_group_msg"):
                    await bot.send_group_msg(group_id, text)
                elif hasattr(bot, "send_group_message"):
                    await bot.send_group_message(group_id, text)
                elif hasattr(bot, "send_group"):
                    await bot.send_group(group_id, text)
                else:
                    raise AttributeError("Bot 对象不支持群聊发送方法（send_group_msg/send_group_message/send_group）")

                logger.info(f"[DailySchedule] ✅ 已成功发送到群 {group_id}")
            except Exception as e:
                logger.error(f"[DailySchedule] ❌ 群 {group_id} 发送失败：{e}")

    # ==================================================
    # 定时任务逻辑
    # ==================================================
    async def auto_task(self):
        """每天 7:30 自动执行"""
        result_text = await self.run_script()
        logger.info(f"[DailySchedule] 自动执行结果：\n{result_text}")
        await self.send_to_groups(result_text)

    # ==================================================
    # 手动命令：/run_schedule_now
    # ==================================================
    @filter.command("run_schedule_now")
    async def run_now(self, event: AstrMessageEvent):
        """手动立即执行课表推送"""
        result_text = await self.run_script()
        await self.send_to_groups(result_text)
        yield event.plain_result(
            f"✅ 已手动执行课表解析，并发送到群 {self.TARGET_GROUPS}。\n\n{result_text}"
        )

    # ==================================================
    # 卸载钩子
    # ==================================================
    async def terminate(self):
        """插件卸载时停止调度"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        logger.info("[DailySchedule] 🛑 调度器已停止。")
