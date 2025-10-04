#!/usr/bin/env python3
import getpass
import socket
import tkinter as tk
from tkinter import scrolledtext


class ShellEmulator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.username = getpass.getuser()
        self.hostname = socket.gethostname()
        self.title(f"Эмулятор - [{self.username}@{self.hostname}]")
        self.geometry("700x400")

        # UI: область вывода и поле ввода
        entry_frame = tk.Frame(self)
        entry_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        prompt = tk.Label(entry_frame, text=f"{self.username}@{self.hostname}:~$ ")
        prompt.pack(side=tk.LEFT)

        self.input_var = tk.StringVar()
        self.entry = tk.Entry(entry_frame, textvariable=self.input_var)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind('<Return>', self.on_enter)
        self.entry.focus()

        self.output = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED)
        self.output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Simple command map
        self.commands = {
            'ls': self.cmd_ls,
            'cd': self.cmd_cd,
            'exit': self.cmd_exit,
        }

        # Welcome
        self.write_output(f"Это эмулятор командой строки. Напишите exit для выхода")

    def write_output(self, text):
        """Append text to the output area (safe for disabling)."""
        self.output.configure(state=tk.NORMAL)
        self.output.insert(tk.END, text + '\n')
        self.output.see(tk.END)
        self.output.configure(state=tk.DISABLED)

    def on_enter(self, event=None):
        line = self.input_var.get()
        self.input_var.set('')
        line = line.strip()
        if not line:
            return
        # Echo command with a prompt-like prefix
        self.write_output(f"{self.username}@{self.hostname}:~$ {line}")
        # Parse: simple split on whitespace
        parts = line.split()
        cmd = parts[0]
        args = parts[1:]
        # Dispatch
        handler = self.commands.get(cmd, self.cmd_unknown)
        try:
            handler(args)
        except Exception as e:
            self.write_output(f"Error executing command '{cmd}': {e}")

    # Command implementations (stubs)
    def cmd_ls(self, args):
        # Stub: just print command name and args
        self.write_output(f"ls called with arguments: {args}")

    def cmd_cd(self, args):
        # Stub: just print command name and args
        self.write_output(f"cd called with arguments: {args}")

    def cmd_exit(self, args):
        self.write_output("Exiting emulator...")
        self.destroy()

    def cmd_unknown(self, args):
        # args[0] is not available here; the caller echos the command already
        self.write_output(f"Unknown command. Available stubs: {', '.join(self.commands.keys())}")


if __name__ == '__main__':
    app = ShellEmulator()
    app.mainloop()
