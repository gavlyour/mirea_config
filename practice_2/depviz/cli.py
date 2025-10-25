import argparse
import sys
from .config import Config
from .errors import ConfigError

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="depviz",
        description="Минимальный прототип: вывод настраиваемых параметров для визуализации графа зависимостей.",
    )
    p.add_argument("-p", "--package", required=True, help="Имя анализируемого пакета")
    p.add_argument("-r", "--repo", required=True, help="URL репозитория или путь к файлу/директории тестового репозитория")
    p.add_argument(
        "--repo-mode",
        choices=["url", "path"],
        required=True,
        help="Режим работы с тестовым репозиторием: 'url' или 'path'",
    )
    p.add_argument("-v", "--version", default=None, help="Версия пакета (PEP 440). Необязательно")
    p.add_argument(
        "-o", "--output",
        default="graph.png",
        help="Имя сгенерированного файла с изображением графа (расширение: png/jpg/jpeg/svg/pdf). По умолчанию graph.png",
    )
    p.add_argument(
        "-d", "--max-depth",
        default=3,
        type=int,
        help="Максимальная глубина анализа зависимостей (целое >= 0). По умолчанию 3",
    )
    p.add_argument(
        "-f", "--filter",
        default=None,
        help="Подстрока для фильтрации пакетов при построении графа (опционально)",
    )
    return p

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        cfg = Config.from_args(args)
    except ConfigError as e:
        sys.stderr.write(f"Configuration error [{e.field}]: {e.message}\n")
        return 2

    for line in cfg.to_kv_lines():
        print(line)
    return 0
