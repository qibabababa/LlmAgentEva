#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API客户端模块
处理与LLM API的通信
"""

import json
import time
import logging
import requests
from typing import List, Dict, Any, Optional, Iterator
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)

from lib.core.config_manager import get_config
from lib.core.logger import get_logger

# 创建logger
logger = get_logger(__name__)


class APIClient:
    """
    LLM API客户端
    支持流式和非流式调用，带重试和错误处理
    """
    
    def __init__(self, 
                 api_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 model: Optional[str] = None,
                 timeout: Optional[int] = None):
        """
        初始化API客户端
        
        Args:
            api_url: API地址（可选，默认从配置读取）
            api_key: API密钥（可选，默认从配置读取）
            model: 模型名称（可选，默认从配置读取）
            timeout: 超时时间（可选，默认从配置读取）
        """
        config = get_config()
        
        self.api_url = api_url or config.api.base_url
        self.api_key = api_key or config.api.api_key
        self.model = model or config.api.default_model
        self.timeout = timeout or config.api.timeout
        self.temperature = config.api.temperature
        self.max_retries = config.api.max_retries
        
        logger.info(f"API客户端已初始化: model={self.model}, timeout={self.timeout}s, max_retries={self.max_retries}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.Timeout, 
                                       requests.exceptions.ConnectionError,
                                       requests.exceptions.HTTPError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG)
    )
    def chat_completion(self,
                       messages: List[Dict[str, str]],
                       model: Optional[str] = None,
                       temperature: Optional[float] = None,
                       stream: bool = False,
                       tools: Optional[List[Dict]] = None,
                       **kwargs) -> Dict[str, Any]:
        """
        聊天补全请求（非流式）
        
        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数
            stream: 是否流式（此方法固定为False）
            tools: 工具定义
            **kwargs: 其他参数
            
        Returns:
            API响应
            
        Raises:
            APIError: API调用失败
            requests.exceptions.Timeout: 请求超时
            requests.exceptions.ConnectionError: 连接错误
        """
        start_time = time.time()
        used_model = model or self.model
        
        logger.debug(f"发起API请求: model={used_model}, messages={len(messages)}条, tools={len(tools) if tools else 0}个")
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        
        payload = {
            "model": used_model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "stream": False
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")
        
        # 添加其他参数
        for key, value in kwargs.items():
            if key not in payload and key != "tool_choice":
                payload[key] = value
        
        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            
            # 记录响应时间
            elapsed = time.time() - start_time
            
            if response.status_code != 200:
                error_msg = f"API请求失败: HTTP {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {response.text[:500]}"
                
                logger.error(f"{error_msg} (耗时: {elapsed:.2f}秒)")
                raise APIError(error_msg, status_code=response.status_code)
            
            result = response.json()
            
            # 记录成功的API调用
            usage = result.get('usage', {})
            logger.info(
                f"API调用成功: model={used_model}, "
                f"耗时={elapsed:.2f}秒, "
                f"prompt_tokens={usage.get('prompt_tokens', 'N/A')}, "
                f"completion_tokens={usage.get('completion_tokens', 'N/A')}"
            )
            
            return result
            
        except requests.exceptions.Timeout as e:
            logger.error(f"API请求超时 (>{self.timeout}秒): {str(e)}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"API连接失败: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"API请求发生未预期错误: {type(e).__name__}: {str(e)}")
            raise
    
    def chat_completion_stream(self,
                              messages: List[Dict[str, str]],
                              model: Optional[str] = None,
                              temperature: Optional[float] = None,
                              tools: Optional[List[Dict]] = None,
                              max_retries: Optional[int] = None,
                              **kwargs) -> Iterator[Dict[str, Any]]:
        """
        聊天补全请求（流式）
        
        注意：流式请求的重试逻辑在生成器内部处理
        
        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数
            tools: 工具定义
            max_retries: 最大重试次数（可选）
            **kwargs: 其他参数
            
        Yields:
            API响应chunk
            
        Raises:
            APIError: API调用失败
        """
        used_model = model or self.model
        retry_count = 0
        max_retry = max_retries if max_retries is not None else self.max_retries
        
        while retry_count <= max_retry:
            try:
                logger.debug(
                    f"发起流式API请求 (尝试 {retry_count + 1}/{max_retry + 1}): "
                    f"model={used_model}, messages={len(messages)}条"
                )
                
                start_time = time.time()
                
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream'
                }
                
                payload = {
                    "model": used_model,
                    "messages": messages,
                    "temperature": temperature or self.temperature,
                    "stream": True
                }
                
                if tools:
                    payload["tools"] = tools
                    payload["tool_choice"] = kwargs.get("tool_choice", "auto")
                
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=(30, 60),  # (连接超时, 读取超时): 30秒连接，60秒每次读取
                    stream=True
                )
                
                if response.status_code != 200:
                    error_msg = f"流式API请求失败: HTTP {response.status_code}"
                    try:
                        error_detail = response.json()
                        error_msg += f" - {error_detail}"
                    except:
                        error_msg += f" - {response.text[:500]}"
                    
                    logger.error(error_msg)
                    
                    if retry_count < max_retry:
                        wait_time = min(2 ** retry_count, 10)
                        logger.warning(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                        retry_count += 1
                        continue
                    else:
                        raise APIError(error_msg, status_code=response.status_code)
                
                # 流式响应成功，开始yield chunks
                chunk_count = 0
                first_chunk_time = None
                last_chunk_time = time.time()  # 记录最后一个chunk的时间
                chunk_timeout = 60  # 单个chunk的超时时间（秒）
        
                # 处理SSE响应
                buffer = ""
                byte_buffer = b""  # 用于累积不完整的UTF-8字节
                try:
                    for chunk_bytes in response.iter_content(chunk_size=None, decode_unicode=False):
                        # 收到任何数据（包括空chunk）都更新时间戳
                        current_time = time.time()
                        
                        # 检查距离上次收到数据是否超时
                        if current_time - last_chunk_time > chunk_timeout:
                            logger.error(f"流式响应超时: {chunk_timeout}秒内未收到任何数据")
                            raise TimeoutError(f"流式响应超时: {chunk_timeout}秒内未收到任何数据")
                        
                        # 更新最后接收时间
                        last_chunk_time = current_time
                        
                        if not chunk_bytes:
                            continue
                        
                        # 累积字节到缓冲区
                        byte_buffer += chunk_bytes
                        
                        # 尝试解码，如果失败说明UTF-8字符被截断
                        try:
                            chunk_text = byte_buffer.decode('utf-8')
                            byte_buffer = b""  # 解码成功，清空字节缓冲区
                            buffer += chunk_text
                        except UnicodeDecodeError as e:
                            # UTF-8字符被截断，保留字节缓冲区，等待下一个chunk
                            # 只保留可能不完整的末尾字节（通常是1-3个字节）
                            if len(byte_buffer) > 100:  # 如果缓冲区太大，说明可能有其他问题
                                logger.warning(f"UTF-8字节缓冲区过大({len(byte_buffer)}字节)，尝试部分解码")
                                # 尝试解码前面完整的部分
                                for i in range(len(byte_buffer) - 1, max(0, len(byte_buffer) - 4), -1):
                                    try:
                                        chunk_text = byte_buffer[:i].decode('utf-8')
                                        buffer += chunk_text
                                        byte_buffer = byte_buffer[i:]  # 保留未解码的部分
                                        break
                                    except UnicodeDecodeError:
                                        continue
                            # 否则继续等待下一个chunk
                            continue
                        
                        # 按SSE事件分割
                        while '\n\n' in buffer or '\r\n\r\n' in buffer:
                            if '\r\n\r\n' in buffer:
                                event, buffer = buffer.split('\r\n\r\n', 1)
                            else:
                                event, buffer = buffer.split('\n\n', 1)
                            
                            event = event.strip()
                            if not event:
                                continue
                            
                            # 提取JSON
                            if event.startswith('data:'):
                                json_str = event[5:].strip()
                            elif event.startswith('data: '):
                                json_str = event[6:].strip()
                            else:
                                continue
                            
                            if json_str == '[DONE]':
                                elapsed = time.time() - start_time
                                logger.info(
                                    f"流式API完成: model={used_model}, "
                                    f"chunks={chunk_count}, 耗时={elapsed:.2f}秒"
                                )
                                return
                            
                            try:
                                chunk = json.loads(json_str)
                                chunk_count += 1
                                
                                if chunk_count == 1:
                                    first_chunk_time = time.time() - start_time
                                    logger.debug(f"收到首个chunk (TTFB: {first_chunk_time:.2f}秒)")
                                elif chunk_count % 50 == 0:  # 每50个chunk打印一次进度
                                    logger.debug(f"已接收 {chunk_count} 个chunks...")
                                
                                yield chunk
                            except json.JSONDecodeError as e:
                                logger.warning(f"解析chunk JSON失败: {e}, json_str={json_str[:100]}")
                                continue
                    
                    # 流结束，处理可能残留的字节
                    if byte_buffer:
                        logger.warning(f"流结束时有残留字节({len(byte_buffer)}字节)，尝试解码")
                        try:
                            chunk_text = byte_buffer.decode('utf-8', errors='ignore')
                            buffer += chunk_text
                        except Exception as e:
                            logger.warning(f"解码残留字节失败: {e}")
                    
                    # 处理可能残留在buffer中的事件
                    if buffer.strip():
                        logger.debug(f"流结束时buffer有残留数据: {buffer[:100]}")
                    
                    elapsed = time.time() - start_time
                    logger.info(
                        f"流式API完成: model={used_model}, "
                        f"chunks={chunk_count}, 耗时={elapsed:.2f}秒"
                    )
                    return
                    
                except UnicodeDecodeError as e:
                    logger.error(f"UTF-8解码错误: {e}")
                    if retry_count < max_retry:
                        wait_time = min(2 ** retry_count, 10)
                        logger.warning(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                        retry_count += 1
                        continue
                    else:
                        raise APIError(f"UTF-8解码失败: {e}")
                        
                except requests.exceptions.ChunkedEncodingError as e:
                    logger.error(f"流式传输中断: {e}")
                    if retry_count < max_retry:
                        wait_time = min(2 ** retry_count, 10)
                        logger.warning(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                        retry_count += 1
                        continue
                    else:
                        raise APIError(f"流式传输失败: {e}")
                
                except TimeoutError as e:
                    logger.error(f"流式响应超时: {e}")
                    if retry_count < max_retry:
                        wait_time = min(2 ** retry_count, 10)
                        logger.warning(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                        retry_count += 1
                        continue
                    else:
                        raise APIError(f"流式响应超时: {e}")
                        
            except (requests.exceptions.Timeout, 
                    requests.exceptions.ConnectionError) as e:
                logger.error(f"流式API连接错误: {type(e).__name__}: {e}")
                if retry_count < max_retry:
                    wait_time = min(2 ** retry_count, 10)
                    logger.warning(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    retry_count += 1
                    continue
                else:
                    raise
            except Exception as e:
                logger.error(f"流式API发生未预期错误: {type(e).__name__}: {e}")
                raise
    
    def reconstruct_from_stream(self, stream: Iterator[Dict[str, Any]]) -> Dict[str, Any]:
        """
        从流式响应重构完整响应
        
        Args:
            stream: 流式响应生成器
            
        Returns:
            完整的响应对象
        """
        final_resp = {}
        tool_calls_accumulator = []
        chunk_count = 0
        
        for chunk in stream:
            chunk_count += 1
            
            if not final_resp:
                final_resp = {
                    "id": chunk.get("id", "unknown"),
                    "model": chunk.get("model", "unknown"),
                    "object": chunk.get("object", "chat.completion"),
                    "created": chunk.get("created", int(time.time())),
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "",
                        },
                        "finish_reason": None
                    }]
                }
            
            delta = chunk.get('choices', [{}])[0].get('delta', {})
            
            # 累加内容
            if 'content' in delta and delta['content']:
                final_resp["choices"][0]["message"]["content"] += delta['content']
            
            # 累加工具调用
            if "tool_calls" in delta:
                for tool_call_delta in delta["tool_calls"]:
                    index = tool_call_delta.get("index", 0)
                    
                    if index >= len(tool_calls_accumulator):
                        tool_calls_accumulator.append({
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""}
                        })
                    
                    if "id" in tool_call_delta:
                        tool_calls_accumulator[index]["id"] = tool_call_delta["id"]
                    if "function" in tool_call_delta:
                        if "name" in tool_call_delta["function"]:
                            tool_calls_accumulator[index]["function"]["name"] += tool_call_delta["function"]["name"]
                        if "arguments" in tool_call_delta["function"]:
                            tool_calls_accumulator[index]["function"]["arguments"] += tool_call_delta["function"]["arguments"]
            
            # 更新完成原因
            finish_reason = chunk.get('choices', [{}])[0].get('finish_reason')
            if finish_reason:
                final_resp["choices"][0]["finish_reason"] = finish_reason
        
        # 添加工具调用到最终响应
        if tool_calls_accumulator:
            final_resp["choices"][0]["message"]["tool_calls"] = tool_calls_accumulator
        
        if not final_resp:
            raise RuntimeError(f"流式API没有返回任何数据 (收到 {chunk_count} 个chunk)")
        
        return final_resp


class APIError(Exception):
    """API调用错误"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


# 便捷函数
def create_client(**kwargs) -> APIClient:
    """创建API客户端"""
    return APIClient(**kwargs)


if __name__ == "__main__":
    # 测试
    client = APIClient()
    print(f"API客户端已创建")
    print(f"  URL: {client.api_url}")
    print(f"  Model: {client.model}")
