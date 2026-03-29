# 如何编写nocode coding agent
我想实现一个类似claude code的在命令行运行的coding agent程序。我目前使用最熟练的语言是python，因此以python为构建程序的主要语言。在使用claude code时，安装好后，需要输入claude进入程序内部，这种交互形式叫做基于TUI的Agentic AI Interface。那么首先第一步，我需要实现的就是输入nocode,然后进入交互页面。先说明一下我的环境，我使用uv来管理依赖，python版本选择3.12。在pyproject.toml里声明依赖 textual>=8.2.1，为后面TUI做准备。再在pyject.toml里加入[build-system], 并设置[tool.uv] package = true, 让本地项目作为包安装并生成控制台脚本。在项目根目录下新建src/nocode文件夹，在该文件夹下新建__init__.py和cli.py。在cli.py里写入以下代码
```python
def main() -> None:
    print("ok")
```
至此，在命令行运行`uv sync`后，输入`nocode`，打印`ok`。