# vfs.py
"""
Модуль VFS: модель виртуальной файловой системы в памяти и загрузчик из XML.
Добавлены вспомогательные методы для работы с деревом (удаление узла, получение родителя).
Вся работа с VFS — только в памяти.
"""

import os
import base64
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Union


class VFSNode:
    """Базовый узел VFS."""
    def __init__(self, name: str):
        self.name = name


class VFSDirectory(VFSNode):
    """Каталог VFS — содержит дочерние узлы в словаре name -> node."""
    def __init__(self, name: str):
        super().__init__(name)
        self.children: Dict[str, VFSNode] = {}

    def add_child(self, node: VFSNode):
        self.children[node.name] = node

    def get_child(self, name: str) -> Optional[VFSNode]:
        return self.children.get(name)

    def remove_child(self, name: str) -> bool:
        """Удалить дочерний узел по имени. Возвращает True если удалено, False если нет."""
        if name in self.children:
            del self.children[name]
            return True
        return False


class VFSFile(VFSNode):
    """Файл VFS — хранит содержимое как bytes."""
    def __init__(self, name: str, data: bytes):
        super().__init__(name)
        self.data = data


def load_vfs_from_xml(path: str) -> VFSDirectory:
    """
    Загружает VFS из XML-файла и возвращает корневой каталог (VFSDirectory).
    Бросает исключения при ошибках (FileNotFoundError, ValueError при некорректном XML).
    Ожидаемый формат описан ранее.
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

    vfs_root = VFSDirectory('/')

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
                enc = child.get('encoding')  # 'base64' или 'utf-8' и т.п.
                raw_text = child.text or ''
                if enc and enc.lower() == 'base64':
                    try:
                        data = base64.b64decode(raw_text)
                    except Exception as e:
                        raise ValueError(f"Ошибка base64 в файле {name}: {e}")
                else:
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
                # неизвестные теги игнорируем
                continue

    # Если внутри <vfs> есть <dir name="/"> — используем его содержимое как корень
    top_dirs = [c for c in root if c.tag.lower() == 'dir' and c.get('name') == '/']
    if top_dirs:
        process_dir(top_dirs[0], vfs_root)
    else:
        process_dir(root, vfs_root)

    return vfs_root


# ---------- функции работы с путями ----------
def split_path(path: str) -> List[str]:
    """Разбивает Unix-стиль путь на компоненты, убирая пустые и точечные элементы."""
    return [p for p in path.split('/') if p not in ('', '.')]


def resolve_path(root: VFSDirectory, cwd: List[str], path: str) -> Optional[Union[VFSDirectory, VFSFile]]:
    """
    Разрешает путь относительно текущей директории cwd (список компонентов от корня).
    Возвращает VFSNode или None, если путь не найден.
    Поддерживает абсолютные и относительные пути, '.' и '..'.
    """
    if path.startswith('/'):
        comps = split_path(path)
    else:
        comps = list(cwd) + split_path(path)

    # Нормализация с обработкой '..'
    stack: List[str] = []
    for c in comps:
        if c == '..':
            if stack:
                stack.pop()
        elif c == '.':
            continue
        else:
            stack.append(c)

    node: VFSNode = root
    for comp in stack:
        if not isinstance(node, VFSDirectory):
            return None
        node = node.get_child(comp)
        if node is None:
            return None
    return node


def resolve_parent(root: VFSDirectory, cwd: List[str], path: str) -> Optional[tuple]:
    """
    Разрешает путь и возвращает (parent_dir, name) для указанного path.
    parent_dir — VFSDirectory (куда должен находиться элемент),
    name — имя последнего компонента пути.
    Возвращает None, если родитель не найден или не является директорией.
    Примеры:
      path = '/a/b/c.txt' => вернёт (dir('/a/b'), 'c.txt') если такой родитель существует.
      path = 'd/e' относительно cwd => аналогично.
    """
    if path == '/':
        return None
    # Разделим путь на компоненты
    if path.startswith('/'):
        comps = split_path(path)
    else:
        comps = list(cwd) + split_path(path)
    if not comps:
        return (root, '')  # special case корень (не используется)
    parent_comps = comps[:-1]
    name = comps[-1]
    # Нормализация parent_comps (обработка .. и .)
    stack: List[str] = []
    for c in parent_comps:
        if c == '..':
            if stack:
                stack.pop()
        elif c == '.':
            continue
        else:
            stack.append(c)
    # Пройдём от корня по stack
    node: VFSNode = root
    for comp in stack:
        if not isinstance(node, VFSDirectory):
            return None
        node = node.get_child(comp)
        if node is None:
            return None
    if not isinstance(node, VFSDirectory):
        return None
    return (node, name)