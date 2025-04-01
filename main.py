from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api.all import *
from astrbot.api.message_components import *
import subprocess
import sys
import importlib
import re
import asyncio

@register("astrbot_plugin_tongyipainting", "Cheng-MaoMao", "通过阿里云通义生成绘画", "1.0.0", "https://github.com/Cheng-MaoMao/astrbot_plugin_tongyipainting")
class MyPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "wanx2.1-t2i-turbo")
        self.prompt_extend = config.get("prompt_extend",False)

        # 检查并安装 dashscope
        if not self._check_dashscope():
            self._install_dashscope()
        
        # 导入 dashscope
        global ImageSynthesis
        from dashscope import ImageSynthesis
    
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
    async def generate_image(self, event: AstrMessageEvent):
        """监听所有消息,处理文生图命令"""
        message = event.message_str
        
        # 检查是否是文生图命令
        if not message.startswith("文生图"):
            return
            
        # 检查是否配置了API密钥
        if not self.api_key:
            yield event.plain_result("\n请联系管理员配置文生图API密钥")
            return

        # 移除命令前缀并检查格式
        message = message.replace("文生图", "").strip()
        if not message or message == "横着" or message == "竖着":
            yield event.plain_result("\n请按照正确格式：文生图 提示词 横着/竖着")
            return
        
        # 设置图片尺寸
        size = "1440*810"  # 默认横向 16:9
        if "竖着" in message:
            size = "810*1440"  # 竖向 9:16
            message = message.replace("竖着", "").strip()
        elif "横着" in message:
            message = message.replace("横着", "").strip()
        
        # 获取提示词
        prompt = message.strip()
        if not prompt:
            yield event.plain_result("\n请按照正确格式：文生图 提示词 横着/竖着")
            return

        # 发送正在生成的提示
        yield event.plain_result("\n正在生成图片，请稍候...")

        # 调用异步图像生成方法
        image_url = await self.generate_image_async(prompt, "", size)
        if image_url:
            chain = [
                Plain(f"\n提示词：{prompt}\n大小：{size}\n"),
                Image.fromURL(image_url)
            ]
            yield event.chain_result(chain)
        else:
            yield event.plain_result("\n生成图片失败")

    async def generate_image_async(self, prompt, negative_prompt, size):
        """异步生成图像并返回图像URL"""
        try:
            # 如果启用了prompt_extend，则添加该参数
            params = {
                "api_key": self.api_key,
                "model": self.model,
                "prompt": prompt,
                "n": 1,
                "size": size,
                "prompt_extend": self.prompt_extend
            }
            
            if negative_prompt:
                params["negative_prompt"] = negative_prompt
            
            # 创建异步任务
            task_rsp = ImageSynthesis.async_call(**params)
            
            if task_rsp.status_code != 200:
                raise Exception(f"任务提交失败: {task_rsp.message}")
            
            # 等待任务完成
            result_rsp = await asyncio.to_thread(ImageSynthesis.wait, task_rsp, api_key=self.api_key)
            
            if result_rsp.status_code == 200:
                results = result_rsp.output.results
                if results and results[0].url:
                    return results[0].url
                else:
                    raise Exception("任务成功，但没有返回图像结果")
            else:
                raise Exception(f"任务失败: {result_rsp.message}")
        
        except Exception as e:
            print(f"生成图片失败: {str(e)}")
            return None
