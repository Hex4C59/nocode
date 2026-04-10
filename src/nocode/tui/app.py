"""Textual application shell for the local `nocode` coding agent."""

from __future__ import annotations

from asyncio import CancelledError, Future, get_running_loop
from typing import ClassVar, override

from rich.markup import escape
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Input, RichLog, Rule
from textual.worker import Worker

from nocode.clipboard import get_clipboard_image
from nocode.config import Settings, project_root
from nocode.core import AgentLoop, build_system_prompt
from nocode.messages import ChatSession, ContentBlock, build_user_content_blocks, format_api_message_markup
from nocode.providers import get_provider
from nocode.tools import TodoItemState, ToolRuntime, UserQuestion, build_default_registry
from nocode.tui.welcome import WelcomePanel


def _normalize_newlines(text: str) -> str:
    """Normalize pasted newlines so all platforms behave the same."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


class NocodeApp(App[None]):
    """Minimal chat shell that projects session state into a Textual RichLog."""

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
        self._pending_images: list[tuple[bytes, str | None]] = []
        self._pending_submission: list[ContentBlock] | None = None
        self._streaming_worker: Worker[None] | None = None
        self._streaming_text = ""
        self._streaming_error: str | None = None
        self._todos_snapshot: list[TodoItemState] = []
        self._pending_tool_question: UserQuestion | None = None
        self._pending_tool_future: Future[str] | None = None
        settings = Settings.from_env()
        tool_registry = build_default_registry()
        tool_runtime = ToolRuntime(
            workspace_root=project_root(),
            ask_user=self._ask_user_for_tool,
            on_todos_changed=self._set_todos_snapshot,
        )
        self._agent = AgentLoop(
            session=ChatSession(),
            provider=get_provider(settings),
            tool_registry=tool_registry,
            tool_runtime=tool_runtime,
            system_prompt=build_system_prompt(tool_registry.keys()),
        )
        self._session = self._agent.session

    @override
    def compose(self) -> ComposeResult:
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
        log_widget = self.query_one("#log", RichLog)
        log_widget.can_focus = False
        _ = self.call_after_refresh(self._focus_input_after_layout)

    def _focus_input_after_layout(self) -> None:
        log_widget = self.query_one("#log", RichLog)
        log_widget.can_focus = False
        if log_widget.has_focus:
            log_widget.blur()
        message_input = self.query_one("#msg", Input)
        _ = message_input.focus()

    def action_paste_clipboard_image(self) -> None:
        if self._has_active_stream():
            self.notify("正在生成回复，暂时不能继续贴图", severity="warning")
            return
        result = get_clipboard_image()
        if result is None:
            self.notify("剪贴板里没有可用的图片", severity="warning")
            return
        raw, media_type = result
        self._pending_images.append((raw, media_type))
        self.notify(f"已添加剪贴板图片（共 {len(self._pending_images)} 张），回车发送")

    def _refresh_log(self) -> None:
        log_widget = self.query_one("#log", RichLog)
        log_widget.clear()
        for message in self._session.messages:
            _ = log_widget.write(format_api_message_markup(message))
        if self._todos_snapshot:
            todo_body = " | ".join(
                f"{item.status}: {item.content}" for item in self._todos_snapshot
            )
            _ = log_widget.write(f"[bold yellow]待办[/]: {escape(todo_body)}")
        if self._pending_tool_question is not None:
            line = f"[bold magenta]工具提问[/]: {escape(self._pending_tool_question.question)}"
            if self._pending_tool_question.options:
                options = " / ".join(self._pending_tool_question.options)
                line += f" [dim]选项: {escape(options)}[/dim]"
            _ = log_widget.write(line)
        if self._has_active_stream() and not self._streaming_error:
            if self._streaming_text:
                _ = log_widget.write(
                    format_api_message_markup(
                        {"role": "assistant", "content": self._streaming_text}
                    )
                )
            else:
                _ = log_widget.write("[bold blue]助手[/]: [dim]正在生成...[/dim]")
        if self._streaming_error:
            _ = log_widget.write(f"[bold red]错误[/]: {escape(self._streaming_error)}")

    def _has_active_stream(self) -> bool:
        return self._streaming_worker is not None and not self._streaming_worker.is_finished

    def _set_input_enabled(self, enabled: bool) -> None:
        message_input = self.query_one("#msg", Input)
        message_input.disabled = not enabled
        if enabled:
            _ = message_input.focus()

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

    def _notify_tool_fallback(self) -> None:
        self.notify("当前 provider 不支持最小工具循环；已回退单轮聊天。")

    @work(exclusive=True, exit_on_error=False, group="assistant")
    async def _run_streaming(self) -> None:
        self._streaming_error = None
        self._streaming_text = ""
        self._refresh_log()
        try:
            assert self._pending_submission is not None
            blocks = self._pending_submission
            self._pending_submission = None
            await self._agent.submit(
                blocks,
                on_text_delta=self._append_stream_delta,
                on_session_change=self._refresh_after_session_change,
                on_tool_fallback=self._notify_tool_fallback,
            )
        except CancelledError:
            if self._pending_tool_future is not None and not self._pending_tool_future.done():
                self._pending_tool_future.cancel()
            if self._streaming_text:
                self._session.append_assistant_text(self._streaming_text)
            self._streaming_text = ""
            self._streaming_error = "已中断当前回复。"
            self._refresh_log()
            raise
        except Exception as error:
            self._streaming_text = ""
            self._streaming_error = self._agent.format_error(error)
            self._refresh_log()
        else:
            self._streaming_text = ""
            self._streaming_error = None
            self._refresh_log()
        finally:
            self._streaming_worker = None
            self._set_input_enabled(True)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw_input = _normalize_newlines(event.value)
        text = raw_input.strip()
        if self._pending_tool_future is not None and not self._pending_tool_future.done():
            if not text:
                return
            self._pending_tool_future.set_result(text)
            event.input.value = ""
            return
        if text.casefold() in {"/exit", "/quit"}:
            self.exit()
            return
        if not text and not self._pending_images:
            return
        pending_images = list(self._pending_images)
        self._pending_images.clear()
        blocks = build_user_content_blocks(
            text=text if text else None,
            image_raw=pending_images,
        )
        if not blocks:
            return
        event.input.value = ""
        self._streaming_error = None
        self._streaming_text = ""
        self._pending_submission = blocks
        self._refresh_log()
        self._set_input_enabled(False)
        self._streaming_worker = self._run_streaming()


def run_tui() -> None:
    """Run the full-screen Textual application."""
    NocodeApp().run()
