# uconfig — перевод учебного конфига в JSON

CLI-инструмент на Python: читает конфигурацию из **stdin**, вычисляет константы `имя := значение` / `$[имя]`, пишет результат в **JSON-файл**. Ошибки лексики/синтаксиса/вычисления печатает в `stderr`.

## Требования
- Python 3.10+
- Для тестов: `pytest`

## Установка (рекомендуется)
Из корня проекта:
```bash
python -m pip install -e .
```

## Запуск (GIT Bash)
```bash
python -m uconfig -o out.json < examples/web_server.ucfg
```

## Запуск (Powershell)
```bash
gc -Raw .\examples\web_server.ucfg | python -m uconfig -o out.json
```

## Тесты
```bash
python -m pip install pytest
python -m pytest -q
```

## Примеры
Смотреть `examples/`:
- `web_server.ucfg`
- `ml_training.ucfg`
- `smart_home.ucfg`
