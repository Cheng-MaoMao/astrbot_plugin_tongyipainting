from astrbot.api.event import filter, AstrMessageEvent, EventMessageType
from astrbot.api.star import Context, Star, register
from astrbot.api.all import *
from astrbot.api.message_components import *
import subprocess
import sys
import importlib
import re
import asyncio
from http import HTTPStatus

@register(
    "astrbot_plugin_tongyipainting",
    "Cheng-MaoMao",
    "基于阿里云百炼通义万相API的文生图/文生视频/图生视频插件",
    "1.0.8",
    "https://github.com/Cheng-MaoMao/astrbot_plugin_tongyipainting"
)
class TongyiPainting(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.api_key = config.get("api_key", "")
        self.image_model = config.get("image_model", "wanx2.1-t2i-turbo")
        self.t2v_model = config.get("t2v_model", "wanx2.1-t2v-turbo")
        self.i2v_model = config.get("i2v_model", "wanx2.1-i2v-turbo")
        self.prompt_extend = config.get("prompt_extend", False)

        # 检查并安装 dashscope
        if not self._check_dashscope():
            self._install_dashscope()
        
        # 导入必要的模块
        global ImageSynthesis, VideoSynthesis
        from dashscope import ImageSynthesis, VideoSynthesis
    
    def _check_dashscope(self) -> bool:
        """检查是否安装了 dashscope"""
        try:
            importlib.import_module('dashscope')
            return True
        except ImportError:
            return False

    def _install_dashscope(self):
        """安装 dashscope 包"""
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "dashscope"])
            print("成功安装 dashscope 包")
        except subprocess.CalledProcessError as e:
            print(f"安装 dashscope 包失败: {str(e)}")
            raise
    
    @filter.event_message_type(EventMessageType.ALL)
    async def handle_all_messages(self, event: AstrMessageEvent):
        """监听所有消息并处理图像和视频生成请求"""
        message = event.message_str
        
        # 处理图像生成命令
        if message.startswith(("/图像生成", "/画图")):
            async for result in self.handle_image_gen(event):
                yield result
            return
            
        # 处理视频生成命令
        if message.startswith(("/视频生成", "/生成视频")):
            async for result in self.handle_video_gen(event):
                yield result
            return

    @filter.command(["图像生成", "画图"])  # 可以添加多个命令触发词
    async def handle_image_gen(self, event: AstrMessageEvent):
        """处理文生图命令"""
        message = event.message_str
        
        # 移除命令前缀
        for prefix in ["/图像生成", "/画图"]:
            if message.startswith(prefix):
                message = message[len(prefix):].strip()
                break
        
        if not message:
            yield event.plain_result("\n请提供绘画内容的描述!")
            return
            
        # 检查是否配置了API密钥
        if not self.api_key:
            yield event.plain_result("\n请联系管理员配置API密钥")
            return

        # 检查方向参数
        size = "1280*720"  # 默认横屏
        if "竖着" in message:
            size = "720*1280"
            message = message.replace("竖着", "").strip()
        elif "横着" in message:
            message = message.replace("横着", "").strip()
        
        # 发送正在生成的提示
        yield event.plain_result("\n正在生成图片，请稍候...")

        try:
            # 调用同步图像生成方法
            response = ImageSynthesis.call(
                api_key=self.api_key,
                model=self.image_model,
                prompt=message,
                n=1,
                size=size
            )
            
            if response.status_code == HTTPStatus.OK:
                image_url = response.output.results[0].url
                chain = [
                    Plain(f"\n提示词：{message}\n方向：{'竖版' if size=='720*1280' else '横版'}\n"),
                    Image.fromURL(image_url)
                ]
                yield event.chain_result(chain)
            else:
                error_msg = (f"\n生成图片失败:\n"
                            f"HTTP状态码: {response.status_code}\n"
                            f"错误代码: {response.code}\n"
                            f"错误信息: {response.message}")
                yield event.plain_result(error_msg)

        except Exception as e:
            error_msg = (f"\n生成图片时发生错误:\n"
                        f"错误类型: {type(e).__name__}\n"
                        f"错误信息: {str(e)}")
            yield event.plain_result(error_msg)
    
    async def generate_image_async(self, prompt, negative_prompt, size):
        """异步生成图像并返回图像URL"""
        try:
            # 转换尺寸格式，DashScope API 使用 "width*height"
            api_size = size.replace('x', '*')
            
            # 创建异步任务
            task_rsp = ImageSynthesis.async_call(
                api_key=self.api_key,
                model=self.image_model,
                prompt=prompt,
                negative_prompt=negative_prompt if negative_prompt else None,
                n=1,
                size=api_size
            )
            
            if task_rsp.status_code != 200:
                raise Exception(f"任务提交失败: {task_rsp.message}")
            
            # 等待任务完成
            result_rsp = await asyncio.to_thread(ImageSynthesis.wait, task_rsp, api_key=self.api_key)
            
            if result_rsp.status_code == 200:
                results = result_rsp.output.results
                if results:
                    image_url = results[0].url
                    return image_url
                else:
                    raise Exception("任务成功，但没有返回图像结果")
            else:
                raise Exception(f"任务失败: {result_rsp.message}")
        
        except Exception as e:
            print(f"生成图片失败: {str(e)}")
            return None

    @filter.command(["视频生成", "生成视频"])  # 可以添加多个命令触发词
    async def handle_video_gen(self, event: AstrMessageEvent):
        """处理文生视频和图生视频命令"""
        message = event.message_str
        
        # 移除命令前缀
        for prefix in ["/视频生成", "/生成视频"]:
            if message.startswith(prefix):
                message = message[len(prefix):].strip()
                break
        
        if not message:
            yield event.plain_result("\n请提供视频生成的描述!")
            return
            
        if not self.api_key:
            yield event.plain_result("\n请联系管理员配置API密钥")
            return

        # 检查方向参数
        size = "1280*720"  # 默认横屏
        if "竖着" in message:
            size = "720*1280"
            message = message.replace("竖着", "").strip()
        elif "横着" in message:
            message = message.replace("横着", "").strip()

        # 检查是否是图生视频
        image_url = None
        if "图生视频" in message:
            # 提取图片URL
            message = message.replace("图生视频", "").strip()
            # 假设图片URL在消息的最后
            url_match = re.search(r'https?://\S+', message)
            if (url_match):
                image_url = url_match.group()
                message = message.replace(image_url, "").strip()
            else:
                yield event.plain_result("\n请提供有效的图片URL!")
                return

        yield event.plain_result("\n正在生成视频，请稍候...")

        try:
            if image_url:  # 图生视频
                response = VideoSynthesis.call(
                    model=self.i2v_model,
                    prompt=message,
                    img_url=image_url
                )
            else:  # 文生视频
                response = VideoSynthesis.call(
                    model=self.t2v_model,
                    prompt=message,
                    size=size
                )

            if response.status_code == HTTPStatus.OK:
                video_url = response.output.video_url
                chain = [
                    Plain(f"\n提示词：{message}\n"),
                    Video.fromURL(video_url)
                ]
                yield event.chain_result(chain)
            else:
                yield event.plain_result(f"\n生成视频失败: {response.message}")

        except Exception as e:
            yield event.plain_result(f"\n生成视频时发生错误: {str(e)}")
