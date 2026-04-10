# Textual 聊天壳：消息区 + 单行输入；ChatSession 为真源，RichLog 为投影；支持本地工具循环与流式回复。
from asyncio import CancelledError, Future, get_running_loop
from typing import ClassVar, override

from rich.markup import escape
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Input, RichLog, Rule
from textual.worker import Worker

from nocode.clipboard_image import get_clipboard_image
from nocode.env import NOCODE_LLM_MOONSHOT, project_root, resolved_llm_provider
from nocode.messages import (
    ChatSession,
    build_user_content_blocks,
    format_api_message_markup,
)
from nocode.streaming import format_stream_error, stream_assistant
from nocode.system_prompt import build_system_prompt
from nocode.tool_loop import run_tool_loop
from nocode.tools import (
    TodoItemState,
    ToolRuntime,
    UserQuestion,
    build_default_registry,
)
from nocode.welcome import WelcomePanel


def _normalize_newlines(text: str) -> str:
    """
    将文本中的换行符规范为 Unix 风格的 \\n，便于在 macOS/Linux/Windows 粘贴内容时表现一致。

    text: 原始字符串，可能含 \\r\\n（Windows）或单独 \\r。
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


class NocodeApp(App[None]):
    """最小聊天 shell：提交用户消息后流式请求模型，并将增量文本实时投影到日志区。"""

    CSS: ClassVar[str] = """
    #log { height: 1fr; background: $background; scrollbar-size: 0 0; }
    .input-rule { height: 1; margin: 0; color: $primary; }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+c", "quit", "退出", show=True),
        Binding("escape", "cancel_streaming", "中断", show=True),
        Binding("alt+v", "paste_clipboard_image", "贴图", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._session = ChatSession()
        self._pending_images: list[tuple[bytes, str | None]] = []
        self._streaming_worker: Worker[None] | None = None
        self._streaming_text = ""
        self._streaming_error: str | None = None
        self._todos_snapshot: list[TodoItemState] = []
        self._pending_tool_question: UserQuestion | None = None
        self._pending_tool_future: Future[str] | None = None
        self._tool_registry = build_default_registry()
        self._tool_runtime = ToolRuntime(
            workspace_root=project_root(),
            ask_user=self._ask_user_for_tool,
            on_todos_changed=self._set_todos_snapshot,
        )
        self._system_prompt = build_system_prompt(self._tool_registry.keys())

    @override
    def compose(self) -> ComposeResult:
        """构建界面: 欢迎面板 + 输入框 + 日志区（日志区在输入框下方扩展）"""
        yield WelcomePanel()
        yield Rule(classes="input-rule")
        yield Input(
            placeholder="输入后回车… Alt+V 贴剪贴板图片",
            id="msg",
            compact=True,
        )
        yield Rule(classes="input-rule")
        yield RichLog(id="log", highlight=True, markup=True)

    def on_mount(self) -> None:
        """禁止日志区聚焦；首帧布局完成后再聚焦输入框（避免 Input 仍为 0×0 时 focus 失败）。"""
        log_w = self.query_one("#log", RichLog)
        log_w.can_focus = False
        _ = self.call_after_refresh(self._focus_input_after_layout)

    def _focus_input_after_layout(self) -> None:
        log_w = self.query_one("#log", RichLog)
        log_w.can_focus = False
        if log_w.has_focus:
            log_w.blur()
        msg = self.query_one("#msg", Input)
        _ = msg.focus()

    def action_paste_clipboard_image(self) -> None:
        if self._has_active_stream():
            self.notify("正在生成回复，暂时不能继续贴图", severity="warning")
            return
        got = get_clipboard_image()
        if got is None:
            self.notify("剪贴板里没有可用的图片", severity="warning")
            return
        raw, mt = got
        self._pending_images.append((raw, mt))
        n = len(self._pending_images)
        self.notify(f"已添加剪贴板图片（共 {n} 张），回车发送")

    def _refresh_log(self) -> None:
        log_w = self.query_one("#log", RichLog)
        log_w.clear()
        for msg in self._session.messages:
            _ = log_w.write(format_api_message_markup(msg))
        if self._todos_snapshot:
            todo_body = " | ".join(
                f"{item.status}: {item.content}" for item in self._todos_snapshot
            )
            _ = log_w.write(f"[bold yellow]待办[/]: {escape(todo_body)}")
        if self._pending_tool_question is not None:
            question = self._pending_tool_question
            line = f"[bold magenta]工具提问[/]: {escape(question.question)}"
            if question.options:
                options = " / ".join(question.options)
                line += f" [dim]选项: {escape(options)}[/dim]"
            _ = log_w.write(line)
        if self._has_active_stream() and not self._streaming_error:
            if self._streaming_text:
                line = format_api_message_markup(
                    {"role": "assistant", "content": self._streaming_text}
                )
            else:
                line = "[bold blue]助手[/]: [dim]正在生成...[/dim]"
            _ = log_w.write(line)
        if self._streaming_error:
            _ = log_w.write(f"[bold red]错误[/]: {escape(self._streaming_error)}")

    def _has_active_stream(self) -> bool:
        return (
            self._streaming_worker is not None
            and not self._streaming_worker.is_finished
        )

    def _set_input_enabled(self, enabled: bool) -> None:
        msg = self.query_one("#msg", Input)
        msg.disabled = not enabled
        if enabled:
            _ = msg.focus()

    def action_cancel_streaming(self) -> None:
        if not self._has_active_stream():
            return
        assert self._streaming_worker is not None
        self._streaming_worker.cancel()
        self.notify("已请求中断当前回复")

    def _append_stream_delta(self, delta: str) -> None:
        self._streaming_text += delta
        self._refresh_log()

    def _refresh_after_session_change(self) -> None:
        self._streaming_text = ""
        self._refresh_log()

    def _set_todos_snapshot(self, todos: list[TodoItemState]) -> None:
        self._todos_snapshot = todos
        self._refresh_log()

    async def _ask_user_for_tool(self, question: UserQuestion) -> str:
        if self._pending_tool_future is not None and not self._pending_tool_future.done():
            raise RuntimeError("another tool question is already pending")
        future = get_running_loop().create_future()
        self._pending_tool_question = question
        self._pending_tool_future = future
        self._streaming_text = ""
        self._set_input_enabled(True)
        self._refresh_log()
        try:
            return await future
        finally:
            if not future.done():
                future.cancel()
            self._pending_tool_question = None
            self._pending_tool_future = None
            self._set_input_enabled(False)
            self._refresh_log()

    @work(exclusive=True, exit_on_error=False, group="assistant")
    async def _run_streaming(self) -> None:
        accumulated = ""
        self._streaming_error = None
        self._streaming_text = ""
        self._refresh_log()
        try:
            if resolved_llm_provider() == NOCODE_LLM_MOONSHOT:
                self.notify(
                    "当前仅 Anthropic / Kimi Anthropic 网关支持最小工具循环；已回退单轮聊天。",
                )
                async for delta in stream_assistant(
                    self._session.to_json_serializable(),
                    system=self._system_prompt,
                ):
                    accumulated += delta
                    self._streaming_text = accumulated
                    self._refresh_log()
            else:
                await run_tool_loop(
                    self._session,
                    system=self._system_prompt,
                    registry=self._tool_registry,
                    runtime=self._tool_runtime,
                    on_text_delta=self._append_stream_delta,
                    on_session_change=self._refresh_after_session_change,
                )
        except CancelledError:
            if self._pending_tool_future is not None and not self._pending_tool_future.done():
                self._pending_tool_future.cancel()
            partial = accumulated or self._streaming_text
            if partial:
                self._session.append_assistant_text(partial)
            self._streaming_text = ""
            self._streaming_error = "已中断当前回复。"
            self._refresh_log()
            raise
        except Exception as error:
            self._streaming_text = ""
            self._streaming_error = format_stream_error(error)
            self._refresh_log()
        else:
            if accumulated:
                self._session.append_assistant_text(accumulated)
            self._streaming_text = ""
            self._streaming_error = None
            self._refresh_log()
        finally:
            self._streaming_worker = None
            self._set_input_enabled(True)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """
        处理输入框回车：合并输入与待发图片，写入会话并启动流式助手回复。

        event: Textual 的 Input.Submitted, 含 value 与对应 Input 控件。
        """
        raw_input = _normalize_newlines(event.value)
        text = raw_input.strip()
        if self._pending_tool_future is not None and not self._pending_tool_future.done():
            if not text:
                return
            self._pending_tool_future.set_result(text)
            event.input.value = ""
            return
        if text.casefold() in ("/exit", "/quit"):
            self.exit()
            return
        if not text and not self._pending_images:
            return
        pending = list(self._pending_images)
        self._pending_images.clear()
        blocks = build_user_content_blocks(
            text=text if text else None, image_raw=pending
        )
        if not blocks:
            return
        self._session.append_user_content_blocks(blocks)
        event.input.value = ""
        self._streaming_error = None
        self._streaming_text = ""
        self._refresh_log()
        self._set_input_enabled(False)
        self._streaming_worker = self._run_streaming()


def run_tui() -> None:
    """启动全屏 TUI 应用（阻塞直到用户退出）"""
    NocodeApp().run()
