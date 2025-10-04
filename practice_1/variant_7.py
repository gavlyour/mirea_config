#!/usr/bin/env python3
"""
Эмулятор командной строки (REPL) с GUI на tkinter — этап 2 (конфигурация).

Поддерживает параметры командной строки:
  --vfs PATH    Путь к физическому расположению VFS (не используется функционально, хранится как конфиг).
  --script FILE Путь к стартовому скрипту (файл с командами, выполняется при старте).

Стартовый скрипт:
  - каждая непустая незакомментированная строка файла воспринимается как команда;
  - строки выполняются последовательно;
  - при ошибках выполнение продолжается (строка пропускается с выводом ошибки);
  - при выполнении строка и её вывод отображаются в окне, имитируя ввод пользователя.

Запуск:
  python3 shell_emulator.py --vfs /path/to/vfs --script scripts/init1.txt
"""
import argparse
import getpass
import os
import socket
import tkinter as tk
from tkinter import scrolledtext


class ShellEmulator(tk.Tk):
    def __init__(self, vfs_path=None, startup_script=None):
        """
        Инициализация GUI и внутренних параметров.
        vfs_path и startup_script — значения, переданные через командную строку.
        """
        super().__init__()

        # Конфигурация: параметры, переданные извне (не обязательно использовать их функционально)
        self.vfs_path = vfs_path
        self.startup_script = startup_script

        # Получаем имя пользователя и хост для заголовка/прошений
        self.username = getpass.getuser()
        self.hostname = socket.gethostname()

        # Заголовок окна в формате: Эмулятор - [username@hostname]
        self.title(f"Эмулятор - [{self.username}@{self.hostname}]")
        self.geometry("700x400")

        # Frame для строки ввода (промпт + поле ввода)
        entry_frame = tk.Frame(self)
        entry_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        # Виджет-подсказка (постоянная метка)
        prompt = tk.Label(entry_frame, text=f"{self.username}@{self.hostname}:~$ ")
        prompt.pack(side=tk.LEFT)

        # Поле ввода и связанная строковая переменная
        self.input_var = tk.StringVar()
        self.entry = tk.Entry(entry_frame, textvariable=self.input_var)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind('<Return>', self.on_enter)
        self.entry.focus()

        # Область вывода (скроллируемая), по умолчанию заблокирована для редактирования пользователем
        self.output = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED)
        self.output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Карта команд: имя -> метод-обработчик
        self.commands = {
            'ls': self.cmd_ls,
            'cd': self.cmd_cd,
            'exit': self.cmd_exit,
        }

        # Отладочный вывод параметров конфигурации (выполняется в UI)
        self.write_output("=== debug: параметры запуска ===")
        self.write_output(f"VFS путь: {self.vfs_path}")
        self.write_output(f"Стартовый скрипт: {self.startup_script}")
        self.write_output("================================")

        # Приветствие
        self.write_output("Это эмулятор командной строки. Напишите exit для выхода")

        # Если указан стартовый скрипт, запланируем его выполнение после старта GUI
        # Используем self.after, чтобы UI мог отобразиться до начала последовательного выполнения
        if self.startup_script:
            # Проверяем существование файла; если отсутствует — выводим ошибку
            if os.path.isfile(self.startup_script):
                # малый отступ перед выполнением, чтобы приветствие и параметры уже были видимы
                self.after(200, lambda: self.run_startup_script(self.startup_script))
            else:
                self.write_output(f"Ошибка: стартовый скрипт не найден: {self.startup_script}")

    def write_output(self, text):
        """Добавление текста в окно вывода (безопасно при state=DISABLED)."""
        self.output.configure(state=tk.NORMAL)
        self.output.insert(tk.END, text + '\n')
        self.output.see(tk.END)
        self.output.configure(state=tk.DISABLED)

    def on_enter(self, event=None):
        """
        Обработка ввода пользователя (нажатие Enter).
        Парсим строку, выводим её в окно (эхо) и выполняем соответствующую команду.
        """
        line = self.input_var.get()
        self.input_var.set('')      # очищаем поле ввода
        line = line.strip()
        if not line:
            return

        # Эхо-команда с промптом (имитация терминала)
        self.write_output(f"{self.username}@{self.hostname}:~$ {line}")

        # Разделение на команду и аргументы (простой split по пробелам)
        parts = line.split()
        cmd = parts[0]
        args = parts[1:]

        # Диспетчеризация: если команда есть в словаре — вызываем обработчик, иначе сообщаем об ошибке
        handler = self.commands.get(cmd)
        if handler:
            try:
                handler(args)
            except Exception as e:
                self.write_output(f"Ошибка выполнения команды '{cmd}': {e}")
        else:
            self.write_output(f"Неизвестная команда: {cmd}. Доступные команды: {', '.join(self.commands.keys())}")

    def execute_line(self, line):
        """
        Выполнение команды — используется как единичный шаг при запуске стартового скрипта.
        Поведение такое же, как при ручном вводе:
         - печатаем эхо строки с промптом
         - парсим и выполняем команду
         - при ошибке выводим сообщение и продолжаем
        """
        line = line.strip()
        if not line:
            return
        # Принт эхо
        self.write_output(f"{self.username}@{self.hostname}:~$ {line}")

        parts = line.split()
        cmd = parts[0]
        args = parts[1:]

        handler = self.commands.get(cmd)
        if handler:
            try:
                handler(args)
            except Exception as e:
                # При ошибке продолжаем выполнение следующих команд
                self.write_output(f"Ошибка выполнения команды '{cmd}' в скрипте: {e}")
        else:
            # Если команда неизвестна — выводим и продолжаем
            self.write_output(f"Неизвестная команда в скрипте: {cmd}. Пропускаю строку.")

    def run_startup_script(self, path):
        """
        Читает файл path и последовательно выполняет строки.
        Комментарии (строки, начинающиеся с '#') и пустые строки пропускаются.
        Для удобства выполнения и видимости результатов используем self.after
        для последовательного (с небольшими задержками) выполнения строк.
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw_lines = f.readlines()
        except Exception as e:
            self.write_output(f"Не удалось открыть стартовый скрипт {path}: {e}")
            return

        # Фильтруем: убираем пустые строки и строки-комментарии
        lines = []
        for ln in raw_lines:
            s = ln.rstrip('\n')
            if not s:
                continue
            stripped = s.strip()
            if not stripped:
                continue
            if stripped.startswith('#'):
                continue
            lines.append(s)

        if not lines:
            self.write_output("Стартовый скрипт пуст или содержит только комментарии.")
            return

        # Выполняем строки последовательно с небольшой задержкой между ними,
        # чтобы пользователь видел пошаговый ввод и вывод.
        # Задержка выбирается небольшой (например, 300 мс) — можно увеличить при желании.
        delay_ms = 600
        for i, line in enumerate(lines):
            # лямбда с именованным аргументом, чтобы корректно захватить текущее значение line
            self.after(delay_ms * i, lambda l=line: self.execute_line(l))

    # Заглушки команд
    def cmd_ls(self, args):
        """Заглушка команды ls: просто выводит имя и аргументы."""
        self.write_output(f"ls вызвано с аргументами: {args}")

    def cmd_cd(self, args):
        """Заглушка команды cd: не меняет директорию, только выводит аргументы."""
        self.write_output(f"cd вызвано с аргументами: {args}")

    def cmd_exit(self, args):
        """Команда exit завершает приложение."""
        self.write_output("Выход...")
        self.destroy()


def parse_args():
    """Парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(description="Эмулятор командной строки (GUI) — параметры конфигурации")
    parser.add_argument('--vfs', dest='vfs_path', help='Путь к физическому расположению VFS', default=None)
    parser.add_argument('--script', dest='startup_script', help='Путь к стартовому скрипту', default=None)
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    # Создаём приложение, передавая параметры
    app = ShellEmulator(vfs_path=args.vfs_path, startup_script=args.startup_script)
    app.mainloop()
