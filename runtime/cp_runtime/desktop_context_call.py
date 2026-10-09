"""中文：Desktop 读取调用统一序列化一次，不手工转义 JavaScript。

English: Canonical Desktop reader calls: serialize once, never hand-escape JavaScript.
"""
from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath

from .routing_contract import fail


def _shell_path(value: str) -> str:
    if not isinstance(value, str) or not value or any(char in value for char in "'\r\n\0"):
        fail("CONTEXT_V2_COMMAND_PATH")
    windows = PureWindowsPath(value)
    if windows.is_absolute():
        if ".." in windows.parts:
            fail("CONTEXT_V2_COMMAND_PATH")
        # 中文：扩展设备路径保持原生命名空间写法；后续 JSON 序列化仍保护 JavaScript 中的每个反斜杠。
        # English: Extended device paths preserve their native namespace spelling; JSON
        # serialization below still protects every backslash through JavaScript.
        return value if value.startswith("\\\\?\\") else windows.as_posix()
    if not Path(value).is_absolute() or ".." in Path(value).parts:
        fail("CONTEXT_V2_COMMAND_PATH")
    return value


def reader_call(*, python_path: str, reader_path: str, grant_path: str, recovery: bool = False,
                expected_output_chars: int | None = None, output_limit: int = 8192,
                output_tokens: int = 10000, delivery_contract: str | None = None) -> dict:
    """中文：返回精确的 shell 命令、工具对象和代码模式调用。输入是控制器拥有且已验证的运行时与许可路径，不接受模型自造路径；执行门禁比较同一规范命令。
    
    English: Return the exact shell command, tool object and code-mode invocation.
    
    Inputs are controller-owned validated runtime/grant paths, never model paths.
    The execution guard must compare against this same canonical command.
    """
    python, reader, grant = map(_shell_path, (python_path, reader_path, grant_path))
    command = "& '{}' -I -B '{}' '{}'".format(python, reader, grant)
    if (output_limit,output_tokens) not in ({(196608,50000)} if delivery_contract=='same-call-notify/2' else {(8192,10000),(65536,50000)}) or delivery_contract not in {None,'same-call-notify/2'}:
        fail("CONTEXT_V2_OUTPUT_PROFILE")
    parameters = {"cmd": command, "max_output_tokens": output_tokens}
    encoded = json.dumps(parameters, ensure_ascii=True, separators=(",", ":"))
    javascript = "const result = await tools.exec_command(" + encoded + ");\ntext(result);"
    if recovery:
        from .context_recovery_v2 import MAX_ATTEMPTS, MAX_ELAPSED_MS
        if expected_output_chars is not None and (type(expected_output_chars) is not int or not 1 <= expected_output_chars <= output_limit):
            fail("CONTEXT_V2_EXPECTED_OUTPUT_SIZE")
        length_check = "true" if expected_output_chars is None else f"result.output.length === {expected_output_chars}"
        # 中文：程序决定重试，Hook 决定许可。English: retries are generated, each admission remains guarded.
        javascript = (
            "const started = Date.now();\n"
            f"for (let attempt = 0; attempt < {MAX_ATTEMPTS}; attempt++) {{\n"
            "  try {\n"
            "    const result = await tools.exec_command(" + encoded + ");\n"
            "    if (result.exit_code === 0 && typeof result.output === 'string') {\n"
            "      let complete = false;\n"
            "      try { JSON.parse(result.output); complete = result.output.endsWith('\\n') && " + length_check + "; } catch (_) {}\n"
            "      if (!complete) {\n"
            f"        if (attempt + 1 < {MAX_ATTEMPTS} && Date.now() - started <= {MAX_ELAPSED_MS}) {{\n"
            "          await new Promise(resolve => setTimeout(resolve, 100)); continue;\n"
            "        }\n"
            "      }\n"
            "    }\n"
            "    text(result); break;\n"
            "  } catch (error) {\n"
            f"    if (!String(error).includes('CONTEXT_V2_RETRY_RECEIPT') || attempt + 1 >= {MAX_ATTEMPTS}\n"
            f"        || Date.now() - started > {MAX_ELAPSED_MS}) throw error;\n"
            "    await new Promise(resolve => setTimeout(resolve, 100));\n"
            "  }\n"
            "}"
        )
    if output_tokens != 10000:
        javascript='// @exec: {"max_output_tokens":50000}\n'+javascript
    return {"schema_version": "desktop-reader-call/2", "parameters": parameters, "javascript": javascript}
