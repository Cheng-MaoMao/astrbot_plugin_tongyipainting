import asyncio
import importlib
import re
import subprocess
import sys
from dashscope import ImageSynthesis, VideoSynthesis
from astrbot.api.event import MessageChain
import astrbot.api.message_components as Comp
from astrbot.api.message_components import Plain, Image, Video
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import *

@register("astrbot_plugin_tongyipainting", "Cheng-MaoMao", "通过阿里云通义生成绘画和视频", "1.0.0", "https://github.com/Cheng-MaoMao/astrbot_plugin_tongyipainting")
class TongyiPainting(Star):
    def __init__(self, context: Context, config: dict):
        """初始化插件
        Args:
            context: 插件上下文
            config: 插件配置字典
        """
        super().__init__(context)
        # 保存配置信息
        self.config = config
        self.api_key = config.get("api_key", "")
        
        # 检查并安装必要的依赖包
        if not self._check_package("dashscope"):
            self._install_package("dashscope")

    def _check_package(self, package: str) -> bool:
        """检查包是否已安装
        Args:
            package: 包名
        Returns:
            bool: 是否已安装
        """
        try:
            importlib.import_module(package)
            return True
        except ImportError:
            return False

    def _install_package(self, package: str):
        """安装指定的包
        Args:
            package: 要安装的包名
        Raises:
            subprocess.CalledProcessError: 安装失败时抛出
        """
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", package])
            print(f"成功安装 {package}")
        except subprocess.CalledProcessError as e:
            print(f"安装 {package} 失败: {str(e)}")
            raise

    @filter.event_message_type(EventMessageType.ALL)
    async def handle_message(self, event: AstrMessageEvent):
        """处理接收到的消息
        Args:
            event: 消息事件对象
        """
        # 检查API密钥是否配置
        if not self.api_key:
            yield event.plain_result("请配置API密钥")
            return

        message = event.message_str

        # 根据触发词判断要调用的功能
        if any(kw in message for kw in self.image_keywords):
            await self.handle_image_generation(event, message)
        elif any(kw in message for kw in self.video_keywords):
            await self.handle_video_generation(event, message)
        elif any(kw in message for kw in self.i2v_keywords):
            await self.handle_image_to_video(event, message)

    @filter.command("文生图")
    async def handle_image_generation(self, event: AstrMessageEvent):
        """处理文生图请求"""
        message = event.message_str.strip()

        # 检查命令格式
        parts = message.split()
        if len(parts) != 3 or parts[2] not in ["横图", "竖图"]:
            yield event.plain_result("请使用正确的命令格式：/文生图 提示词 横图/竖图")
            return

        prompt = parts[1]
        is_horizontal = parts[2] == "横图"

        # 设置尺寸
        size = "1920*1080" if is_horizontal else "1080*1920"

        yield event.plain_result("正在生成图片，请稍候...")

        try:
            # 调用文生图API
            rsp = ImageSynthesis.async_call(
                api_key=self.api_key,
                model=self.config.get("image_model", "wanx2.1-t2i-turbo"),
                prompt=prompt,
                prompt_extend=self.config.get("prompt_extend", False),
                n=1,
                size=size
            )

            result = await asyncio.to_thread(ImageSynthesis.wait, rsp)

            if result.status_code == 200:
                image_url = result.output.results[0].url
                yield event.image_result(image_url)
            else:
                yield event.plain_result(f"生成失败: {result.message}")

        except Exception as e:
            yield event.plain_result(f"生成失败: {str(e)}")

    @filter.command("文生视频")
    async def handle_video_generation(self, event: AstrMessageEvent):
        """处理文生视频请求"""
        message = event.message_str.strip()

        # 检查命令格式
        parts = message.split()
        if len(parts) != 3 or parts[2] not in ["横图", "竖图"]:
            yield event.plain_result("请使用正确的命令格式：/文生视频 提示词 横图/竖图")
            return

        prompt = parts[1]
        is_horizontal = parts[2] == "横图"

        # 设置尺寸
        size = "1920*1080" if is_horizontal else "1080*1920"

        yield event.plain_result("正在生成视频，请稍候...")

        try:
            rsp = VideoSynthesis.async_call(
                api_key=self.api_key,
                model=self.config.get("video_model", "wanx2.1-i2v-turbo"),
                prompt=prompt,
                prompt_extend=self.config.get("prompt_extend", False),
                size=size
            )

            result = await asyncio.to_thread(VideoSynthesis.wait, rsp)

            if result.status_code == 200:
                video_url = result.output.video_url
                message_chain = MessageChain().message(f"生成完成!\n提示词：{prompt}").video(video_url)
                await self.context.send_message(event.unified_msg_origin, message_chain)
            else:
                yield event.plain_result(f"生成失败: {result.message}")

        except Exception as e:
            yield event.plain_result(f"生成失败: {str(e)}")

    @filter.command("图生视频")
    async def handle_image_to_video(self, event: AstrMessageEvent):
        """处理图生视频请求
        格式：/图生视频 提示词 横图/竖图 [图片]
        """
        message = event.message_str
        images = event.get_message_images()

        # 检查命令格式
        parts = message.split()
        if len(parts) < 3 or parts[2] not in ["横图", "竖图"]:
            yield event.plain_result("请使用正确的命令格式：/图生视频 提示词 横图/竖图 [图片]")
            return

        # 检查是否包含图片
        if not images:
            yield event.plain_result("请在命令后附带一张图片")
            return

        prompt = parts[1]
        is_horizontal = parts[2] == "横图"
        size = "1920*1080" if is_horizontal else "1080*1920"

        yield event.plain_result("正在生成视频，请稍候...")

        try:
            # API调用
            rsp = VideoSynthesis.async_call(
                api_key=self.api_key,
                model=self.config.get("video_model", "wanx2.1-i2v-turbo"),
                prompt=prompt,
                prompt_extend=self.config.get("prompt_extend", False),
                img_url=images[0].url,
                size=size
            )

            result = await asyncio.to_thread(VideoSynthesis.wait, rsp)

            if result.status_code == 200:
                video_url = result.output.video_url
                chain = [
                    Plain(f"生成完成!\n提示词：{prompt}\n"),
                    Video.fromURL(video_url)
                ]
                yield event.chain_result(chain)
            else:
                yield event.plain_result(f"生成失败: {result.message}")

        except Exception as e:
            yield event.plain_result(f"生成失败: {str(e)}")

    def _extract_prompt(self, message: str) -> str:
        """从消息中提取提示词
        Args:
            message: 原始消息内容
        Returns:
            str: 提取出的提示词
        """
        # 移除所有触发词
        for kw in self.image_keywords + self.video_keywords + self.i2v_keywords:
            message = message.replace(kw, "")
        return message.strip()