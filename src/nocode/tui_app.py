# Textual 聊天壳：消息区 + 单行输入；ChatSession 为真源，RichLog 为投影；不接模型。
from typing import ClassVar, override

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Input, RichLog, Rule

from nocode.clipboard_image import get_clipboard_image
from nocode.messages import (
    ChatSession,
    ContentBlock,
    build_user_content_blocks,
    format_api_message_markup,
)
from nocode.welcome import WelcomePanel


def _normalize_newlines(text: str) -> str:
    """
    将文本中的换行符规范为 Unix 风格的 \\n，便于在 macOS/Linux/Windows 粘贴内容时表现一致。

    text: 原始字符串，可能含 \\r\\n（Windows）或单独 \\r。
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _placeholder_assistant_reply(
    user_text: str | None, blocks: list[ContentBlock]
) -> str:
    ntxt = user_text.strip() if user_text else ""
    nimg = sum(1 for b in blocks if b["type"] == "image")
    if ntxt and nimg:
        return f"收到: {ntxt}（{nimg} 张图）"
    if ntxt:
        return f"收到: {ntxt}"
    return f"收到: {nimg} 张图片"


class NocodeApp(App[None]):
    """最小聊天shell: ChatSession 为真源；Alt+V 贴剪贴板图片，回车与输入合并提交。"""

    CSS: ClassVar[str] = """
    #log { height: 1fr; background: $background; scrollbar-size: 0 0; }
    .input-rule { height: 1; margin: 0; color: $primary; }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+c", "quit", "退出", show=True),
        Binding("alt+v", "paste_clipboard_image", "贴图", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._session = ChatSession()
        self._pending_images: list[tuple[bytes, str | None]] = []

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

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """
        处理输入框回车: 合并输入与待发图片，写入会话与占位助手回复，并清空输入。

        event: Textual 的 Input.Submitted, 含 value 与对应 Input 控件。
        """
        raw_input = _normalize_newlines(event.value)
        text = raw_input.strip()
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
        self._session.append_assistant_text(
            _placeholder_assistant_reply(text if text else None, blocks)
        )
        self._refresh_log()
        event.input.value = ""
        _ = event.input.focus()


def run_tui() -> None:
    """启动全屏 TUI 应用（阻塞直到用户退出）"""
    NocodeApp().run()
