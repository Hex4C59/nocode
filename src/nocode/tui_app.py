from typing import ClassVar, override

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.widgets import Input, RichLog


class NocodeApp(App[None]):
    """最小聊天shell: 上方RichLog, 下方Input; 提交后写占位回复"""

    CSS: ClassVar[str] = """
    Vertical { height: 100%; }
    #log { height: 1fr; border: solid $primary; min-height: 5;}
    #msg { height: 1;}
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+c", "quit", "退出", show=True)
    ]
    
    @override
    def compose(self) -> ComposeResult:
        """构建界面: 日志区 + 输入框"""
        with Vertical():
            yield RichLog(id="log", highlight=True, markup=True)
            yield Input(placeholder="输入后回车...", id="msg")

    def on_mount(self) -> None:
        """界面挂载后把焦点放到输入框"""
        _ = self.query_one("#msg", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """
        处理输入框回车: 写入用户与占位助手回复，并清空输入。

        event: Textual 的 Input.Submitted, 含 value 与对应 Input 控件。
        """
        if event.input.id != "msg":
            return
        text = event.value.strip()
        if not text:
            return
        log_w = self.query_one("#log", RichLog)
        _ = log_w.write(f"[bold green]你[/]: {text}")
        _ = log_w.write(f"[bold blue]助手[/]: 收到: {text}")
        event.input.value = ""
        _ = event.input.focus()


def run_tui() -> None:
    """启动全屏 TUI 应用（阻塞直到用户退出）"""
    NocodeApp().run()
