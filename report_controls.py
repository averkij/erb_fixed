"""Offline Russian oracle/empty audit from measured control outputs (stdlib only)."""
import argparse
import base64
from collections import Counter
from html import escape
import json
from pathlib import Path
import shutil

from erb.common import ROOT, check_manifest, now, read_json, read_jsonl, sha256, write_json
from erb.data import CATEGORIES, DATA_SHA, load_dataset
from erb.metrics import STATUSES, summarize


def cell(value):
    return escape(str(value))


def table(headers, rows, ident="", filterable=False):
    head = "".join(f"<th scope='col'>{cell(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>" for row in rows)
    return f"<div class='table-scroll'><table id='{ident}'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def control(directory, kind, tasks):
    m = check_manifest(read_json(directory / "manifest.json"), "evaluation")
    if m["config"].get("control") != kind or m["config"].get("dataset_sha256") != DATA_SHA:
        raise ValueError(f"Expected measured {kind} control on pinned data")
    rows = list(read_jsonl(directory / "results.jsonl"))
    expected = {t["task_id"]: t for t in tasks}
    seen = set()
    for row in rows:
        i = row["task_id"]
        if i not in expected or i in seen or row["status"] not in STATUSES:
            raise ValueError("Unknown/duplicate control result or status")
        if row.get("dataset_sha256") != DATA_SHA or row.get("evaluation_fingerprint") != m["fingerprint"]:
            raise ValueError("Result fingerprint/data hash differs")
        task = expected[i]
        if row["repo_name"] != task["repo_name"] or row["fill_type"] != task["fill_type"]:
            raise ValueError("Result category/repository differs from source task")
        seen.add(i)
    summary = summarize(rows, tasks)
    return m, rows, summary


def fraction(group):
    return f"{group['passes']} / {group['expected']}"


def percentage(group):
    value = group["micro_pass_at_1_percent"]
    return f"{value:.2f}%" if value is not None else "не определена"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=Path("data/exec_repo_bench.jsonl"))
    p.add_argument("--gold", type=Path, required=True, help="Directory with measured gold manifest/results")
    p.add_argument("--empty", type=Path, required=True)
    p.add_argument("--images", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, default=Path("control_report"))
    args = p.parse_args()
    tasks = load_dataset(args.data)
    gm, gold, gs = control(args.gold, "gold", tasks)
    em, empty, es = control(args.empty, "empty", tasks)
    if (gm["config"]["images"] != em["config"]["images"]
            or gm["config"]["limits"] != em["config"]["limits"]):
        raise ValueError("Gold/empty image IDs or limits differ")
    images = check_manifest(read_json(args.images), "images")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checked = now()
    windows = {}
    for label, rows in [("gold", gold), ("empty", empty)]:
        starts = [r["started_at"] for r in rows if r.get("started_at")]
        ends = [r["completed_at"] for r in rows if r.get("completed_at")]
        windows[label] = {"start": min(starts) if starts else None, "end": max(ends) if ends else None}
    overlap = (all(w["start"] and w["end"] for w in windows.values())
               and max(w["start"] for w in windows.values()) < min(w["end"] for w in windows.values()))
    compact = lambda rows: [{k: row.get(k) for k in ["task_id", "repo_name", "fill_type", "status", "exit_code", "duration_seconds",
                           "oom_killed", "timed_out", "candidate_sha256", "infrastructure_error", "runner"]} for row in sorted(rows, key=lambda r: r["task_id"])]
    evidence = dict(created_at=checked, dataset_sha256=DATA_SHA, gold=gs, empty=es,
                    measurement_windows=windows, controls_overlap=overlap,
                    gold_manifest=gm, empty_manifest=em, images_manifest=images,
                    results={"gold": compact(gold), "empty": compact(empty)},
                    input_sha256={"gold_results": sha256(args.gold / "results.jsonl"),
                                  "empty_results": sha256(args.empty / "results.jsonl"), "images": sha256(args.images)})
    write_json(args.output_dir / "evidence.json", evidence)
    all_gold = gs["complete"] and gs["passes"] == len(tasks)
    known_gold_fail = sum(gs["statuses"][s] for s in ["test_fail", "timeout", "oom"])
    verdict = ("Oracle: 100% подтверждено" if all_gold else
               "Oracle: 100% не достигнуто в этой среде" if known_gold_fail else
               "Oracle: 100% пока не подтверждено — проверка неполна")
    overview = [("Эталон (oracle)", gs), ("Пустая вставка", es)]
    markdown = ["# ExecRepoBench: полный oracle и empty контроль", "", verdict, "",
                f"Дата UTC: {checked}. Данные: {DATA_SHA}.", "",
                "| Контроль | Pass / все задачи | Полная доля | Тестировано | Test fail | Timeout | OOM | Infrastructure | Не записано |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for label, group in overview:
        c = group["statuses"]
        markdown.append(f"| {label} | {fraction(group)} | {percentage(group)} | {group['scored']} | {c['test_fail']} | {c['timeout']} | {c['oom']} | {c['infrastructure_error']} | {group['expected']-group['recorded']} |")
    markdown += ["", "Знаменатель — все 1164 исходные задачи. При infrastructure_error полная доля не определена.",
                 "Успешный empty не исключает задачу. Тесты/исходные проекты/выборка не менялись.", "",
                 "## По категориям", "", "| Категория | Oracle pass / N | Oracle infra | Empty pass / N | Empty infra |", "| --- | ---: | ---: | ---: | ---: |"]
    categories = []
    for category in CATEGORIES:
        g, e = gs["categories"][category], es["categories"][category]
        categories.append([cell(category), fraction(g), str(g["statuses"]["infrastructure_error"]), fraction(e), str(e["statuses"]["infrastructure_error"])])
        markdown.append(f"| {category} | {fraction(g)} | {g['statuses']['infrastructure_error']} | {fraction(e)} | {e['statuses']['infrastructure_error']} |")
    markdown += ["", "## Все 50 проектов", "", "| Проект | Oracle pass / N | Oracle fail/timeout/OOM | Oracle infra | Empty pass / N | Empty fail/timeout/OOM | Empty infra |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    repositories = []
    issues = []
    for repo in sorted(gs["repositories"]):
        g, e = gs["repositories"][repo], es["repositories"][repo]
        fails = lambda group: sum(group["statuses"][s] for s in ["test_fail", "timeout", "oom"])
        row = [cell(repo), fraction(g), str(fails(g)), str(g["statuses"]["infrastructure_error"]), fraction(e), str(fails(e)), str(e["statuses"]["infrastructure_error"])]
        repositories.append(row)
        markdown.append("| " + " | ".join(row) + " |")
        failed = next((r for r in gold if r["repo_name"] == repo and r["status"] != "pass"), None)
        if failed:
            log = args.gold / "tasks" / str(failed["task_id"]) / "stderr.txt"
            text = log.read_text("utf-8", errors="replace") if log.exists() else failed.get("infrastructure_error", "")
            image_record = images["config"]["images"].get(repo, {})
            if image_record.get("status") != "ready":
                build = args.images.parent / repo / "build.log"
                if build.exists():
                    text += "\n\nBUILD LOG (tail):\n" + build.read_text("utf-8", errors="replace")[-10000:]
            issues.append(f"<details><summary>{cell(repo)} · задача {failed['task_id']} · {cell(failed['status'])}</summary><pre>{cell(text[-12000:])}</pre></details>")
            markdown += ["", f"### {repo}: пример gold {failed['task_id']} — {failed['status']}", "", "```text", text[-4000:], "```", ""]
    limits = gm["config"]["limits"]
    ready = sum(item["status"] == "ready" for item in images["config"]["images"].values())
    markdown += ["", "## Метод и границы", "",
                 f"Образы: {ready}/50 готовы. Base: {images['config']['base_image']}.",
                 f"Ограничения: {json.dumps(limits, ensure_ascii=False)}; workers gold={gm['config']['workers']}, empty={em['config']['workers']}.",
                 f"Запуски контролей перекрывались по времени: {overlap}. Лимиты workers относятся к каждому запуску отдельно.",
                 "Каждый кандидат в свежем Linux-контейнере, сеть отключена, непривилегированный пользователь; точные prefix+middle+suffix.",
                 "Это локальное исполнение контрольных тестов. Модель/GPU/vLLM и серверная генерация не проверялись.",
                 "Полные fingerprints, image IDs, статусы всех задач и сведения об импортах сохранены в evidence.json.",
                 "При инфраструктурных ошибках итоговый model score не разрешён; нельзя объявлять непроверенные reference ошибочными."]
    (args.output_dir / "report.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    assets = ROOT / "report_assets"
    style = (assets / "editorial.css").read_text("utf-8")
    font = base64.b64encode((assets / "InterVariable-4.1.woff2").read_bytes()).decode()
    style = style.replace("url(InterVariable-4.1.woff2)", "url(data:font/woff2;base64," + font + ")")
    style += "\ncode{overflow-wrap:anywhere;word-break:break-word}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-width:100%;font:11px/1.55 Consolas,monospace}details{border-top:1px solid var(--rule);padding:12px 0}summary{cursor:pointer}#repos{min-width:850px}.controls{margin-bottom:16px}"
    style += "\n@media(max-width:650px){.metrics{grid-template-columns:1fr;gap:14px}.metric{border-left:0;border-top:1px solid var(--rule);padding:12px 0 0}.metric:first-child{border-top:0;padding-top:0}.metric strong{white-space:nowrap}}"
    summary_rows = []
    for label, group in overview:
        c = group["statuses"]
        summary_rows.append([cell(label), fraction(group), percentage(group), str(group["scored"]), str(c["test_fail"]), str(c["timeout"]), str(c["oom"]), str(c["infrastructure_error"]), str(group["expected"]-group["recorded"])])
    html = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ExecRepoBench — oracle и empty, все задачи</title><style>{style}</style></head><body><main>
<header class="masthead"><a class="brand" href="#top">ExecRepoBench / Control audit</a><span>{cell(checked[:10])} · локальное исполнение</span></header>
<div class="intro" id="top"><p class="kicker">Измерение стенда</p><h1>Эталонные и пустые вставки</h1><p class="subtitle">Все 1 164 исходные задачи и 50 проектов: сколько эталонов проходит тесты и насколько тесты чувствительны к удалению вставки.</p>
<div class="metrics"><div class="metric"><strong>{fraction(gs)}</strong><span>oracle: подтверждённые pass / все задачи</span></div><div class="metric"><strong>{fraction(es)}</strong><span>empty: pass / все задачи</span></div><div class="metric"><strong>{ready} / 50</strong><span>готовых окружений проектов</span></div></div></div>
<nav class="navigation" aria-label="Содержание"><a href="#result">Результат</a><a href="#categories">Категории</a><a href="#repositories">Проекты</a><a href="#failures">Диагностика</a><a href="#method">Метод и источники</a></nav>
<section class="section" id="result"><p class="kicker">01 / Проверка oracle</p><h2>{cell(verdict)}</h2>
{table(['Контроль','Pass / все','Полная доля','Тестировано','Test fail','Timeout','OOM','Infrastructure','Не записано'], summary_rows)}
<p class="note">Знаменатель — все 1 164 задачи. При проблемах инфраструктуры полная доля не определена: неизвестные исходы нельзя превращать в провал reference или незаметно исключать. Успешный empty остаётся в наборе.</p></section>
<section class="section" id="categories"><p class="kicker">02 / Все шесть категорий</p><h2>Результаты по типу вставки</h2>{table(['Категория','Oracle pass / N','Oracle infra','Empty pass / N','Empty infra'], categories)}</section>
<section class="section" id="repositories"><p class="kicker">03 / Все 50 проектов</p><h2>Проверка каждого репозитория</h2><div class="controls"><label for="repo-filter">Поиск проекта</label> <input id="repo-filter" type="search" placeholder="Название проекта"> <span id="shown" role="status">50 проектов</span></div>
{table(['Проект','Oracle pass / N','Oracle fail / timeout / OOM','Oracle infra','Empty pass / N','Empty fail / timeout / OOM','Empty infra'], repositories, 'repos')}
<p class="caption">N — исходное число задач проекта; число проверенных задач и инфраструктурные пробелы доступны в JSON-доказательствах.</p></section>
<section class="section" id="failures"><p class="kicker">04 / Причины непрохождения</p><h2>Диагностика reference</h2><p class="prose">Для каждого проекта с неуспешным gold приведён один пример. Это наблюдаемый результат в указанной среде, а не доказательство дефекта эталона. Полный список задач и статусов — в <a href="evidence.json">evidence.json</a>.</p>{''.join(issues) or '<p>Неуспешных gold в записанных результатах нет.</p>'}</section>
<section class="section" id="method"><p class="kicker">05 / Метод, источники и границы</p><h2>Что именно проверено</h2><div class="prose"><p>Из неизменённого release JSONL удалены исторические генерации. ID — индекс строки плюс SHA256 полного датасета. Oracle явно подставляет reference middle; empty явно подставляет пустую строку. Кандидат собирается точно как prefix + middle + suffix.</p><p>Каждая задача — свежий Linux-контейнер, UID 10001, без сети, host mounts и Docker socket. Ограничения: {cell(json.dumps(limits))}; workers: gold {gm['config']['workers']}, empty {em['config']['workers']}. Образы собраны на Python 3.9, base digest: <code>{cell(images['config']['base_image'])}</code>. Исходные проекты, тесты и отбор задач не менялись.</p><p>Это локальные контрольные измерения. Модель, CUDA, vLLM и серверная генерация не проверялись. Полная модельная оценка требует 1164/1164 gold pass с той же инфраструктурой. Изменения окружения и build inputs фиксируются в image manifest; пакету без VCS может быть задана явно обозначенная служебная SCM-версия для сборки.</p><p>Данные: <a href="https://huggingface.co/datasets/CSJianYang/ExecRepoBench/tree/fa61028ce495c9ceff58398b8a7c47b5ae9f5276">закреплённый HF revision</a>, SHA256 <code>{DATA_SHA}</code>. <a href="https://arxiv.org/abs/2412.11990">Статья ExecRepoBench</a>. Машиночитаемые результаты: <a href="evidence.json">evidence.json</a>; текстовая версия: <a href="report.md">report.md</a>. Полные сырые stdout/stderr/build logs сохраняются локально в каталогах запусков; JSON содержит fingerprints и хеши входов.</p></div></section>
<footer class="page-footer">ExecRepoBench · oracle / empty controls · {cell(checked)} · Inter 4.1, OFL</footer></main>
<script>const input=document.getElementById('repo-filter');const rows=[...document.querySelectorAll('#repos tbody tr')];input.addEventListener('input',()=>{{let count=0;const term=input.value.toLocaleLowerCase();rows.forEach(row=>{{row.hidden=!row.cells[0].textContent.toLocaleLowerCase().includes(term);if(!row.hidden)count++}});document.getElementById('shown').textContent=count+' / 50 проектов'}});</script></body></html>"""
    (args.output_dir / "report.html").write_text(html, encoding="utf-8")
    shutil.copyfile(assets / "INTER-LICENSE.txt", args.output_dir / "INTER-LICENSE.txt")
    print("Oracle: all reference tasks passed" if all_gold else "Oracle: failed or unverified reference tasks remain")
    print(f"gold {fraction(gs)} / empty {fraction(es)}; reports in {args.output_dir}")


if __name__ == "__main__":
    main()
