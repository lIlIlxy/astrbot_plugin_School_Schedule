import asyncio
import os
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .image_generator import ImageGenerator  # ✅ 导入你的图片生成类


@register("daily_schedule", "LitRainLee", "每天早上7:30自动发送课表（含图片）", "1.3.0")
class DailySchedulePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.scheduler = AsyncIOScheduler()
        # ✅ 支持多群推送
        self.target_group_ids = [875059212, 705502243, 1030481229]  # ← 修改为你的群号列表
        self.image_generator = ImageGenerator()

    async def initialize(self):
        """初始化插件（启动定时任务）"""
        self.scheduler.add_job(self.send_daily_schedule, "cron", hour=7, minute=30)
        self.scheduler.start()
        logger.info("[DailySchedule] 已注册每日 7:30 定时任务。")

    async def send_daily_schedule(self):
        """调用课表脚本并生成图片并推送到多个群"""
        try:
            # 1️⃣ 调用课表脚本
            process = await asyncio.create_subprocess_exec(
                "python3", "schedule_parser.py",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.dirname(__file__),  # 在插件目录下执行
            )
            stdout, stderr = await process.communicate()

            if stderr:
                logger.error(f"[DailySchedule] 课表脚本错误:\n{stderr.decode('utf-8')}")
                return

            output = stdout.decode("utf-8").strip()
            if not output:
                output = "课表脚本未输出任何内容。"

            logger.info(f"[DailySchedule] 脚本输出:\n{output}")

            # 2️⃣ 转换为课程结构
            courses = []
            for line in output.splitlines():
                if "|" not in line or "~" not in line:
                    continue
                try:
                    time_part, name, location, teacher = [x.strip() for x in line.split("|")]
                    start_str, end_str = [t.strip() for t in time_part.split("~")]
                    from datetime import datetime, timedelta, timezone
                    today = datetime.now(timezone(timedelta(hours=8))).date()
                    start_time = datetime.strptime(f"{today} {start_str}", "%Y-%m-%d %H:%M").astimezone(timezone(timedelta(hours=8)))
                    end_time = datetime.strptime(f"{today} {end_str}", "%Y-%m-%d %H:%M").astimezone(timezone(timedelta(hours=8)))
                    courses.append({
                        "summary": name,
                        "location": location,
                        "nickname": teacher,
                        "user_id": "0",
                        "start_time": start_time,
                        "end_time": end_time
                    })
                except Exception as e:
                    logger.warning(f"[DailySchedule] 无法解析行: {line} ({e})")

            # 3️⃣ 生成图片
            if courses:
                img_path = await self.image_generator.generate_user_schedule_image(
                    courses, nickname="今日课表"
                )
            else:
                from PIL import Image, ImageDraw, ImageFont
                from datetime import datetime
                img_path = os.path.join(os.path.dirname(__file__), "no_course.png")
                img = Image.new("RGB", (800, 200), (250, 250, 250))
                draw = ImageDraw.Draw(img)
                font = ImageFont.load_default()
                draw.text((50, 80), f"📅 {datetime.now().strftime('%Y-%m-%d')} 今天没有课程", fill=(0, 0, 0), font=font)
                img.save(img_path)

            # 4️⃣ 多群推送
            for group_id in self.target_group_ids:
                try:
                    await self.context.bot.send_group_message(group_id, output)
                    await self.context.bot.send_group_image(group_id, img_path)
                    logger.info(f"[DailySchedule] ✅ 已发送课表图片至群 {group_id}")
                except Exception as e:
                    logger.error(f"[DailySchedule] ❌ 群 {group_id} 发送失败: {e}")

        except Exception as e:
            logger.error(f"[DailySchedule] 执行任务时出错: {e}")

    @filter.command("scheduletest", description="手动触发课表推送")
    async def test_command(self, event: AstrMessageEvent):
        await self.send_daily_schedule()
        yield event.plain_result("✅ 已手动执行课表推送任务。")

    async def terminate(self):
        self.scheduler.shutdown()
        logger.info("[DailySchedule] 插件已卸载，定时任务已停止。")
