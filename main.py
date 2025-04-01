import subprocess
import sys
import importlib
import asyncio

from typing import Optional, List
from dashscope import ImageSynthesis, VideoSynthesis
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain, Image, Video
from astrbot.api.event import MessageChain


@register("astrbot_plugin_tongyipainting", "Cheng-MaoMao", "通过阿里云通义生成绘画和视频", "1.0.3",
          "https://github.com/Cheng-MaoMao/astrbot_plugin_tongyipainting")
class TongyiPainting(Star):
    def __init__(self, context: Context, config: dict):
        """初始化插件"""
        super().__init__(context)
        self.config = config
        self.api_key = config.get("api_key", "")

        # 检查并安装必要的依赖包
        if not self._check_package("dashscope"):
            self._install_package("dashscope")

    def _check_package(self, package: str) -> bool:
        try:
            importlib.import_module(package)
            return True
        except ImportError:
            return False

    def _install_package(self, package: str):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", package])
            print(f"成功安装 {package}")
        except subprocess.CalledProcessError as e:
            print(f"安装 {package} 失败: {str(e)}")
            raise

    @filter.command("文生图")
    async def text_to_image(self, event: AstrMessageEvent, prompt: str = "", mode: str = ""):
        """处理文生图请求"""
        if not self.api_key:
            yield event.plain_result("请配置API密钥")
            return

        if not prompt or mode not in ["横图", "竖图"]:
            yield event.plain_result("请使用正确的命令格式：/文生图 提示词 横图/竖图")
            return

        size = "1920*1080" if mode == "横图" else "1080*1920"
        yield event.plain_result("正在生成图片，请稍候...")

        try:
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
                chain = [
                    Plain(f"生成完成!\n提示词：{prompt}\n"),
                    Image.fromURL(image_url)
                ]
                yield event.chain_result(chain)
            else:
                yield event.plain_result(f"生成失败: {result.message}")

        except Exception as e:
            yield event.plain_result(f"生成失败: {str(e)}")

    @filter.command("文生视频")
    async def text_to_video(self, event: AstrMessageEvent, prompt: str = "", mode: str = ""):
        """处理文生视频请求"""
        if not self.api_key:
            yield event.plain_result("请配置API密钥")
            return

        if not prompt or mode not in ["横图", "竖图"]:
            yield event.plain_result("请使用正确的命令格式：/文生视频 提示词 横图/竖图")
            return

        size = "1920*1080" if mode == "横图" else "1080*1920"
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
                chain = [
                    Plain(f"生成完成!\n提示词：{prompt}\n"),
                    Video.fromURL(video_url)
                ]
                yield event.chain_result(chain)
            else:
                yield event.plain_result(f"生成失败: {result.message}")

        except Exception as e:
            yield event.plain_result(f"生成失败: {str(e)}")

    @filter.command("图生视频")
    async def image_to_video(self, event: AstrMessageEvent, prompt: str = "", mode: str = ""):
        """处理图生视频请求"""
        if not self.api_key:
            yield event.plain_result("请配置API密钥")
            return

        if not prompt or mode not in ["横图", "竖图"]:
            yield event.plain_result("请使用正确的命令格式：/图生视频 提示词 横图/竖图 [图片]")
            return

        images = event.get_message_images()
        if not images:
            yield event.plain_result("请在命令后附带一张图片")
            return

        size = "1920*1080" if mode == "横图" else "1080*1920"
        yield event.plain_result("正在生成视频，请稍候...")

        try:
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