# Проверки ExecRepoBench

Дата: 2026-11-03. Все перечисленные запуски выполнялись локально,
не через SSH и не на mounted server. Никакие файлы под `X:` не изменены.

- Закреплённый JSONL: SHA256, схема всех 1164 задач, шесть категорий,
  50 репозиториев; historical ответы/метрики очищаются whitelist-загрузчиком.
  Все 9592 записи ZIP прошли проверку безопасных путей.
- 23 stdlib unit/launcher-теста прошли: данные, ID/хеши, traversal/links,
  повреждения/дубликаты JSONL, resume, exact whitespace, FIM/budget/close,
  отсутствие model imports при оценке, ES и знаменатели, полный gold gate,
  namespace/scripts, одинаковые параметры launcher, пробелы и exit codes.
- Windows PowerShell и Bash в WSL Ubuntu реально запускались. Оба `--help`
  совпадают; capture interpreter с пробелами получает точные аргументы и
  возвращает 37; отсутствующий `--python` возвращает 2.
  Отдельно проверен настоящий Windows native shim со stderr и exit=37.
- Синтетический Docker-check подтвердил чтение изменённого файла из `/repo`,
  независимость двух параллельных задач, pass/test_fail/timeout/oom/infra,
  nonroot, отсутствие socket и удаление контейнеров. Timeout включал потомка.
- Рабочим Dockerfile собраны три пилотных образа. Gold через Windows launcher:
  12/12, 100%; empty через WSL Linux launcher: 3/12, 25%; infrastructure=0.
  Это только пилот и характеристика его тестов, не полный результат модели.
- Настоящий AutoTokenizer (Transformers 5.19.0, tokenizers 0.23.2), revision
  `b2cff646eb4bb1d68355c01b18ae02e7cf42d120`: проверены все 1164 prompts,
  1175–7168 input tokens, окно 8192 и резерв 1024 соблюдены. Native stop IDs
  совпадают с официальным примером. Независимый tokenizer.json/Jinja-check
  также прошёл все 1164. Весов, Torch, CUDA и vLLM в CPU-проверке не было.

Все 50 образов собраны с успешным финальным pip check и проверкой импортов.
Для двух native Windows build-клиентов наблюдалось зависание после сообщения
export DONE; повторный вызов того же Python-контроллера в локальной WSL завершил
сборку успешно. Docker Desktop image store общий для Windows и WSL. Это
наблюдаемое ограничение native build CLI в текущем окружении; stdin отключён
у всех неинтерактивных Docker-команд. Подготовка данных через standalone CLI
также реально проверена: source-dir, jsonl-only, 1164 чистых экспортированных задач.

Полный oracle/empty аудит всех 1164 задач на окончательных 50 образах выполняется;
его итог и build-проблемы будут сохранены в `control_report/`. До полного
gold 1164/1164 модельный полный score запрещён контроллером.

Общее локальное окружение по разрешению пользователя приведено к рабочей паре
Transformers 4.45.2 / huggingface-hub 0.36.2 / tokenizers 0.20.1; импорт
AutoTokenizer проверен. Для точной 5.19.0 использовано отдельное
`.venv-tokenizer`, `pip check` там проходит. Общее окружение имеет прежние
конфликты сторонних приложений и не объявляется полностью согласованным.

Не подтверждены: установка/драйвер/GPU/engine на Linux-сервере, загрузка модели,
реальная генерация, persistent resume после падения настоящего vLLM. Для них
есть server-only команды в README; они выполняются пользователем.
