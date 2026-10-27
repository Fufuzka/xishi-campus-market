"""Create an administrator in this running Linux site's data directory.

This wrapper selects a unique backend process configuration, then invokes the
existing interactive creation command. It never resets or promotes an account.
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


def running_sites(root, proc=Path('/proc')):
    root = root.resolve()
    choices = {}
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cwd = Path(os.readlink(entry / 'cwd')).resolve()
            args = [x.decode() for x in (entry / 'cmdline').read_bytes().split(b'\0') if x]
            if cwd != root or 'backend.main:app' not in args:
                continue
            env = dict(x.decode().split('=', 1) for x in (entry / 'environ').read_bytes().split(b'\0') if b'=' in x)
            data = Path(env.get('MARKET_DATA_DIR') or root / 'data')
            data = (cwd / data).resolve() if not data.is_absolute() else data.resolve()
            virtual = Path(env['VIRTUAL_ENV']) / 'bin/python' if env.get('VIRTUAL_ENV') else None
            launch = Path(shutil.which(args[0], path=env.get('PATH', '')) or args[0])
            interpreter = virtual if virtual and virtual.is_file() else None
            if interpreter is None and 'python' in launch.name.lower() and launch.is_file():
                interpreter = launch
            if interpreter is None and launch.is_file():
                with launch.open('rb') as stream:
                    first = stream.readline(1024).decode(errors='replace').strip()
                if first.startswith('#!'):
                    command = shlex.split(first[2:])
                    if command and Path(command[0]).name == 'env' and len(command) == 2:
                        command = [shutil.which(command[1], path=env.get('PATH', '')) or '']
                    if len(command) == 1 and 'python' in Path(command[0]).name.lower() and Path(command[0]).is_file():
                        interpreter = Path(command[0])
            if interpreter is None:
                continue
            # Do not resolve interpreter symlinks: that would lose venv identity.
            interpreter = interpreter.absolute()
            choices[(str(data), str(interpreter))] = (data, interpreter)
        except (OSError, ValueError, UnicodeError):
            continue
    return list(choices.values())


def main():
    if len(sys.argv) != 2:
        raise SystemExit('用法：python3 scripts/create-running-admin.py 管理员用户名')
    root = Path(__file__).resolve().parents[1]
    if not Path('/proc').is_dir():
        raise SystemExit('此命令适用于 Linux 面板服务器；其他环境请使用 backend.create_admin。')
    choices = running_sites(root)
    if len(choices) != 1:
        raise SystemExit('无法唯一确定本项目的运行环境。请保持宝塔中的夕拾项目运行，并使用有权限读取进程的终端；若运行了多个不同数据目录，请先核对项目配置。未创建账号。')
    data, interpreter = choices[0]
    if not (data / 'market.db').is_file():
        raise SystemExit('运行进程的数据文件不存在，已停止；不会新建另一份账号数据库。')
    print('运行项目：', root)
    print('账号写入：', data / 'market.db')
    print('项目 Python：', interpreter)
    print('请在下方密码提示中输入准备好的管理员密码；输入时不会显示。', flush=True)
    env = dict(os.environ)
    env['MARKET_DATA_DIR'] = str(data)
    env.pop('MARKET_ADMIN_PASSWORD', None)
    result = subprocess.run([str(interpreter), '-m', 'backend.create_admin', sys.argv[1]], cwd=root, env=env)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
