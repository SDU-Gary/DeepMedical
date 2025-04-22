import logging
import functools
from typing import Any, Callable, Type, TypeVar, Optional

# 导入必要的回调类型
from langchain_core.callbacks import CallbackManagerForToolRun, AsyncCallbackManagerForToolRun
from langchain_core.tools import BaseTool # 如果需要更严格的类型提示，导入 BaseTool

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseTool) # 将 T 约束为 BaseTool 的子类，以获得更好的类型提示


def log_io(func: Callable) -> Callable:
    """
    一个装饰器，用于记录工具函数的输入参数和输出。
    (这个装饰器可能主要用于简单的 @tool 函数，而不是类。
     如果这些函数也期望回调参数，可能需要类似的调整)

    Args:
        func: 需要被装饰的工具函数

    Returns:
        包装后的带有输入/输出日志记录的函数
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # 记录输入参数
        func_name = func.__name__
        # 检查 'callbacks' 或 'run_manager' 是否在 kwargs 中以便记录
        all_params_dict = kwargs.copy()
        # 可能的回调参数名称
        callback_arg_names = ['callbacks', 'run_manager']
        callback_arg_val = None
        callback_arg_name = '' # 记录实际使用的回调参数名
        for name in callback_arg_names:
            if name in all_params_dict:
                callback_arg_val = all_params_dict.pop(name) # 从字典中移除以便清晰记录参数
                callback_arg_name = name
                break # 假设只传递一个回调参数

        params_list = [*(str(arg) for arg in args), *(f"{k}={v}" for k, v in all_params_dict.items())]
        if callback_arg_val:
            params_list.append(f"{callback_arg_name}=<{type(callback_arg_val).__name__}>") # 记录回调类型

        params = ", ".join(params_list)

        logger.debug(f"工具 {func_name} 调用，参数: {params}")

        # 执行函数 - 如果存在回调参数，则传回
        if callback_arg_val:
            kwargs[callback_arg_name] = callback_arg_val # 将其放回以便函数调用
        result = func(*args, **kwargs)

        # 记录输出
        # 注意：记录大型结果时要小心
        try:
            result_repr = repr(result)
            if len(result_repr) > 500: # 限制日志大小
                 result_repr = result_repr[:500] + "..."
        except Exception:
            result_repr = "[无法表示结果]"
        logger.debug(f"工具 {func_name} 返回: {result_repr}")

        return result

    return wrapper


class LoggedToolMixin:
    """
    一个 Mixin 类，为 BaseTool 子类添加日志记录功能，
    并确保回调管理器被正确传递。
    """

    def _log_operation(self, method_name: str, args: tuple, kwargs: dict) -> None:
        """辅助方法，用于记录工具操作，为了清晰起见排除 run_manager。"""
        tool_name = self.__class__.__name__.replace("Logged", "")
        # 将 run_manager 从 kwargs 中分离出来以便更清晰地记录
        log_kwargs = kwargs.copy()
        run_manager = log_kwargs.pop('run_manager', None) # 如果存在 run_manager，则移除

        params = ", ".join(
            [*(str(arg) for arg in args), *(f"{k}={v}" for k, v in log_kwargs.items())]
        )
        logger.debug(f"工具 {tool_name}.{method_name} 调用，参数: {params}")
        if run_manager:
            logger.debug(f"  (附带 run_manager，类型: {type(run_manager).__name__})")
        else:
             logger.debug(f"  (未附带 run_manager)")

    # --- 修正后的 _run 方法 ---
    def _run(
        self,
        *args: Any,
        run_manager: Optional[CallbackManagerForToolRun] = None, # 显式接受 run_manager
        **kwargs: Any
    ) -> Any:
        """重写 _run 方法以添加日志记录并正确传递 run_manager。"""
        # 使用辅助方法记录输入
        self._log_operation("_run", args, kwargs)

        # 调用父类的 _run 方法，显式传递 run_manager
        # 这假设 MRO 中的下一个类（例如 FastAbstractTool）接受 run_manager
        result = super()._run(*args, run_manager=run_manager, **kwargs)

        # 记录输出
        try:
            result_repr = repr(result)
            if len(result_repr) > 500: # 限制日志大小
                 result_repr = result_repr[:500] + "..."
        except Exception:
            result_repr = "[无法表示结果]"
        logger.debug(
            f"工具 {self.__class__.__name__.replace('Logged', '')}._run 返回: {result_repr}"
        )
        return result

    # --- 添加了 _arun 方法以实现异步兼容性 ---
    async def _arun(
        self,
        *args: Any,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None, # 显式接受异步 run_manager
        **kwargs: Any
    ) -> Any:
        """重写 _arun 方法以添加日志记录并正确传递 run_manager。"""
        # 使用辅助方法记录输入
        self._log_operation("_arun", args, kwargs)

        # 调用父类的 _arun 方法，显式传递 run_manager
        # 这假设 MRO 中的下一个类提供了 _arun 或者 BaseTool 会处理它
        # （BaseTool 提供了默认的 _arun 会调用 _run，所以这通常可行）
        result = await super()._arun(*args, run_manager=run_manager, **kwargs)

        # 记录输出
        try:
            result_repr = repr(result)
            if len(result_repr) > 500: # 限制日志大小
                 result_repr = result_repr[:500] + "..."
        except Exception:
            result_repr = "[无法表示结果]"
        logger.debug(
            f"工具 {self.__class__.__name__.replace('Logged', '')}._arun 返回: {result_repr}"
        )
        return result


def create_logged_tool(base_tool_class: Type[T]) -> Type[T]:
    """
    工厂函数，用于创建任何 BaseTool 子类的日志记录版本。

    Args:
        base_tool_class: 需要增强日志记录功能的原始 BaseTool 子类。

    Returns:
        一个同时继承自 LoggedToolMixin 和基础工具类的新类，
        确保回调被正确处理。
    """
    # 如果使用严格类型提示，请确保基类确实是 BaseTool 子类
    if not issubclass(base_tool_class, BaseTool):
        logger.warning(f"create_logged_tool 用于非 BaseTool 类 '{base_tool_class.__name__}'。回调处理可能不适用。")

    class LoggedTool(LoggedToolMixin, base_tool_class):
        pass

    # 为类设置一个更具描述性的名称
    LoggedTool.__name__ = f"Logged{base_tool_class.__name__}"
    LoggedTool.__doc__ = base_tool_class.__doc__ # 保留原始文档字符串
    return LoggedTool