import asyncio
import importlib
import re
import subprocess
import sys
from dashscope import ImageSynthesis, VideoSynthesis
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
        self.model = config.get("model", "wanx2.1-t2i-turbo")
        self.trigger_words = config.get("trigger_words", {})

        # 初始化各功能的触发词列表
        self.image_keywords = self.trigger_words.get("image_keywords", "").split(",")
        self.video_keywords = self.trigger_words.get("video_keywords", "").split(",")
        self.i2v_keywords = self.trigger_words.get("i2v_keywords", "").split(",")

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

    async def handle_image_generation(self, event: AstrMessageEvent, message: str):
        """处理文生图请求
        Args:
            event: 消息事件对象
            message: 消息内容
        """
        # 提取提示词
        prompt = self._extract_prompt(message)
        if not prompt:
            yield event.plain_result("请提供绘画内容描述")
            return

        yield event.plain_result("正在生成图片，请稍候...")

        try:
            # 调用文生图API
            rsp = ImageSynthesis.async_call(
                api_key=self.api_key,
                model=self.model,
                prompt=prompt,
                n=1,
                size="1024*1024"
            )

            # 等待生成完成
            result = await asyncio.to_thread(ImageSynthesis.wait, rsp)

            if result.status_code == 200:
                # 获取生成的图片URL并发送
                image_url = result.output.results[0].url
                chain = [
                    Plain(f"生成完成!\n提示词：{prompt}\n"),
                    Image.fromURL(image_url)
                ]
                yield event.chain_result(chain)
            else:
                yield event.plain_result(f"生成失败: {result.message}")

        except Exception as e:
            yield event.plain_result(f"生成失败: {str(e)}")

    async def handle_video_generation(self, event: AstrMessageEvent, message: str):
        """处理文生视频请求
        Args:
            event: 消息事件对象
            message: 消息内容
        """
        prompt = self._extract_prompt(message)
        if not prompt:
            yield event.plain_result("请提供视频内容描述")
            return

        yield event.plain_result("正在生成视频，请稍候...")

        try:
            # 调用文生视频API
            rsp = VideoSynthesis.async_call(
                api_key=self.api_key,  # 添加api_key参数
                model='wanx2.1-t2v-turbo',
                prompt=prompt,
                size='1280*720'
            )

            # 等待生成完成
            result = await asyncio.to_thread(VideoSynthesis.wait, rsp)

            if result.status_code == 200:
                # 获取生成的视频URL并发送
                video_url = result.output.video_url
                # 使用Video.fromURL构建视频消息
                chain = [
                    Plain(f"生成完成!\n提示词：{prompt}\n"),
                    Video.fromURL(url=video_url)  # 明确指定url参数
                ]
                yield event.chain_result(chain)
            else:
                yield event.plain_result(f"生成失败: {result.message}")

        except Exception as e:
            yield event.plain_result(f"生成失败: {str(e)}")

    async def handle_image_to_video(self, event: AstrMessageEvent, message: str):
        """处理图生视频请求
        Args:
            event: 消息事件对象
            message: 消息内容
        """
        # 检查是否包含图片
        images = event.get_message_images()
        if not images:
            yield event.plain_result("请提供一张图片")
            return

        # 提取提示词
        prompt = self._extract_prompt(message)
        if not prompt:
            prompt = "生成一段流畅自然的视频"  # 默认提示词

        yield event.plain_result("正在生成视频，请稍候...")

        try:
            # 调用图生视频API
            rsp = VideoSynthesis.async_call(
                api_key=self.api_key,
                model='wanx2.1-i2v-turbo',
                prompt=prompt,
                img_url=images[0].url  # 使用第一张图片的URL
            )

            # 等待生成完成
            result = await asyncio.to_thread(VideoSynthesis.wait, rsp)

            if result.status_code == 200:
                # 获取生成的视频URL并发送
                video_url = result.output.video_url
                chain = [
                    Plain(f"生成完成!\n提示词：{prompt}\n"),
                    Video.fromURL(url=video_url)  # 明确指定url参数
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