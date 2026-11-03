# ExecRepoBench: раздельная генерация и Docker-оценка

Один checkout, два независимых процесса. `generate.py` на Linux-сервере загружает
модель через vLLM и сохраняет ответы. `eval.py` на Windows или Linux проверяет
готовый каталог ответов в Linux-контейнерах. Для оценки нужны **только Python
3.10+ и Docker CLI/daemon**; vLLM, CUDA, Torch и Transformers не импортируются.

Публичный пример: `Qwen/Qwen3-Coder-30B-A3B-Instruct`. Формат выбирается явным
`--profile qwen3-coder`, а не именем модели. Оригинальные девять файлов upstream
сохранены в Git baseline `7cf9b21fd2433afbfe0dc6ff158bb260a4906627`; происхождение
и исходные хеши — в [UPSTREAM.json](UPSTREAM.json). Старые combined-launcher
и установщик выводят указатель на новые команды и завершаются с кодом 2.

Полный локальный [контрольный отчёт](control_report/report.html), 2026-11-03:
oracle **1089/1164 (93,56%)**, 75 test_fail в четырёх проектах; empty —
**285 подтверждённых pass**, 870 test_fail, 7 timeout, 1 OOM и 1 infrastructure_error
после явного повтора четырёх инфраструктурных пробелов. Полная доля empty
не определена; границы — 24,48–24,57%. Все 50 проектов и 1164 ID сохранены,
задачи не исключались. Это результат текущих окружений; среди отказов oracle
есть отсутствующий NLTK punkt и несовместимое поведение зависимостей.
Полная модельная оценка остаётся заблокирована условием gold 1164/1164.
[CSV всех задач](control_report/tasks.csv), [JSON-доказательства](control_report/evidence.json),
[границы проверки](VALIDATION.md).

## 1. Зависимости и рабочие каталоги

Все относительные пути ниже считаются от корня checkout `erb_fixed`, включая
вызовы через `scripts/`. Сервер и локальный компьютер используют одну версию
кода, но отдельные окружения. Ничего не запускается через SSH автоматически.
Коммиты этой доработки пока локальные; перед новым клонированием нужно отдельно
опубликовать их либо вручную перенести checkout. Скрипты не публикуют код.

**Оценка на Windows:** рабочий каталог — выбранный вами локальный `erb_fixed`.
Нужен запущенный Docker Desktop в режиме **Linux containers** и обычный Python.
Сначала перейдите в корень checkout в PowerShell, затем:

```powershell
python --version
docker info --format '{{.OSType}}'
```

**Оценка на Linux:** рабочий каталог — корень checkout `erb_fixed`.
Нужны Python 3.10+ и доступный текущему пользователю Docker Engine:

```bash
python3 --version
docker info --format '{{.OSType}}'
```

В обоих случаях Docker должен вывести `linux`. Контроллер проверяет daemon,
но не устанавливает Docker, не запускает службу и не добавляет `sudo`.
Команды выше диагностические, файлов не создают, повторять можно свободно.

**Только сервер генерации:** пример использует точный рабочий каталог
`$HOME/erb_fixed` (разместите checkout там либо замените значение `ERB_ROOT`).
Нужны Linux, Python 3.11+, подходящие CUDA/драйвер и свободная GPU с достаточной
памятью для BF16-модели. Настройка драйвера находится вне этого runner.

```bash
set -euo pipefail
ERB_ROOT="$HOME/erb_fixed"
cd "$ERB_ROOT"
python3.11 -m venv .venv-gen
.venv-gen/bin/python -m pip install -r requirements-generation.txt
.venv-gen/bin/python -m pip check
nvidia-smi
```

Вход: checkout и [requirements-generation.txt](requirements-generation.txt).
Выход: локальное для сервера `.venv-gen`. Создавайте новое окружение; повторная
установка обновляет зависимости этого окружения. Оценке оно не требуется.
Совместимость конкретного сервера подтверждается только его фактическим запуском.

## 2. Закреплённые данные без родительского репозитория

Рабочий каталог — корень `erb_fixed` на соответствующем компьютере. Подготовка
использует stdlib и HTTPS, GPU/модель не нужны. HF revision, размеры и SHA256
обоих файлов закреплены в [data.lock.json](data.lock.json):
`CSJianYang/ExecRepoBench@fa61028ce495c9ceff58398b8a7c47b5ae9f5276`.

Серверу достаточно JSONL:

```bash
cd "$HOME/erb_fixed"
.venv-gen/bin/python prepare_data.py --jsonl-only --data-dir data
```

На машине оценки нужны JSONL и ZIP (пример для Windows; на Linux замените
`python` на `python3`):

```powershell
python prepare_data.py --data-dir data
```

Можно использовать уже скачанные **те же** файлы:
`python prepare_data.py --source-dir "PATH_TO_EXISTING_ASSETS" --data-dir data`.
Замените `PATH_TO_EXISTING_ASSETS` на каталог с release JSONL/ZIP. Он не должен
быть родительским репозиторием: это лишь необязательный источник копирования.

Выход: исходные `data/exec_repo_bench.jsonl`, `data/repos.zip` (кроме jsonl-only),
очищенный `data/tasks.jsonl`, `data/prepared.json`. Повторный запуск проверяет
хеши и использует целые файлы; повреждённый существующий файл вызывает ошибку.
Незавершённая загрузка `.part` скачивается заново. Производные tasks/prepared
перезаписываются. Исходные данные не исправляются.

Параметр `--data` всех runner принимает **оригинальный release JSONL**, проверяет
полный SHA256 и заново выбирает только семь полей задачи. `tasks.jsonl` — экспорт
для аудита, не замена исходного входа. Удаляются все прежние ответы, prompts и
метрики. Сохраняются 1 164 задачи, 50 проектов, шесть категорий. ID — нулевой
индекс исходной строки вместе с SHA256 полного JSONL. Пути, схема и контекст
проверяются; распаковка запрещает traversal, ссылки и Windows case collisions.

## 3. Образы, gold и empty до сравнения моделей

Место выполнения — **машина оценки**, рабочий каталог — корень `erb_fixed`.
Нужны подготовленные JSONL/ZIP, Docker Linux и сеть для сборки/установки пакетов.
Каждый проект получает отдельный образ Python 3.9, как в upstream.

```powershell
python prepare_images.py --data data/exec_repo_bench.jsonl --archive data/repos.zip --output-dir images
python controls.py --data data/exec_repo_bench.jsonl --control gold --run-dir runs/gold
python controls.py --data data/exec_repo_bench.jsonl --control empty --run-dir runs/empty
```

Те же команды на Linux выполняются через `python3`. Для быстрой диагностики
можно сначала указать `--selection pilot` у **всех трёх** команд, выбрать
каталоги `images-pilot`, `runs/gold-pilot`, `runs/empty-pilot` и оценивать также
с `--selection pilot`. Это только 12 задач / три проекта. Полный запуск
`prepare_images.py` по умолчанию готовит все 50 проектов, без `repos/build`.

Сборка использует неизменённое дерево архива, его `requirements.txt`, `pip
install -e .` из `/repo` и явные [зависимости тестов](docker/test-requirements.txt).
Любая ошибка установки останавливает соответствующий образ; сводный код 2
указывает на неполную подготовку. Ошибки не игнорируются. Тесты, драйверы и
правила отбора задач ради score не меняются. Удаляются Python `.pyc/.pyo` и
`__pycache__`, а установленные модули должны разрешаться именно в `/repo`.

Сборка по умолчанию последовательная; `--build-workers 4` явно разрешает четыре
параллельные сборки. Это отдельный параметр, не workers оценки. Для архивного
`eip712` без VCS-метаданных задаётся служебная версия сборки
`SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0+erb.archive`; она фиксируется в manifest
и не утверждает исходную release-версию. Для msgpack недостающий C-файл
генерируется из исходного `.pyx` закреплённым в архиве Cython. Конфликт
flake8/pycodestyle предотвращён совместимыми pins; тесты не переписываются.
У `python-sortedcontainers` архивная C++-зависимость `pyannote-banyan`
компилируется с `-std=c++03 -D_GLIBCXX_USE_CXX11_ABI=0`; флаги записываются
в `image.json`. Исходники зависимости не исправляются.
В этом же проекте сохранённый `pylint<2.6` требует `mccabe==0.6.1`:
несовместимый общий инструмент flake8 удаляется перед финальным `pip check`;
его использует dev-окружение другого проекта, а не этот тестовый драйвер.
Обе команды явно записаны в image manifest.

Выход: `images/manifest.json`, по проекту `build.log`, `image.json`,
`packages.txt`, `imports.json`; сохранены base digest, image ID, версии пакетов,
хеши build-входов и пути импортов. Неготовые образы не допускаются к оценке.
Повторная подготовка использует прежний base digest и готовые image ID при
совпадении build fingerprint. Неудавшиеся сборки повторяются. При изменении
build-настроек используйте новый каталог либо `--rebuild-changed`: предыдущие
диагностики сохраняются в `history/<fingerprint>/`, затем обновляются только
производные build-файлы. Для явной смены базы есть
`--base-image`; для долгой установки — `--build-timeout` (секунды).

В текущей локальной Windows-среде два native Docker build-клиента зависали
после export DONE. Тот же `prepare_images.py`, запущенный в локальной WSL,
успешно завершил подготовку. Если встречается этот симптом, можно использовать
Linux-команду подготовки в WSL и общий image store Docker Desktop; это локальный
запуск, не SSH на сервер. Уже готовые matching image IDs переиспользуются.

Gold/empty — **явно записанные** ответы с отдельными manifest. Повторная запись
требует `--resume` и совпадения fingerprint либо нового каталога. В gold берётся
ровно `middle_code`; в empty — ровно пустая строка. В оценщике fallback к gold нет.

Windows, PowerShell:

```powershell
.\scripts\evaluate_local.ps1 --data data/exec_repo_bench.jsonl --run-dir runs/gold --output-dir evaluation/gold --images images/manifest.json
.\scripts\evaluate_local.ps1 --data data/exec_repo_bench.jsonl --run-dir runs/empty --output-dir evaluation/empty --images images/manifest.json
```

Linux:

```bash
bash scripts/evaluate_local.sh --python python3 --data data/exec_repo_bench.jsonl --run-dir runs/gold --output-dir evaluation/gold --images images/manifest.json
bash scripts/evaluate_local.sh --python python3 --data data/exec_repo_bench.jsonl --run-dir runs/empty --output-dir evaluation/empty --images images/manifest.json
```

Выход: `evaluation/<control>/summary.json`, `manifest.json`, `results.jsonl`,
`tasks/<id>/stdout.txt`, `stderr.txt` и `result.json`. Результат каждой задачи
сохраняется до агрегации; промежуточная сводка обновляется раз в десять результатов.
Кратковременные Windows-блокировки атомарной перезаписи повторяются; блокировка
живой сводки не прерывает сохранение основного JSONL. Перед полным model score требуются
**1164/1164 pass в gold**. Непрошедший gold требует диагностики среды, не
исключения задач. Доля успеха empty публикуется как чувствительность тестов;
задачи с успешным empty автоматически не исключаются.

## 4. Серверный пилот генерации

Место: Linux GPU-сервер, точный cwd в примере `$HOME/erb_fixed`.
Входы: подготовленный JSONL, окружение генерации и публичная модель. Сеть нужна
для первого получения весов/tokenizer; последующие обращения используют HF cache.
Выберите свободную GPU в `CUDA_VISIBLE_DEVICES`.

```bash
set -euo pipefail
cd "$HOME/erb_fixed"
export CUDA_VISIBLE_DEVICES=0
bash scripts/generate_qwen30b.sh --python .venv-gen/bin/python \
  --data data/exec_repo_bench.jsonl --run-dir runs/qwen30b-pilot \
  --selection pilot --model-revision main
```

`main` разрешается в immutable HF commit и записывается в manifest. Для
воспроизведения подставьте этот commit вместо `main`. Локальные model/tokenizer
каталоги допустимы через `--model` / `--tokenizer`: их файлы хешируются, включая
веса; это может занять время. Не меняйте модель во время запуска.

Пилот детерминированно берёт две первые подходящие задачи каждой категории,
предпочитая второй проект, и сортирует 12 ID. Это проверка цепочки, не итоговый
score. У полного набора и пилота разные каталоги и fingerprint.

Начальные настройки: BF16, TP=1, temperature=0, n=1, seed=0, окно 8192,
внешний контекст до 4096 токенов, выход до 1024, batch=8. Можно явно менять
`--tensor-parallel-size`, `--temperature`, `--seed`, `--window`,
`--context-tokens`, `--max-new-tokens`, `--batch-size`,
`--gpu-memory-utilization`; настройки записываются. Превышение native окна
вызывает ошибку, ограничения молча не снижаются.

Протокол Qwen3-Coder: PSM `<|fim_prefix|>prefix<|fim_suffix|>suffix<|fim_middle|>`
в user-сообщении; system `You are a code completion assistant.`; native chat
template применяется к итоговому содержимому один раз. Stop-набор официального
примера: FIM prefix/suffix/pad, repo_name, file_sep, endoftext, im_end
(проверяются native token IDs). Контекст сохраняет порядок `close`: выбор
сначала в исходном порядке релевантности, затем разворот. Все заголовки и chat
токены входят в бюджет. Сохраняются точные хвост prefix и начало suffix;
готовый prompt повторно токенизируется и проверяется. Срезы отражены в записи.

Выход: `runs/qwen30b-pilot/manifest.json` и `generations.jsonl`. Каждый полученный
ответ записывается с flush/fsync сразу: ID, hash данных/fingerprint, точный prompt
и IDs, middle без strip/извлечения Markdown, output IDs, usage, finish/stop reason,
время. Manifest фиксирует модель/tokenizer, код, параметры и окружение.

Для продолжения повторите ту же команду с `--resume`. Завершённые ID, включая
пустой ответ и `finish_reason=length`, пропускаются. Менять выборку, модель,
параметры, код или окружение при resume нельзя. Повреждённый/дублированный JSONL
вызывает ошибку. Оборванная последняя строка не отбрасывается автоматически:
сохраните копию и разберите повреждение явно. `.lock` после аварии удаляется
вручную лишь после проверки, что прежний процесс завершён.

## 5. Ручной перенос и оценка пилота

Вручную скопируйте **весь каталог запуска**, минимум два файла manifest/JSONL,
на машину оценки, например в `runs/qwen30b-pilot`. Весов/tokenizer/CUDA там не
нужно. Автоматических SSH, копирования и поиска checkpoint нет. Проверяются hash
данных, fingerprint и точный набор ID; дубликаты, неизвестные ID и неполный вход
отвергаются до запуска кандидатов.

Windows, cwd — корень локального `erb_fixed`:

```powershell
.\scripts\evaluate_local.ps1 --data data/exec_repo_bench.jsonl --run-dir runs/qwen30b-pilot --output-dir evaluation/qwen30b-pilot --images images/manifest.json --selection pilot --workers 1 --cpus 2 --memory 4g --pids 256 --timeout 240
```

Linux, cwd — корень локального `erb_fixed`:

```bash
bash scripts/evaluate_local.sh --python python3 --data data/exec_repo_bench.jsonl --run-dir runs/qwen30b-pilot --output-dir evaluation/qwen30b-pilot --images images/manifest.json --selection pilot --workers 1 --cpus 2 --memory 4g --pids 256 --timeout 240
```

Оба launcher принимают одинаковые `--data`, `--run-dir`, `--output-dir`,
`--images`, `--selection`, `--workers`, `--cpus`, `--memory`, `--pids`,
`--timeout`, `--gold-summary`. `--python` выбирает исполняемый файл; иначе
используется `$PYTHON` / `$env:PYTHON`, затем `python`. Пути с пробелами заключайте
в кавычки. Скрипты передают параметры общему `eval.py` и возвращают его код.
PowerShell при блокировке политикой можно вызвать через
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/evaluate_local.ps1 ...`.

Каждая задача запускается в свежем контейнере, меняется только целевой файл
кандидата: UTF-8 bytes от `prefix + generated_middle + suffix`, без конвертации
CRLF/пробелов. Сеть отключена; нет host bind mounts, Docker socket, дополнительных
capabilities; UID/GID 10001, no-new-privileges. Записываемый слой только у
собственного контейнера. Ограничения по умолчанию — один worker, 2 CPU, 4 GiB,
256 PID, 240 секунд исполнения. По таймауту убивается весь контейнер с потомками.
Stdout/stderr, exit code, OOM, длительность, hash кандидата и наблюдаемые импорты
сохраняются до удаления контейнера. Образ всегда выбирается по image ID.

Статусы: `pass`, `test_fail`, `timeout`, `oom`, `infrastructure_error`.
Для gold/empty также записывается infrastructure_error по каждой задаче проекта
с неготовым образом: такой reference ещё не был проверен. Модельный запуск
при отсутствии готового образа отвергается.
Timeout/OOM — неуспех кандидата. При infrastructure_error итог неполон,
`micro_pass_at_1_percent=null`, exit=2. Завершённая оценка возвращает 0 даже при
неуспешных кандидатах. Каждый запуск оценки требует нового пустого output-dir;
перезаписи и неявного resume нет. Генерации при этом можно использовать повторно.

## 6. Полный запуск и чтение результатов

На сервере, cwd `$HOME/erb_fixed`, после пилота:

```bash
cd "$HOME/erb_fixed"
bash scripts/generate_qwen30b.sh --python .venv-gen/bin/python \
  --data data/exec_repo_bench.jsonl --run-dir runs/qwen30b-full \
  --selection full --model-revision main
```

Для точного повторения пилота замените `main` на его сохранённый commit.
После ручного переноса полного каталога на машине оценки, cwd — её `erb_fixed`:

```powershell
.\scripts\evaluate_local.ps1 --data data/exec_repo_bench.jsonl --run-dir runs/qwen30b-full --output-dir evaluation/qwen30b-full --images images/manifest.json --gold-summary evaluation/gold/summary.json
```

Linux использует ту же строку параметров после
`bash scripts/evaluate_local.sh --python python3`. Полная модельная оценка
блокируется без gold 1164/1164 с теми же image IDs, данными, лимитами и исходным
кодом контроллера. Проверяются также gold manifest и сохранённые results.

`summary.json` содержит micro pass@1 в процентах, числители/знаменатели,
распределение статусов, все шесть категорий и проекты. Отсутствующие категории
имеют expected=0 и null score. ES не влияет на запуск тестов: нормализация
upstream удаляет тройные строковые литералы и пустые строки, затем strip;
`#`-комментарии сохраняются. Реализация сравнения закреплена на поведении
`fuzzywuzzy 0.18.0` с **difflib SequenceMatcher, autojunk=True**, с upstream
порядком аргументов и целочисленным округлением пары. Дополнительный Levenshtein
не переключает backend. Python/version и ES implementation записываются;
исторические ES с неизвестным backend нельзя считать строго сопоставимыми.

## 7. Локальные проверки и границы подтверждения

Рабочий каталог — корень `erb_fixed`. Unit/launcher-проверки требуют Python stdlib;
Linux launcher проверяется в Linux либо WSL Ubuntu, Windows — в PowerShell.
Docker-проверка дополнительно требует Linux daemon и загрузку Python 3.9 image:

```powershell
python -m unittest discover -s tests -v
python tests/docker_integration.py --output-dir test-artifacts/docker
```

Выход unit-тестов — консоль; Docker-check пишет build log/report и diagnostics в
`test-artifacts/docker`, создаёт только синтетический проект и удаляет свой
временный image tag. Для повторной независимой проверки выбирайте новый output-dir.
Это тест изоляции/статусов, не benchmark score.

Проверка настоящего tokenizer на CPU, без загрузки модели (нужны Transformers
из requirements-tokenizer-check.txt, но не vLLM):

```powershell
python tests/tokenizer_check.py --data data/exec_repo_bench.jsonl --selection full --output test-artifacts/tokenizer.json
```

Она скачивает только tokenizer, фиксирует revision, проверяет native stops,
однократную обвязку и бюджет всех prompts, перезаписывает JSON-отчёт. Доступен
независимый `--backend tokenizers` с оригинальным tokenizer.json и Jinja template;
этот режим отдельно обозначается в отчёте и не проверяет AutoTokenizer.

Рекомендуемое отдельное Windows CPU-окружение (тот же cwd; создание/установка
обновляют только `.venv-tokenizer`):

```powershell
python -m venv .venv-tokenizer
.venv-tokenizer/Scripts/python.exe -m pip install -r requirements-tokenizer-check.txt
.venv-tokenizer/Scripts/python.exe tests/tokenizer_check.py --data data/exec_repo_bench.jsonl --selection full
```

Полный отчёт oracle/empty строится после двух полных оценок на машине оценки,
cwd — корень `erb_fixed`, Python stdlib, без сети/модели:

```powershell
python report_controls.py --data data/exec_repo_bench.jsonl --gold evaluation/gold --empty evaluation/empty --images images/manifest.json --output-dir control_report
```

Входы — исходный JSONL, оба measured manifest/results и image manifest. Выходы —
`control_report/report.html`, `report.md`, `evidence.json`, `tasks.csv` и лицензия Inter.
Повторный вызов перезаписывает производный отчёт; сырые измерения не меняются.
Отчёт включает все 50 проектов/шесть категорий и сохраняет инфраструктурные
пробелы с точными знаменателями.

Если полный контроль завершился с инфраструктурными пробелами, их можно явно
повторить в новом каталоге, сохранив исходные измерения. Cwd тот же; Docker
должен быть доступен. Повтор использует один worker и исходные образы/лимиты,
проверяет совпадение исходного кода и не повторяет test_fail/timeout/OOM:

```powershell
python retry_controls.py --data data/exec_repo_bench.jsonl --source evaluation/empty --control empty --output-dir evaluation/empty-infra-retry
python report_controls.py --data data/exec_repo_bench.jsonl --gold evaluation/gold --empty evaluation/empty --empty-retry evaluation/empty-infra-retry --images images/manifest.json --output-dir control_report
```

Для gold используются `--control gold` и `--gold-retry`. Выход повторной оценки —
собственные manifest/results/summary и диагностика. Новый каталог обязателен;
автоматической перезаписи нет. Отчёт явно показывает повтор, сохраняет первичные
статусы и проверяет, что заменены только исходные infrastructure_error. Такая
сводка контролей не подменяет исходный gold-summary для model gate.

Фактический статус проверок, включая ограничения полного gold и сервера:
[VALIDATION.md](VALIDATION.md). Прохождение локальных тестов/пилота не заменяет
полный gold и не подтверждает совместимость GPU-сервера.

## Источники

- [Официальный Qwen3-Coder FIM-пример и stop IDs](https://github.com/QwenLM/Qwen3-Coder/tree/33bc6aabd7791ad7b32f7e92104f11f2359ba890#fill-in-the-middle-with-qwen3-coder).
- [Данные и revision](https://huggingface.co/datasets/CSJianYang/ExecRepoBench/tree/fa61028ce495c9ceff58398b8a7c47b5ae9f5276).
- [vLLM AsyncLLMEngine в закреплённой версии](https://github.com/vllm-project/vllm/blob/v0.32.0/vllm/engine/async_llm_engine.py).
- [Ограничения контейнеров Docker](https://docs.docker.com/reference/cli/docker/container/run/).
- [ExecRepoBench paper](https://arxiv.org/abs/2412.11990).

При использовании данных цитируйте Yang et al., *ExecRepoBench: Multi-level
Executable Code Completion Evaluation*, arXiv:2412.11990 (2024).
