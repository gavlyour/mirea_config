# shell_app.py
"""
GUI-приложение: ShellEmulator — REPL с поддержкой VFS.
Импортирует функции/классы из vfs.py.
"""

import time
import getpass
import os
import socket
import base64
import tkinter as tk
from tkinter import scrolledtext
from typing import List, Optional

from vfs import VFSDirectory, VFSFile, VFSNode, load_vfs_from_xml, resolve_path, split_path


class ShellEmulator(tk.Tk):
    def __init__(self, vfs_path: Optional[str] = None, startup_script: Optional[str] = None):
        """
        Инициализация GUI и состояния.
        vfs_path: путь к XML VFS (опционально)
        startup_script: путь к стартовому скрипту (опционально)
        """
        super().__init__()

        self.vfs_path = vfs_path
        self.startup_script = startup_script

        # отметка времени запуска эмулятора — используется для uptime
        self.start_time = time.time()

        # Заголовок/пользователь/хост
        self.username = getpass.getuser()
        self.hostname = socket.gethostname()
        self.title(f"Эмулятор - [{self.username}@{self.hostname}]")
        self.geometry("800x500")

        # Строка ввода (фрейм)
        entry_frame = tk.Frame(self)
        entry_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        prompt = tk.Label(entry_frame, text=f"{self.username}@{self.hostname}:~$ ")
        prompt.pack(side=tk.LEFT)
        self.input_var = tk.StringVar()
        self.entry = tk.Entry(entry_frame, textvariable=self.input_var)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind('<Return>', self.on_enter)
        self.entry.focus()

        # Область вывода
        self.output = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED)
        self.output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Команды (добавлены uptime и whoami)
        self.commands = {
            'ls': self.cmd_ls,
            'cd': self.cmd_cd,
            'cat': self.cmd_cat,
            'vfsinfo': self.cmd_vfsinfo,
            'uptime': self.cmd_uptime,
            'whoami': self.cmd_whoami,
            'exit': self.cmd_exit,
        }

        # VFS state
        self.vfs_root: Optional[VFSDirectory] = None
        self.cwd: List[str] = []

        # Попытка загрузки VFS
        if self.vfs_path:
            try:
                self.vfs_root = load_vfs_from_xml(self.vfs_path)
                self.write_output(f"VFS загружен из: {self.vfs_path}")
            except Exception as e:
                self.write_output(f"Ошибка загрузки VFS: {e}")
                self.vfs_root = None

        # Отладочный вывод параметров
        self.write_output("=== debug: параметры запуска ===")
        self.write_output(f"VFS путь: {self.vfs_path}")
        self.write_output(f"Стартовый скрипт: {self.startup_script}")
        self.write_output("================================")

        self.write_output("Это эмулятор командной строки с VFS. Напишите exit для выхода")

        # Запустить стартовый скрипт при наличии
        if self.startup_script:
            if os.path.isfile(self.startup_script):
                self.after(200, lambda: self.run_startup_script(self.startup_script))
            else:
                self.write_output(f"Ошибка: стартовый скрипт не найден: {self.startup_script}")

    # --- UI helper ---
    def write_output(self, text: str):
        """Добавление текста в окно вывода."""
        self.output.configure(state=tk.NORMAL)
        self.output.insert(tk.END, text + '\n')
        self.output.see(tk.END)
        self.output.configure(state=tk.DISABLED)

    # --- обработка ввода ---
    def on_enter(self, event=None):
        """Обработка нажатия Enter: эхо, парсинг и выполнение команды."""
        line = self.input_var.get()
        self.input_var.set('')
        line = line.strip()
        if not line:
            return
        self.write_output(f"{self.username}@{self.hostname}:~$ {line}")
        parts = line.split()
        cmd = parts[0]
        args = parts[1:]
        handler = self.commands.get(cmd)
        if handler:
            try:
                handler(args)
            except Exception as e:
                self.write_output(f"Ошибка выполнения команды '{cmd}': {e}")
        else:
            self.write_output(f"Неизвестная команда: {cmd}. Доступные: {', '.join(self.commands.keys())}")

    # --- VFS helpers ---
    def vfs_resolve(self, path: str):
        """Разрешить путь в текущем VFS."""
        if not self.vfs_root:
            self.write_output("VFS не загружен.")
            return None
        return resolve_path(self.vfs_root, self.cwd, path)

    def vfs_change_dir(self, path: str) -> bool:
        """Поменять текущую директорию (cwd)."""
        if not self.vfs_root:
            self.write_output("VFS не загружен.")
            return False
        if path == '/':
            self.cwd = []
            return True
        node = self.vfs_resolve(path)
        if node is None or not isinstance(node, VFSDirectory):
            return False
        if path.startswith('/'):
            self.cwd = split_path(path)
        else:
            comps = list(self.cwd) + split_path(path)
            stack: List[str] = []
            for c in comps:
                if c == '..':
                    if stack:
                        stack.pop()
                elif c == '.':
                    continue
                else:
                    stack.append(c)
            self.cwd = stack
        return True

    # --- команды ---
    def cmd_ls(self, args: List[str]):
        """ls: перечислить содержимое директории или показать файл.
        Поддерживает относительные и абсолютные пути, '.' и '..'.
        """
        target = args[0] if args else '.'
        if target == '.':
            if not self.vfs_root:
                self.write_output("VFS не загружен.")
                return
            # текущая директория как путь
            cur_path = '/' + '/'.join(self.cwd) if self.cwd else '/'
            node = resolve_path(self.vfs_root, self.cwd, cur_path)
        else:
            node = self.vfs_resolve(target)
        if node is None:
            self.write_output(f"ls: путь не найден: {target}")
            return
        if isinstance(node, VFSDirectory):
            # перечислим имена в отсортированном порядке
            names = []
            for name, child in sorted(node.children.items()):
                names.append(name + ('/' if isinstance(child, VFSDirectory) else ''))
            self.write_output('  '.join(names) if names else '(пустая директория)')
        else:
            self.write_output(node.name)

    def cmd_cd(self, args: List[str]):
        """cd: смена директории внутри VFS."""
        if not args:
            ok = self.vfs_change_dir('/')
            if ok:
                self.write_output("Перешёл в /")
            else:
                self.write_output("cd: не удалось перейти в /")
            return
        path = args[0]
        ok = self.vfs_change_dir(path)
        if ok:
            cur = '/' + '/'.join(self.cwd) if self.cwd else '/'
            self.write_output(f"Тек. директория: {cur}")
        else:
            self.write_output(f"cd: путь не найден или не является директорией: {path}")

    def cmd_cat(self, args: List[str]):
        """cat: показать содержимое файла (попытка декодирования utf-8, иначе base64)."""
        if not args:
            self.write_output("cat: требуется путь к файлу")
            return
        node = self.vfs_resolve(args[0])
        if node is None:
            self.write_output(f"cat: файл не найден: {args[0]}")
            return
        if isinstance(node, VFSDirectory):
            self.write_output(f"cat: {args[0]}: это директория")
            return
        assert isinstance(node, VFSFile)
        data = node.data
        try:
            text = data.decode('utf-8')
            if text == '':
                self.write_output('')
            else:
                for line in text.splitlines():
                    self.write_output(line)
        except Exception:
            b64 = base64.b64encode(data).decode('ascii')
            self.write_output(f"(binary data, base64): {b64}")

    def cmd_vfsinfo(self, args: List[str]):
        """vfsinfo: показать краткую статистику загруженного VFS."""
        if not self.vfs_root:
            self.write_output("VFS не загружен.")
            return
        files = 0
        dirs = 0
        max_depth = 0

        def walk(node: VFSDirectory, depth: int):
            nonlocal files, dirs, max_depth
            dirs += 1
            if depth > max_depth:
                max_depth = depth
            for child in node.children.values():
                if isinstance(child, VFSDirectory):
                    walk(child, depth + 1)
                else:
                    files += 1

        walk(self.vfs_root, 0)
        self.write_output(f"VFS загружен: {self.vfs_path}")
        self.write_output(f"Директории: {dirs}, Файлы: {files}, Максимальная глубина: {max_depth}")

    def cmd_uptime(self, args: List[str]):
        """uptime: показать, как долго работает эмулятор (и, если доступно, системный uptime)."""
        now = time.time()
        secs = int(now - self.start_time)
        days, rem = divmod(secs, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        human = []
        if days:
            human.append(f"{days}d")
        human.append(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        self.write_output(f"Uptime (эмулятор): {' '.join(human)}")

        # Попытка также показать системный uptime на Unix-подобных системах
        try:
            if os.path.exists('/proc/uptime'):
                with open('/proc/uptime', 'r') as f:
                    content = f.read().strip().split()
                    sys_secs = int(float(content[0]))
                    d, r = divmod(sys_secs, 86400)
                    h, r = divmod(r, 3600)
                    m, s = divmod(r, 60)
                    sys_human = (f"{d}d " if d else "") + f"{h:02d}:{m:02d}:{s:02d}"
                    self.write_output(f"Uptime (система): {sys_human}")
        except Exception:
            # если не удалось — молча пропускаем (не критично)
            pass

    def cmd_whoami(self, args: List[str]):
        """whoami: напечатать имя текущего пользователя ОС."""
        self.write_output(self.username)

    def cmd_exit(self, args: List[str]):
        """exit: завершить приложение."""
        self.write_output("Выход...")
        self.destroy()

    # --- стартовый скрипт ---
    def execute_line(self, line: str):
        """Выполнить одну строку скрипта (эмуляция ручного ввода)."""
        line = line.rstrip('\n')
        if not line:
            return
        self.write_output(f"{self.username}@{self.hostname}:~$ {line}")
        parts = line.split()
        if not parts:
            return
        cmd = parts[0]
        args = parts[1:]
        handler = self.commands.get(cmd)
        if handler:
            try:
                handler(args)
            except Exception as e:
                self.write_output(f"Ошибка выполнения команды '{cmd}' в скрипте: {e}")
        else:
            self.write_output(f"Неизвестная команда в скрипте: {cmd}. Пропускаю строку.")

    def run_startup_script(self, path: str):
        """Читать и запускать стартовый скрипт построчно (пропуск комментариев)."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw_lines = f.readlines()
        except Exception as e:
            self.write_output(f"Не удалось открыть стартовый скрипт {path}: {e}")
            return

        lines = []
        for ln in raw_lines:
            if ln.strip() == '':
                continue
            if ln.strip().startswith('#'):
                continue
            lines.append(ln.rstrip('\n'))

        if not lines:
            self.write_output("Стартовый скрипт пуст или содержит только комментарии.")
            return

        delay_ms = 500
        for i, ln in enumerate(lines):
            self.after(delay_ms * i, lambda l=ln: self.execute_line(l))