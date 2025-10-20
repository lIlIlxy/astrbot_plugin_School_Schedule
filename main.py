# -*- coding: utf-8 -*-
"""
AstrBot 插件：每日 7:30 自动运行 ics_parser.py，解析并发送今日课表到指定群。
兼容当前 AstrBot 版本，延迟获取 Bot 对象，避免初始化时报错。
"""

import os
import sys
import importlib.util
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("astrbot_plugin_school_schedule", "LitRainLee", "每天7:30自动解析课表并发送结果到群", "2.0.3")
class DailySchedulePlugin(Star):
    # 多群号列表
    TARGET_GROUPS = [875059212, 705502243, 1030481229]

    def __init__(self, context: Context):
        super().__init__(context)
        self.scheduler = AsyncIOScheduler()
        self.script_path = os.path.join(os.path.dirname(__file__), "ics_parser.py")
        self.bot = None  # 延迟获取

    async def initialize(self):
        """插件初始化时自动调用"""
        logger.info("[DailySchedule] 初始化中...")

        if not os.path.exists(self.script_path):
            logger.error(f"[DailySchedule] ❌ 未找到课表脚本文件：{self.script_path}")
            return

        # 尝试预缓存 context 中的 bot（某些 AstrBot 版本会在 context 上直接暴露 bot）
        try:
            self.bot = getattr(self.context, "bot", None)
            if self.bot:
                logger.debug("[DailySchedule] 已从 context 预获取到 bot 对象并缓存。")
        except Exception:
            self.bot = None

        # 初始化不获取 Bot，对象延迟到发送消息时再获取
        logger.info("[DailySchedule] ✅ 插件初始化完成，Bot 对象将在发送消息时获取。")

        # 设置定时任务：每天 7:30 执行
        self.scheduler.add_job(
            self.auto_task,
            "cron",
            hour=7,
            minute=30,
            id="daily_schedule_job",
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=60*5
        )
        self.scheduler.start()
        logger.info("✅ [DailySchedule] 已设置每日 7:30 自动运行课表解析脚本。")

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
            logger.error(f"[DailySchedule] 课表脚本错误：{e}")
            return f"❌ 执行课表脚本出错：{e}"

    async def send_to_groups(self, text: str, bot=None):
        """将课程信息发送到指定群（兼容多种 AstrBot 版本）
        优先使用传入的 bot（例如来自 event.bot），否则再从 context 获取并缓存。
        """
        # 已由调用方提供 bot（例如 event.bot）则优先使用
        if bot:
            self.bot = bot

        # 延迟获取并缓存 Bot 对象（兼容 context.get_bot() 或 context.bot）
        if not self.bot:
            ctx = self.context
            bot_candidate = None
            if hasattr(ctx, "get_bot"):
                try:
                    bot_candidate = await ctx.get_bot()
                except Exception as e:
                    logger.debug(f"[DailySchedule] 尝试 await context.get_bot() 失败：{e}")
            if not bot_candidate:
                bot_candidate = getattr(ctx, "bot", None)
            if not bot_candidate:
                logger.error("[DailySchedule] ❌ 未获取到 Bot 对象，无法发送群消息")
                return
            self.bot = bot_candidate

        # 选择可用的发送方法并发送到每个群
        for group_id in self.TARGET_GROUPS:
            sent = False
            last_exc = None
            for method_name in ("send_group_msg", "send_group_message", "send_group"):
                if not hasattr(self.bot, method_name):
                    continue
                method = getattr(self.bot, method_name)
                try:
                    # 尝试关键字参数（多数 CQHttp 封装使用 group_id=..., message=...）
                    ret = method(group_id=group_id, message=text)
                    if asyncio.iscoroutine(ret):
                        await ret
                    sent = True
                    break
                except TypeError as e:
                    last_exc = e
                    try:
                        # 回退尝试位置参数（部分接口可能接受）
                        ret = method(group_id, text)
                        if asyncio.iscoroutine(ret):
                            await ret
                        sent = True
                        break
                    except Exception as e2:
                        last_exc = e2
                        continue
                except Exception as e:
                    last_exc = e
                    continue

            if not sent:
                # 最后尝试直接调用 call_action（若封装暴露此方法）
                try:
                    if hasattr(self.bot, "call_action"):
                        ret = self.bot.call_action("send_group_msg", group_id=group_id, message=text)
                        if asyncio.iscoroutine(ret):
                            await ret
                        sent = True
                except Exception as e:
                    last_exc = e

            if sent:
                logger.info(f"[DailySchedule] ✅ 已发送到群 {group_id}")
            else:
                logger.error(f"[DailySchedule] ❌ 发送到群 {group_id} 失败：{last_exc}")

    async def auto_task(self):
        """每天 7:30 自动执行任务"""
        result_text = await self.run_script()
        logger.info(f"[DailySchedule] 自动执行结果：\n{result_text}")
        await self.send_to_groups(result_text)

    @filter.command("run_schedule_now")
    async def run_now(self, event: AstrMessageEvent, *args, **kwargs):
        """手动立即执行课表任务（兼容不同调用约定）"""
        result_text = await self.run_script()

        # 优先从 kwargs/args 中获取可能传入的 bot（兼容不同 AstrBot 版本）
        event_bot = kwargs.get("bot", None)
        if not event_bot and args:
            candidate = args[0]
            # 若第一个额外参数看起来像 bot（包含常见发送方法），则使用
            if candidate and any(hasattr(candidate, m) for m in ("send_group_msg", "send_group_message", "send_group", "call_action")):
                event_bot = candidate

        # 最后退回到 event.bot（如果存在）
        if not event_bot:
            event_bot = getattr(event, "bot", None)

        await self.send_to_groups(result_text, bot=event_bot)
        yield event.plain_result(
            f"✅ 已手动执行课表解析，并发送到群 {self.TARGET_GROUPS}。\n\n{result_text}"
        )

    async def terminate(self):
        """插件卸载时停止调度"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        logger.info("[DailySchedule] 🛑 调度器已停止。")
