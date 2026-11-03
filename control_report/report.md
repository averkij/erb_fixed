# ExecRepoBench: полный oracle и empty контроль

Oracle: 100% не достигнуто в этой среде

Дата UTC: 2026-11-03T11:58:55.075170+00:00. Данные: b614124d827b5e7290e9f5e3e96522583a6bb9a4b0131ff38e35a7b29716c4c5.

Отдельные повторные попытки только для исходных infrastructure_error: empty: 4. Сводка использует повторные результаты для этих ID; исходные попытки сохранены в evidence.json и отдельных колонках tasks.csv. Тестовые провалы не заменяются; повторные задачи выполнялись с одним worker и теми же образами/кодом/лимитами.

| Контроль | Pass / все задачи | Полная доля | Тестировано | Test fail | Timeout | OOM | Infrastructure | Не записано |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Эталон (oracle) | 1089 / 1164 | 93.56% | 1164 | 75 | 0 | 0 | 0 | 0 |
| Пустая вставка | 285 / 1164 | не определена | 1163 | 870 | 7 | 1 | 1 | 0 |

Пустая вставка: 1 неизвестных исходов. Подтверждённая нижняя граница — 285/1164 (24.48%); верхняя при успехе всех неизвестных — 286/1164 (24.57%). Это границы, а не полный score.
Empty, ID 872 (python-pinyin): Runner/container exit codes differ.

Знаменатель — все 1164 исходные задачи. При infrastructure_error полная доля не определена.
Успешный empty не исключает задачу. Тесты/исходные проекты/выборка не менялись.

## Парный контроль

| Oracle / Empty | Empty pass | Empty fail/timeout/OOM | Empty infra/не записано |
| --- | ---: | ---: | ---: |
| Oracle pass | 285 | 803 | 1 |
| Oracle fail / timeout / OOM | 0 | 75 | 0 |
| Oracle infra / не записано | 0 | 0 | 0 |

## По категориям

| Категория | Oracle pass / N | Oracle infra | Empty pass / N | Empty infra |
| --- | ---: | ---: | ---: | ---: |
| Random Span Completion | 39 / 42 | 0 | 7 / 42 | 0 |
| Random Single-line Completion | 31 / 34 | 0 | 20 / 34 | 0 |
| Random Multi-line Completion | 34 / 38 | 0 | 11 / 38 | 0 |
| grammar-based: expression | 377 / 407 | 0 | 130 / 407 | 0 |
| grammar-based: statement | 253 / 266 | 0 | 52 / 266 | 0 |
| grammar-based: block | 355 / 377 | 0 | 65 / 377 | 1 |

## Все 50 проектов

| Проект | Oracle pass / N | Oracle fail/timeout/OOM | Oracle infra | Empty pass / N | Empty fail/timeout/OOM | Empty infra |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Chronyk | 15 / 15 | 0 | 0 | 3 / 15 | 12 | 0 |
| PTable | 27 / 27 | 0 | 0 | 5 / 27 | 22 | 0 |
| PyPattyrn | 22 / 22 | 0 | 0 | 3 / 22 | 19 | 0 |
| Unipath | 21 / 21 | 0 | 0 | 3 / 21 | 18 | 0 |
| algorithms | 22 / 22 | 0 | 0 | 8 / 22 | 14 | 0 |
| attrs | 12 / 12 | 0 | 0 | 1 / 12 | 11 | 0 |
| boltons | 18 / 18 | 0 | 0 | 3 / 18 | 15 | 0 |
| cacheout | 13 / 13 | 0 | 0 | 4 / 13 | 9 | 0 |
| compressed_rtf | 40 / 40 | 0 | 0 | 5 / 40 | 35 | 0 |
| css-html-js-minify | 13 / 13 | 0 | 0 | 11 / 13 | 2 | 0 |
| csv-diff | 26 / 26 | 0 | 0 | 1 / 26 | 25 | 0 |
| csvkit | 35 / 35 | 0 | 0 | 5 / 35 | 30 | 0 |
| datetime_truncate | 14 / 14 | 0 | 0 | 3 / 14 | 11 | 0 |
| dict2css | 17 / 17 | 0 | 0 | 10 / 17 | 7 | 0 |
| dpath-python | 13 / 13 | 0 | 0 | 3 / 13 | 10 | 0 |
| easyargs | 29 / 29 | 0 | 0 | 6 / 29 | 23 | 0 |
| edx-lint | 35 / 35 | 0 | 0 | 3 / 35 | 32 | 0 |
| eip712 | 25 / 25 | 0 | 0 | 8 / 25 | 17 | 0 |
| eml_parser | 24 / 24 | 0 | 0 | 6 / 24 | 18 | 0 |
| fastkml | 21 / 21 | 0 | 0 | 6 / 21 | 15 | 0 |
| geopy | 21 / 21 | 0 | 0 | 9 / 21 | 12 | 0 |
| gruut | 68 / 68 | 0 | 0 | 55 / 68 | 13 | 0 |
| html-to-json | 0 / 13 | 13 | 0 | 0 / 13 | 13 | 0 |
| imageio | 27 / 27 | 0 | 0 | 15 / 27 | 12 | 0 |
| json_repair | 40 / 40 | 0 | 0 | 5 / 40 | 35 | 0 |
| lxml_html_clean | 0 / 29 | 29 | 0 | 0 / 29 | 29 | 0 |
| markdown-it-py | 21 / 21 | 0 | 0 | 5 / 21 | 16 | 0 |
| maya | 15 / 15 | 0 | 0 | 5 / 15 | 10 | 0 |
| mdformat | 7 / 7 | 0 | 0 | 2 / 7 | 5 | 0 |
| moment | 19 / 19 | 0 | 0 | 4 / 19 | 15 | 0 |
| more-itertools | 51 / 51 | 0 | 0 | 2 / 51 | 49 | 0 |
| msgpack-python | 20 / 20 | 0 | 0 | 11 / 20 | 9 | 0 |
| objprint | 15 / 15 | 0 | 0 | 3 / 15 | 12 | 0 |
| pysrt | 21 / 21 | 0 | 0 | 5 / 21 | 16 | 0 |
| python-fastjsonschema | 27 / 27 | 0 | 0 | 3 / 27 | 24 | 0 |
| python-patterns | 12 / 12 | 0 | 0 | 8 / 12 | 4 | 0 |
| python-pinyin | 25 / 25 | 0 | 0 | 3 / 25 | 21 | 1 |
| python-rasterstats | 0 / 17 | 17 | 0 | 0 / 17 | 17 | 0 |
| python-sortedcontainers | 8 / 8 | 0 | 0 | 2 / 8 | 6 | 0 |
| shortuuid | 23 / 23 | 0 | 0 | 8 / 23 | 15 | 0 |
| sqlparse | 39 / 39 | 0 | 0 | 6 / 39 | 33 | 0 |
| tabulator-py | 25 / 25 | 0 | 0 | 13 / 25 | 12 | 0 |
| textdistance | 27 / 27 | 0 | 0 | 5 / 27 | 22 | 0 |
| transitions | 25 / 25 | 0 | 0 | 2 / 25 | 23 | 0 |
| truecase | 0 / 16 | 16 | 0 | 0 / 16 | 16 | 0 |
| tryme | 19 / 19 | 0 | 0 | 5 / 19 | 14 | 0 |
| untangle | 19 / 19 | 0 | 0 | 2 / 19 | 17 | 0 |
| w2n | 22 / 22 | 0 | 0 | 6 / 22 | 16 | 0 |
| workdays | 20 / 20 | 0 | 0 | 3 / 20 | 17 | 0 |
| xmltodict | 31 / 31 | 0 | 0 | 1 / 31 | 30 | 0 |

## Диагностика reference

Один пример на проект с неуспешным gold; полный список статусов — в evidence.json.

### html-to-json: пример gold 531 — test_fail

```text
 },
  +                 {
  +                     '_attributes': {
  +                         'href': '/static/css/style.css',
  +                         'rel': [
  +                             'stylesheet',
  +                         ],
  +                     },
  +                 },
  +             ],
                'meta': [
                    {
                        '_attributes': {
                            'charset': 'UTF-8',
                        },
                    },
                    {
                        '_attributes': {
                            'content': 'Yara Rule Manager',
                            'name': 'description',
                        },
                    },
                    {
                        '_attributes': {
                            'content': 'zI3MVR02eLr7MZ_BbS_4ZMlqjmmuriRFcvymZ6dD5Vc',
                            'name': 'google-site-verification',
                        },
  -                     'link': [
  +                 },
  -                         {
  ? --------
  +                 {
  -                             '_attributes': {
  ? --------
  +                     '_attributes': {
  +                         'content': 'yara,rules',
  +                         'name': 'keywords',
  -                                 'href': '/static/css/bootstrap.css',
  -                                 'rel': [
  -                                     'stylesheet',
  -                                 ],
  -                             },
  -                         },
  -                         {
  -                             '_attributes': {
  -                                 'href': '/static/css/style.css',
  -                                 'rel': [
  -                                     'stylesheet',
  -                                 ],
  -                             },
  -                         },
  -                     ],
  ?                     ^
  +                     },
  ?                     ^
  -                     'meta': [
  +                 },
  +             ],
  +             'script': [
  -                         {
  ? --------
  +                 {
  -                             '_attributes': {
  ? --------
  +                     '_attributes': {
  +                         'src': 'https://maps.googleapis.com/maps/api/js?v=3.exp',
  -                                 'content': 'yara,rules',
  -                                 'name': 'keywords',
  -                             },
  -                         },
  -                     ],
  ?                     ^
  +                     },
  ?                     ^
  -                     'script': [
  -                         {
  -                             '_attributes': {
  -                                 'src': 'https://maps.googleapis.com/maps/api/js?v=3.exp',
  -                             },
  -                         },
  -                     ],
                    },
                ],
                'title': [
                    {
                        '_value': 'MalwareConfig - Rule Manager',
                    },
                ],
            },
        ],
    }
========================= 1 failed, 20 passed in 3.44s =========================


STDERR:
Traceback (most recent call last):
  File "/opt/erb/runner.py", line 38, in main
    runpy.run_path("/repo/evaluate_repo.py", run_name="__main__")
  File "/usr/local/lib/python3.9/runpy.py", line 288, in run_path
    return _run_module_code(code, init_globals, run_name,
  File "/usr/local/lib/python3.9/runpy.py", line 97, in _run_module_code
    _run_code(code, mod_globals, init_globals,
  File "/usr/local/lib/python3.9/runpy.py", line 87, in _run_code
    exec(code, run_globals)
  File "/repo/evaluate_repo.py", line 28, in <module>
    run_pytest_in_directory(test_path)
  File "/repo/evaluate_repo.py", line 9, in run_pytest_in_directory
    raise Exception("Assert Error")
Exception: Assert Error

```


### lxml_html_clean: пример gold 611 — test_fail

```text
STDOUT (tail):


STDERR:
.....F.FF............
======================================================================
FAIL: test_host_whitelist_invalid (test_clean.CleanerTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/repo/tests/test_clean.py", line 322, in test_host_whitelist_invalid
    self.assertEqual(expected, cleaner.clean_html(html))
AssertionError: '<div></div>' != '<div>&lt;/div&gt;</div>'
- <div></div>
+ <div>&lt;/div&gt;</div>


======================================================================
FAIL: test_host_whitelist_sneaky_userinfo (test_clean.CleanerTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/repo/tests/test_clean.py", line 329, in test_host_whitelist_sneaky_userinfo
    self.assertEqual(expected, cleaner.clean_html(html))
AssertionError: '<div></div>' != '<div>&lt;/div&gt;</div>'
- <div></div>
+ <div>&lt;/div&gt;</div>


======================================================================
FAIL: test_host_whitelist_valid (test_clean.CleanerTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/repo/tests/test_clean.py", line 316, in test_host_whitelist_valid
    self.assertEqual(expected, cleaner.clean_html(html))
AssertionError: '<div><iframe src="https://example.com/page"></iframe></div>' != '<div><iframe src="https://example.com/page">&lt;/div&gt;</iframe></div>'
- <div><iframe src="https://example.com/page"></iframe></div>
+ <div><iframe src="https://example.com/page">&lt;/div&gt;</iframe></div>
?                                             ++++++++++++


----------------------------------------------------------------------
Ran 21 tests in 0.015s

FAILED (failures=3)
Traceback (most recent call last):
  File "/opt/erb/runner.py", line 38, in main
    runpy.run_path("/repo/evaluate_repo.py", run_name="__main__")
  File "/usr/local/lib/python3.9/runpy.py", line 288, in run_path
    return _run_module_code(code, init_globals, run_name,
  File "/usr/local/lib/python3.9/runpy.py", line 97, in _run_module_code
    _run_code(code, mod_globals, init_globals,
  File "/usr/local/lib/python3.9/runpy.py", line 87, in _run_code
    exec(code, run_globals)
  File "/repo/evaluate_repo.py", line 29, in <module>
    run_unittest_in_directory(test_path)
  File "/repo/evaluate_repo.py", line 20, in run_unittest_in_directory
    raise Exception("Error")
Exception: Error

```


### python-rasterstats: пример gold 873 — test_fail

```text
PendingDeprecationWarning: Use ...
FAILED tests/test_zonal.py::test_all_touched - PendingDeprecationWarning: Use...
FAILED tests/test_zonal.py::test_ndarray - PendingDeprecationWarning: Use `@`...
FAILED tests/test_zonal.py::test_alias - PendingDeprecationWarning: Use `@` m...
FAILED tests/test_zonal.py::test_add_stats - PendingDeprecationWarning: Use `...
FAILED tests/test_zonal.py::test_add_stats_prop - PendingDeprecationWarning: ...
FAILED tests/test_zonal.py::test_add_stats_prop_and_array - PendingDeprecatio...
FAILED tests/test_zonal.py::test_mini_raster - PendingDeprecationWarning: Use...
FAILED tests/test_zonal.py::test_percentile_good - PendingDeprecationWarning:...
FAILED tests/test_zonal.py::test_zone_func_has_return - PendingDeprecationWar...
FAILED tests/test_zonal.py::test_zone_func_good - PendingDeprecationWarning: ...
FAILED tests/test_zonal.py::test_zone_func_bad - PendingDeprecationWarning: U...
FAILED tests/test_zonal.py::test_percentile_nodata - PendingDeprecationWarnin...
FAILED tests/test_zonal.py::test_direct_features_collections - PendingDepreca...
FAILED tests/test_zonal.py::test_all_nodata - PendingDeprecationWarning: Use ...
FAILED tests/test_zonal.py::test_some_nodata - PendingDeprecationWarning: Use...
FAILED tests/test_zonal.py::test_nan_nodata - PendingDeprecationWarning: Use ...
FAILED tests/test_zonal.py::test_some_nodata_ndarray - PendingDeprecationWarn...
FAILED tests/test_zonal.py::test_transform - PendingDeprecationWarning: Use `...
FAILED tests/test_zonal.py::test_prefix - PendingDeprecationWarning: Use `@` ...
FAILED tests/test_zonal.py::test_geojson_out - PendingDeprecationWarning: Use...
FAILED tests/test_zonal.py::test_geojson_out_with_no_properties - PendingDepr...
FAILED tests/test_zonal.py::test_copy_properties_warn - PendingDeprecationWar...
FAILED tests/test_zonal.py::test_nan_counts - PendingDeprecationWarning: Use ...
================== 64 failed, 37 passed, 2 skipped in 21.76s ===================


STDERR:
INFO:fiona._err:GDAL signalled an error: err_no=4, msg='POLYGON ((244697.45179524383 1000369.2307574936, 244827.15493968062 1000373.0455558595, 244933.9692939227 1000353.9715640305, 244933.9692939227 1000353.9715640305, 244930.15449555693 1000147.9724522779, 244697.45179524383 1000159.4168473752, 244697.45179524383 1000369.2307574936)): File name too long'
INFO:fiona._err:GDAL signalled an error: err_no=4, msg='{"type": "InvalidGeometry", "coordinates": [30, 10]}: No such file or directory'
INFO:fiona._err:GDAL signalled an error: err_no=4, msg='POINT(245309 1000064): No such file or directory'
INFO:fiona._err:GDAL signalled an error: err_no=4, msg='POINT(245309 1000064): No such file or directory'
INFO:fiona._err:GDAL signalled an error: err_no=4, msg='POINT(245309 1000308): No such file or directory'
INFO:fiona._err:GDAL signalled an error: err_no=4, msg='/repo/tests/data/DOESNOTEXIST.shp: No such file or directory'
INFO:fiona._err:GDAL signalled an error: err_no=4, msg='blaghrlargh: No such file or directory'
INFO:rasterio._env:GDAL signalled an error: err_no=4, msg='blercherlerch: No such file or directory'
INFO:fiona._err:GDAL signalled an error: err_no=4, msg='POLYGON ((1 0, 4 0, 4 3, 1 3, 1 0)): No such file or directory'
Traceback (most recent call last):
  File "/opt/erb/runner.py", line 38, in main
    runpy.run_path("/repo/evaluate_repo.py", run_name="__main__")
  File "/usr/local/lib/python3.9/runpy.py", line 288, in run_path
    return _run_module_code(code, init_globals, run_name,
  File "/usr/local/lib/python3.9/runpy.py", line 97, in _run_module_code
    _run_code(code, mod_globals, init_globals,
  File "/usr/local/lib/python3.9/runpy.py", line 87, in _run_code
    exec(code, run_globals)
  File "/repo/evaluate_repo.py", line 29, in <module>
    run_pytest_in_directory(test_path)
  File "/repo/evaluate_repo.py", line 10, in run_pytest_in_directory
    raise Exception("Tests failed with exit code: {}".format(exit_code))
Exception: Tests failed with exit code: 1

```


### truecase: пример gold 1037 — test_fail

```text
STDOUT (tail):


STDERR:
..E
======================================================================
ERROR: test_get_true_case (test_truecase.TestTrueCase)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/repo/tests/test_truecase.py", line 13, in test_get_true_case
    result = self.tc.get_true_case(sentence)
  File "/repo/truecase/TrueCaser.py", line 105, in get_true_case
    tokens = word_tokenize(sentence)
  File "/usr/local/lib/python3.9/site-packages/nltk/tokenize/__init__.py", line 129, in word_tokenize
    sentences = [text] if preserve_line else sent_tokenize(text, language)
  File "/usr/local/lib/python3.9/site-packages/nltk/tokenize/__init__.py", line 106, in sent_tokenize
    tokenizer = load(f"tokenizers/punkt/{language}.pickle")
  File "/usr/local/lib/python3.9/site-packages/nltk/data.py", line 750, in load
    opened_resource = _open(resource_url)
  File "/usr/local/lib/python3.9/site-packages/nltk/data.py", line 876, in _open
    return find(path_, path + [""]).open()
  File "/usr/local/lib/python3.9/site-packages/nltk/data.py", line 583, in find
    raise LookupError(resource_not_found)
LookupError: 
**********************************************************************
  Resource [93mpunkt[0m not found.
  Please use the NLTK Downloader to obtain the resource:

  [31m>>> import nltk
  >>> nltk.download('punkt')
  [0m
  For more information see: https://www.nltk.org/data.html

  Attempted to load [93mtokenizers/punkt/PY3/english.pickle[0m

  Searched in:
    - '/tmp/nltk_data'
    - '/usr/local/nltk_data'
    - '/usr/local/share/nltk_data'
    - '/usr/local/lib/nltk_data'
    - '/usr/share/nltk_data'
    - '/usr/local/share/nltk_data'
    - '/usr/lib/nltk_data'
    - '/usr/local/lib/nltk_data'
    - ''
**********************************************************************


----------------------------------------------------------------------
Ran 3 tests in 2.254s

FAILED (errors=1)
Traceback (most recent call last):
  File "/opt/erb/runner.py", line 38, in main
    runpy.run_path("/repo/evaluate_repo.py", run_name="__main__")
  File "/usr/local/lib/python3.9/runpy.py", line 288, in run_path
    return _run_module_code(code, init_globals, run_name,
  File "/usr/local/lib/python3.9/runpy.py", line 97, in _run_module_code
    _run_code(code, mod_globals, init_globals,
  File "/usr/local/lib/python3.9/runpy.py", line 87, in _run_code
    exec(code, run_globals)
  File "/repo/evaluate_repo.py", line 28, in <module>
    run_unittest_in_directory(test_path)
  File "/repo/evaluate_repo.py", line 19, in run_unittest_in_directory
    raise Exception("Error")
Exception: Error

```


Статус test_fail означает ненулевой выход проектного test runner. Он может включать проблемы окружения: например, отсутствие тестового ресурса NLTK punkt или несовместимое поведение зависимостей. Нельзя интерпретировать все такие исходы как ошибки reference.

## Метод и границы

Образы: 50/50 готовы. Base: python@sha256:ff12c273af1e1814efcd8dfdefe16a70a4d901afe94dce721ffed8a34176f285.
Ограничения: {"cpus": 2.0, "memory": "4g", "pids": 256, "timeout": 240.0}; workers gold=6, empty=6.
Запуски контролей перекрывались по времени: True. Лимиты workers относятся к каждому запуску отдельно.
Таймауты и OOM зависят от лимитов и параллельной нагрузки; они не доказывают семантическую ошибку вставки.
Каждый кандидат в свежем Linux-контейнере, сеть отключена, непривилегированный пользователь; точные prefix+middle+suffix.
Это локальное исполнение контрольных тестов. Модель/GPU/vLLM и серверная генерация не проверялись.
Полные fingerprints, image IDs, статусы всех задач и сведения об импортах сохранены в evidence.json; плоская таблица всех ID — в tasks.csv.
При инфраструктурных ошибках итоговый model score не разрешён; нельзя объявлять непроверенные reference ошибочными.
