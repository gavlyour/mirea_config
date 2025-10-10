#!/usr/bin/env python3
"""
Эмулятор командной строки (REPL) с GUI на tkinter — с поддержкой VFS в памяти (Этап 3).

Поддерживаемые аргументы командной строки:
  --vfs PATH    путь к XML-файлу VFS (опционально)
  --script FILE путь к стартовому скрипту (опционально)

VFS (XML) формат (коротко):
<vfs>
  <dir name="/">
    <dir name="sub">
      <file name="text.txt" encoding="utf-8">Пример текста</file>
      <file name="bin.dat" encoding="base64">BASE64ДАННЫЕ</file>
    </dir>
    <file name="root.txt">Текст корня</file>
  </dir>
</vfs>

Правила:
 - Все данные читаются и хранятся в памяти. Никаких модификаций файлов VFS на диске не делаем.
 - Для бинарных данных используйте encoding="base64".
 - Для текстовых данных можно указать encoding="utf-8" или не указывать (будет взят текст напрямую).
"""
import argparse
import base64
import getpass
import os
import socket
import sys
import tkinter as tk
from tkinter import scrolledtext
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Union


# --- Простая внутренняя модель VFS: Directory и File ---
class VFSNode:
    """Базовый узел VFS."""
    def __init__(self, name: str):
        self.name = name


class VFSDirectory(VFSNode):
    """Каталог, содержащий дочерние узлы."""
    def __init__(self, name: str):
        super().__init__(name)
        # Словарь name -> VFSNode
        self.children: Dict[str, VFSNode] = {}

    def add_child(self, node: VFSNode):
        self.children[node.name] = node

    def get_child(self, name: str) -> Optional[VFSNode]:
        return self.children.get(name)


class VFSFile(VFSNode):
    """Файл — хранит байты (в памяти)."""
    def __init__(self, name: str, data: bytes):
        super().__init__(name)
        self.data = data  # содержимое как bytes


# --- Загрузка VFS из XML ---
def load_vfs_from_xml(path: str) -> VFSDirectory:
    """
    Загружает VFS из XML-файла и возвращает корневой каталог.
    Генерирует исключения при ошибках.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"VFS файл не найден: {path}")
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        raise ValueError(f"Ошибка разбора XML VFS: {e}")
    root = tree.getroot()
    if root.tag.lower() != 'vfs':
        raise ValueError("Неверный формат VFS: корневой элемент должен быть <vfs>")

    # Ищем корневой <dir name="/"> если есть — используем его, иначе создаём корень
    # Поддержим оба варианта: <vfs><dir name="/">...</dir></vfs> или <vfs>...</vfs>
    # Создадим виртуальный корень
    vfs_root = VFSDirectory('/')  # логический корень

    # Рекурсивный проход по XML
    def process_dir(xml_elem: ET.Element, dir_node: VFSDirectory):
        for child in xml_elem:
            tag = child.tag.lower()
            if tag == 'dir':
                name = child.get('name')
                if not name:
                    raise ValueError("В VFS: тег <dir> без атрибута name")
                new_dir = VFSDirectory(name)
                dir_node.add_child(new_dir)
                process_dir(child, new_dir)
            elif tag == 'file':
                name = child.get('name')
                if not name:
                    raise ValueError("В VFS: тег <file> без атрибута name")
                enc = child.get('encoding')  # может быть 'base64' или 'utf-8' и т.д.
                raw_text = child.text or ''
                if enc and enc.lower() == 'base64':
                    # decode base64 into bytes
                    try:
                        data = base64.b64decode(raw_text)
                    except Exception as e:
                        raise ValueError(f"Ошибка base64 в файле {name}: {e}")
                else:
                    # трактуем как текст: кодируем в utf-8 (без изменений на диске)
                    # если указана кодировка явно, используем её
                    if enc:
                        try:
                            data = raw_text.encode(enc)
                        except Exception as e:
                            raise ValueError(f"Неверная кодировка '{enc}' для файла {name}: {e}")
                    else:
                        data = raw_text.encode('utf-8')
                file_node = VFSFile(name, data)
                dir_node.add_child(file_node)
            else:
                # игнорируем неизвестные теги, но можно сигнализировать
                continue

    # Если внутри <vfs> есть <dir name="/"> - используем его содержимое как корневое содержимое
    # Иначе обрабатываем все дочерние узлы директно в корне
    top_dirs = [c for c in root if c.tag.lower() == 'dir' and c.get('name') == '/']
    if top_dirs:
        process_dir(top_dirs[0], vfs_root)
    else:
        process_dir(root, vfs_root)

    return vfs_root


# --- Вспомогательные функции для работы с путями VFS ---
def split_path(path: str) -> List[str]:
    """Разбивает путь Unix-стилем на компоненты (удаляет пустые части)."""
    parts = [p for p in path.split('/') if p not in ('', '.')]
    return parts


def resolve_path(start_dir: VFSDirectory, cwd: List[str], path: str) -> Union[VFSNode, VFSDirectory, VFSFile, None]:
    """
    Разрешает path относительно cwd (список компонент от корня, например ['home','user']).
    Возвращает VFSNode или None если не найден.
    path может быть абсолютным (начинается с '/') или относительным.
    """
    # начальная точка — логический root (start_dir). cwd — список компонентов от root.
    node: VFSNode = start_dir
    # build traversal list
    if path.startswith('/'):
        comps = split_path(path)
    else:
        comps = list(cwd) + split_path(path)
    for comp in comps:
        if comp == '..':
            # подняться вверх: если уже в корне — остаёмся в корне
            # но нам хранится только дерево от логического root, поэтому пропустим
            # реализация: пересоберём node по проходу от корня по сокращённому списку
            # проще: пересчитать от корня по оставшимся компонентам
            # Чтобы корректно обработать '..', мы пересчитываем текущую позицию:
            # строим новый список без учёта .. последовательностей
            new_stack: List[str] = []
            # recompute comps up to current index and include previous resolved?
            # Для упрощения: rebuild from scratch using stack approach
            stack: List[str] = []
            for c in comps:
                if c == '..':
                    if stack:
                        stack.pop()
                elif c == '.':
                    continue
                else:
                    stack.append(c)
            # теперь пройдём по stack от корня
            node = start_dir
            for c2 in stack:
                if not isinstance(node, VFSDirectory):
                    return None
                node = node.get_child(c2)
                if node is None:
                    return None
            return node
        else:
            if not isinstance(node, VFSDirectory):
                return None
            node = node.get_child(comp)
            if node is None:
                return None
    return node


# --- Основное приложение (GUI + REPL) ---
class ShellEmulator(tk.Tk):
    def __init__(self, vfs_path: Optional[str] = None, startup_script: Optional[str] = None):
        """
        Инициализация приложения.
        vfs_path: путь к XML VFS (если задан), startup_script: путь к стартовому скрипту.
        """
        super().__init__()

        # Конфигурация
        self.vfs_path = vfs_path
        self.startup_script = startup_script

        # Переменные окружения/заголовок
        self.username = getpass.getuser()
        self.hostname = socket.gethostname()
        self.title(f"Эмулятор - [{self.username}@{self.hostname}]")
        self.geometry("800x500")

        # UI: строка ввода (фрейм)
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

        # Карта команд
        self.commands = {
            'ls': self.cmd_ls,
            'cd': self.cmd_cd,
            'cat': self.cmd_cat,
            'vfsinfo': self.cmd_vfsinfo,
            'exit': self.cmd_exit,
        }

        # Состояние VFS
        self.vfs_root: Optional[VFSDirectory] = None
        self.cwd: List[str] = []  # текущая директория относительно корня как список компонентов

        # Пытаемся загрузить VFS, если путь указан
        if self.vfs_path:
            try:
                self.vfs_root = load_vfs_from_xml(self.vfs_path)
                self.write_output(f"VFS загружен из: {self.vfs_path}")
            except Exception as e:
                self.write_output(f"Ошибка загрузки VFS: {e}")
                # не выкидываем исключение, приложение продолжает работать без VFS
                self.vfs_root = None

        # Отладочный вывод параметров
        self.write_output("=== debug: параметры запуска ===")
        self.write_output(f"VFS путь: {self.vfs_path}")
        self.write_output(f"Стартовый скрипт: {self.startup_script}")
        self.write_output("================================")

        # Приветствие
        self.write_output("Это эмулятор командной строки с VFS. Напишите exit для выхода")

        # Запуск стартового скрипта, если указан (через self.after, чтобы UI отобразился)
        if self.startup_script:
            if os.path.isfile(self.startup_script):
                self.after(200, lambda: self.run_startup_script(self.startup_script))
            else:
                self.write_output(f"Ошибка: стартовый скрипт не найден: {self.startup_script}")

    # --- UI output helper ---
    def write_output(self, text: str):
        """Добавление текста в окно вывода (безопасно при state=DISABLED)."""
        self.output.configure(state=tk.NORMAL)
        self.output.insert(tk.END, text + '\n')
        self.output.see(tk.END)
        self.output.configure(state=tk.DISABLED)

    # --- Обработка ввода ---
    def on_enter(self, event=None):
        """Обработка ручного ввода: эхо, парсинг, вызов команды."""
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

    # --- Вспомогательные: доступ к VFS ---
    def vfs_resolve(self, path: str) -> Optional[VFSNode]:
        """Разрешает путь в VFS и возвращает узел или None."""
        if not self.vfs_root:
            self.write_output("VFS не загружен.")
            return None
        node = resolve_path(self.vfs_root, self.cwd, path)
        return node

    def vfs_change_dir(self, path: str) -> bool:
        """Меняет текущее рабочее каталожное состояние (cwd). Возвращает True при успехе."""
        if not self.vfs_root:
            self.write_output("VFS не загружен.")
            return False
        if path == '/':
            self.cwd = []
            return True
        node = self.vfs_resolve(path)
        if node is None:
            return False
        if not isinstance(node, VFSDirectory):
            return False
        # вычислим новый список компонентов от корня
        if path.startswith('/'):
            self.cwd = split_path(path)
        else:
            # относительный: объединяем и нормализуем .. и .
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

    # --- Команды VFS/REPL ---
    def cmd_ls(self, args: List[str]):
        """ls: показывает содержимое директории (или информации о файле)."""
        target = args[0] if args else '.'
        if target == '.':
            # list cwd
            if not self.vfs_root:
                self.write_output("VFS не загружен.")
                return
            node = resolve_path(self.vfs_root, self.cwd, '/'+'/'.join(self.cwd))  # current node
        else:
            node = self.vfs_resolve(target)
        if node is None:
            self.write_output(f"ls: путь не найден: {target}")
            return
        if isinstance(node, VFSDirectory):
            # перечислим имена: директории с '/', файлы без
            names = []
            for name, child in sorted(node.children.items()):
                if isinstance(child, VFSDirectory):
                    names.append(name + '/')
                else:
                    names.append(name)
            self.write_output('  '.join(names) if names else '(пустая директория)')
        else:
            # файл — просто вывести его имя
            self.write_output(node.name)

    def cmd_cd(self, args: List[str]):
        """cd: перейти в директорию внутри VFS."""
        if not args:
            # возвращаемся в корень
            success = self.vfs_change_dir('/')
            if success:
                self.write_output("Перешёл в /")
            else:
                self.write_output("cd: не удалось перейти в /")
            return
        path = args[0]
        ok = self.vfs_change_dir(path)
        if ok:
            # показываем текущую директорию
            cur = '/' + '/'.join(self.cwd) if self.cwd else '/'
            self.write_output(f"Тек. директория: {cur}")
        else:
            self.write_output(f"cd: путь не найден или не является директорией: {path}")

    def cmd_cat(self, args: List[str]):
        """cat: показать содержимое файла (если текст — печатаем; если бинарный — печатаем base64)."""
        if not args:
            self.write_output("cat: требуется путь к файлу")
            return
        path = args[0]
        node = self.vfs_resolve(path)
        if node is None:
            self.write_output(f"cat: файл не найден: {path}")
            return
        if isinstance(node, VFSDirectory):
            self.write_output(f"cat: {path}: это директория")
            return
        # node — VFSFile
        assert isinstance(node, VFSFile)
        data = node.data
        # Попробуем декодировать как utf-8 для показа; если не выйдет — покажем base64
        try:
            text = data.decode('utf-8')
            # печатаем текст (лимит по длине? пока нет)
            for line in text.splitlines():
                self.write_output(line)
            # если текст пустой — выведем пустую строку
            if text == '':
                self.write_output('')
        except Exception:
            # бинарные данные — показ в base64 (не записываем файл на диск)
            b64 = base64.b64encode(data).decode('ascii')
            self.write_output(f"(binary data, base64): {b64}")

    def cmd_vfsinfo(self, args: List[str]):
        """vfsinfo: показать статус загруженного VFS."""
        if not self.vfs_root:
            self.write_output("VFS не загружен.")
            return
        # посчитать файлы/директории и глубину
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

    def cmd_exit(self, args: List[str]):
        """exit: завершить приложение."""
        self.write_output("Выход...")
        self.destroy()

    # --- Стартовый скрипт исполнения ---
    def execute_line(self, line: str):
        """Выполнить одну строку из стартового скрипта (эмуляция ручного ввода)."""
        line = line.rstrip('\n')
        if not line:
            return
        # Отобразим как ввод
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
        """Читает и запускает стартовый скрипт построчно (пропуск комментариев)."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw_lines = f.readlines()
        except Exception as e:
            self.write_output(f"Не удалось открыть стартовый скрипт {path}: {e}")
            return

        # Фильтруем пустые строки и комментарии (строки, начинающиеся с '#')
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

        # Выполняем строки с небольшой задержкой, чтобы UI отобразил каждую строку по очереди
        delay_ms = 1000
        for i, ln in enumerate(lines):
            self.after(delay_ms * i, lambda l=ln: self.execute_line(l))


# --- Парсер аргументов ---
def parse_args():
    parser = argparse.ArgumentParser(description="Эмулятор командной строки (GUI) с VFS")
    parser.add_argument('--vfs', dest='vfs_path', help='Путь к XML VFS файлу', default=None)
    parser.add_argument('--script', dest='startup_script', help='Путь к стартовому скрипту', default=None)
    return parser.parse_args()


# --- Точка входа ---
if __name__ == '__main__':
    args = parse_args()
    app = ShellEmulator(vfs_path=args.vfs_path, startup_script=args.startup_script)
    app.mainloop()