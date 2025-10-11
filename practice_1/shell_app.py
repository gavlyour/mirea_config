# shell_app.py
"""
GUI-приложение: ShellEmulator — REPL с поддержкой VFS.
Добавлены команды rmdir и cp (все модификации VFS только в памяти).
"""

import time
import getpass
import os
import socket
import base64
import tkinter as tk
from tkinter import scrolledtext
from typing import List, Optional

from vfs import VFSDirectory, VFSFile, VFSNode, load_vfs_from_xml, resolve_path, split_path, resolve_parent


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
        self.geometry("820x520")

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

        # Команды (добавлены rmdir и cp)
        self.commands = {
            'ls': self.cmd_ls,
            'cd': self.cmd_cd,
            'cat': self.cmd_cat,
            'vfsinfo': self.cmd_vfsinfo,
            'uptime': self.cmd_uptime,
            'whoami': self.cmd_whoami,
            'rmdir': self.cmd_rmdir,
            'cp': self.cmd_cp,
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

    # --- команды базовые (ls, cd, cat, vfsinfo, uptime, whoami) ---
    def cmd_ls(self, args: List[str]):
        """ls: перечислить содержимое директории или показать файл."""
        target = args[0] if args else '.'
        if target == '.':
            if not self.vfs_root:
                self.write_output("VFS не загружен.")
                return
            cur_path = '/' + '/'.join(self.cwd) if self.cwd else '/'
            node = resolve_path(self.vfs_root, self.cwd, cur_path)
        else:
            node = self.vfs_resolve(target)
        if node is None:
            self.write_output(f"ls: путь не найден: {target}")
            return
        if isinstance(node, VFSDirectory):
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
        """cat: показать содержимое файла.
        Попытка: декодировать в utf-8 и показать если это читаемый текст.
        В противном случае показать base64-представление бинарных данных.
        """
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
        # node — VFSFile
        assert isinstance(node, VFSFile)
        data = node.data

        # пустой файл — явно показываем
        if not data:
            self.write_output("(empty file)")
            return

        # попробуем декодировать в utf-8
        try:
            text = data.decode('utf-8')
        except Exception:
            # не текст — покажем base64
            b64 = base64.b64encode(data).decode('ascii')
            self.write_output(f"(binary data, base64): {b64}")
            return

        # Если декодирование прошло — проверим, является ли текст отображаемым
        # считаем его текстом, если хотя бы 60% символов печатаемы (порог можно настроить)
        if text.strip() == '':
            # строка состоит только из пробелов/управляющих символов — считать нечитабельным
            b64 = base64.b64encode(data).decode('ascii')
            self.write_output(f"(binary data, base64): {b64}")
            return

        printable_count = sum(1 for ch in text if ch.isprintable() or ch in '\n\r\t')
        ratio = printable_count / max(1, len(text))
        if ratio >= 0.6:
            # считаем это текстом — выводим построчно
            for line in text.splitlines():
                self.write_output(line)
        else:
            # большинство — непечатаемые символы, показываем base64
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
            pass

    def cmd_whoami(self, args: List[str]):
        """whoami: напечатать имя текущего пользователя ОС."""
        self.write_output(self.username)

    # --- НОВЫЕ команды: rmdir и cp ---
    def cmd_rmdir(self, args: List[str]):
        """rmdir: удалить пустую директорию в VFS (только в памяти)."""
        if not args:
            self.write_output("rmdir: требуется путь к директории")
            return
        path = args[0]
        if not self.vfs_root:
            self.write_output("VFS не загружен.")
            return
        # Найти сам узел
        node = self.vfs_resolve(path)
        if node is None:
            self.write_output(f"rmdir: путь не найден: {path}")
            return
        if not isinstance(node, VFSDirectory):
            self.write_output(f"rmdir: {path}: не является директорией")
            return
        # Проверить пустоту
        if node.children:
            self.write_output(f"rmdir: {path}: директория не пуста")
            return
        # Найти родителя и удалить у него этот узел
        parent_info = resolve_parent(self.vfs_root, self.cwd, path)
        if parent_info is None:
            self.write_output(f"rmdir: не удалось найти родителя для {path}")
            return
        parent_dir, name = parent_info
        if not parent_dir.remove_child(name):
            self.write_output(f"rmdir: не удалось удалить {path}")
            return
        self.write_output(f"rmdir: удалено {path}")

    def cmd_cp(self, args: List[str]):
        """cp: копировать файл внутри VFS (в памяти).
        usage: cp <src> <dst>
        """
        if len(args) < 2:
            self.write_output("cp: требуется источник и назначение")
            return
        src, dst = args[0], args[1]
        if not self.vfs_root:
            self.write_output("VFS не загружен.")
            return
        src_node = self.vfs_resolve(src)
        if src_node is None:
            self.write_output(f"cp: источник не найден: {src}")
            return
        if isinstance(src_node, VFSDirectory):
            self.write_output(f"cp: копирование директорий не поддерживается: {src}")
            return
        # src_node — VFSFile
        assert isinstance(src_node, VFSFile)
        # Если dst существует и это директория — копируем внутрь с тем же именем
        dst_node = self.vfs_resolve(dst)
        if dst_node is not None and isinstance(dst_node, VFSDirectory):
            dest_parent = dst_node
            dest_name = src_node.name
        elif dst_node is not None and isinstance(dst_node, VFSFile):
            # dst указывает на файл — перезаписать его
            parent_info = resolve_parent(self.vfs_root, self.cwd, dst)
            if parent_info is None:
                self.write_output(f"cp: не удалось найти родителя для {dst}")
                return
            dest_parent, dest_name = parent_info
        else:
            # dst не существует: найти родитель, куда создавать файл
            parent_info = resolve_parent(self.vfs_root, self.cwd, dst)
            if parent_info is None:
                self.write_output(f"cp: родительская директория для {dst} не найдена")
                return
            dest_parent, dest_name = parent_info
        # Проверка dest_parent
        if not isinstance(dest_parent, VFSDirectory):
            self.write_output(f"cp: целевая директория недоступна: {dst}")
            return
        # Создаём новый файл-узел с копией байтов
        new_data = bytes(src_node.data)  # копия байтов
        new_file = VFSFile(dest_name, new_data)
        # Если там уже есть узел с таким именем — если это директория — ошибка, иначе перезапишем
        existing = dest_parent.get_child(dest_name)
        if existing and isinstance(existing, VFSDirectory):
            self.write_output(f"cp: не могу перезаписать директорию: {dst}")
            return
        dest_parent.add_child(new_file)
        # Вывод успеха
        # отобразим путь в формате, удобном для пользователя
        self.write_output(f"cp: скопировано {src} -> {dst}")

    def cmd_exit(self, args: List[str]):
        """exit: завершить приложение."""
        self.write_output("Выход...")
        self.destroy()

    # --- стартовый скрипт (повторно) ---
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

        delay_ms = 300
        for i, ln in enumerate(lines):
            self.after(delay_ms * i, lambda l=ln: self.execute_line(l))
