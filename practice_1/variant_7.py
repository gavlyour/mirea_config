"""
Точка входа: парсер аргументов и запуск GUI.
"""

import argparse
from shell_app import ShellEmulator


def parse_args():
    parser = argparse.ArgumentParser(description="Эмулятор командной строки (GUI) с VFS")
    parser.add_argument('--vfs', dest='vfs_path', help='Путь к XML VFS файлу', default=None)
    parser.add_argument('--script', dest='startup_script', help='Путь к стартовому скрипту', default=None)
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    app = ShellEmulator(vfs_path=args.vfs_path, startup_script=args.startup_script)
    app.mainloop()
