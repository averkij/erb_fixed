"""Generate durable completions only. Run model loading on the Linux GPU server."""
import argparse
import asyncio
import importlib.metadata
import os
from pathlib import Path
import time

from erb.artifacts import prepare_run
from erb.common import append_jsonl, code_identity, digest, environment, manifest, now, run_lock, sha256
from erb.data import DATA_SHA, load_dataset, select_tasks
from erb.prompting import STOP, build_prompt, native_tokens


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=Path("data/exec_repo_bench.jsonl"))
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--model-revision", help="HF revision; resolved and recorded as immutable commit")
    p.add_argument("--tokenizer", help="Defaults to --model")
    p.add_argument("--tokenizer-revision")
    p.add_argument("--profile", required=True, choices=["qwen3-coder"])
    p.add_argument("--selection", choices=["full", "pilot"], default="full")
    p.add_argument("--dtype", choices=["bfloat16"], default="bfloat16")
    p.add_argument("--tensor-parallel-size", type=int, default=1)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--window", type=int, default=8192)
    p.add_argument("--context-tokens", type=int, default=4096)
    p.add_argument("--max-new-tokens", type=int, default=1024)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--gpu-memory-utilization", type=float, default=0.9)
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()
    if (args.batch_size < 1 or args.tensor_parallel_size < 1 or args.temperature < 0
            or not 0 < args.gpu_memory_utilization <= 1):
        p.error("Invalid batch size, TP, temperature or memory utilization")
    return args


def model_identity(name, revision):
    path = Path(name)
    if path.is_dir():
        files = sorted(p for p in path.rglob("*") if p.is_file()
                       and not any(x.startswith(".") for x in p.relative_to(path).parts)
                       and p.suffix in {".json", ".safetensors", ".bin", ".model", ".txt", ".jinja"})
        if not files:
            raise ValueError(f"No model/tokenizer artifacts: {path}")
        hashes = {p.relative_to(path).as_posix(): sha256(p) for p in files}
        return {"name": str(path.resolve()), "revision": None, "files_sha256": hashes}, None
    from huggingface_hub import model_info
    resolved = model_info(name, revision=revision).sha
    if not resolved:
        raise ValueError("Unable to resolve model revision")
    return {"name": name, "revision": resolved}, resolved


async def generate_batches(engine, sampling, tasks, tokenizer, args, output, fingerprint):
    async def one(task):
        prompt = build_prompt(tokenizer, task, args.window, args.context_tokens, args.max_new_tokens)
        started = now()
        clock = time.monotonic()
        request_id = str(task["task_id"])
        last = None
        async for result in engine.generate({"prompt_token_ids": prompt["prompt_token_ids"]}, sampling, request_id):
            last = result
        if last is None or not last.finished or len(last.outputs) != 1:
            raise RuntimeError(f"No final output for task {request_id}")
        answer = last.outputs[0]
        if answer.finish_reason not in {"stop", "length"}:
            raise RuntimeError(f"Unexpected finish reason for {request_id}: {answer.finish_reason}")
        if list(last.prompt_token_ids) != prompt["prompt_token_ids"]:
            raise RuntimeError("Engine changed the supplied prompt token IDs")
        row = dict(task_id=task["task_id"], dataset_sha256=DATA_SHA, fingerprint=fingerprint,
                   **prompt, generated_middle=answer.text, generated_token_ids=list(answer.token_ids),
                   usage={"prompt_tokens": len(prompt["prompt_token_ids"]), "completion_tokens": len(answer.token_ids)},
                   finish_reason=answer.finish_reason, stop_reason=answer.stop_reason,
                   started_at=started, completed_at=now(), duration_seconds=time.monotonic() - clock)
        append_jsonl(output, row)  # no await between serialization and fsync: one writer
        print(f"Saved task {request_id}: {answer.finish_reason}, {len(answer.token_ids)} tokens", flush=True)

    for offset in range(0, len(tasks), args.batch_size):
        pending = [asyncio.create_task(one(t)) for t in tasks[offset:offset + args.batch_size]]
        try:
            await asyncio.gather(*pending)
        except BaseException:
            for job in pending:
                job.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            raise


def main():
    args = parse_args()
    tasks = select_tasks(load_dataset(args.data), args.selection)
    # Heavy imports are confined to this generation entry point.
    from transformers import AutoConfig, AutoTokenizer
    from vllm import AsyncEngineArgs, AsyncLLMEngine, SamplingParams
    import torch
    model, revision = model_identity(args.model, args.model_revision)
    tokenizer_name = args.tokenizer or args.model
    tokenizer_revision_arg = args.tokenizer_revision or (args.model_revision if not args.tokenizer else None)
    if tokenizer_name == args.model and tokenizer_revision_arg == args.model_revision:
        tokenizer_model, tokenizer_revision = model, revision
    else:
        tokenizer_model, tokenizer_revision = model_identity(tokenizer_name, tokenizer_revision_arg)
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name, revision=tokenizer_revision, trust_remote_code=False)
    config = AutoConfig.from_pretrained(args.model, revision=revision, trust_remote_code=False)
    supported = getattr(config, "max_position_embeddings", None)
    if supported is None or args.window > supported:
        raise ValueError(f"Requested window {args.window} exceeds/has unknown native limit {supported}; choose explicitly")
    tokens = native_tokens(tokenizer)
    # Preflight every prompt before loading weights or writing a run.
    for task in tasks:
        build_prompt(tokenizer, task, args.window, args.context_tokens, args.max_new_tokens)
    env = environment()
    env.update(packages={n: importlib.metadata.version(n) for n in ["vllm", "torch", "transformers", "tokenizers", "huggingface-hub"]},
               cuda=torch.version.cuda, gpus=[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
               variables={k: os.environ.get(k) for k in ["CUDA_VISIBLE_DEVICES", "VLLM_USE_FLASHINFER_SAMPLER", "OMP_NUM_THREADS"]})
    settings = {k: v for k, v in vars(args).items() if k not in {"data", "run_dir", "resume", "model", "model_revision", "tokenizer", "tokenizer_revision"}}
    settings.update(n=1, context_order="close", top_p=1.0, stop_token_ids=[tokens[t] for t in STOP])
    run_config = dict(dataset_sha256=DATA_SHA, task_ids=[t["task_id"] for t in tasks],
                      code=code_identity(), model=model, tokenizer=tokenizer_model,
                      tokenizer_content_sha256=digest(tokenizer.backend_tokenizer.to_str()),
                      chat_template_sha256=digest(tokenizer.chat_template), native_tokens=tokens,
                      settings=settings, environment=env, control=None)
    with run_lock(args.run_dir):
        run, completed = prepare_run(args.run_dir, manifest(run_config, "generations"), args.resume)
        remaining = [t for t in tasks if t["task_id"] not in completed]
        if not remaining:
            print("All selected attempts are already durable")
            return
        engine = AsyncLLMEngine.from_engine_args(AsyncEngineArgs(
            model=args.model, revision=revision, tokenizer=tokenizer_name, tokenizer_revision=tokenizer_revision,
            dtype=args.dtype, tensor_parallel_size=args.tensor_parallel_size, seed=args.seed,
            max_model_len=args.window, max_num_seqs=args.batch_size,
            gpu_memory_utilization=args.gpu_memory_utilization, trust_remote_code=False))
        sampling = SamplingParams(temperature=args.temperature, top_p=1.0, n=1, seed=args.seed,
                                  max_tokens=args.max_new_tokens, stop_token_ids=settings["stop_token_ids"],
                                  skip_special_tokens=False, include_stop_str_in_output=False)
        with (args.run_dir / "generations.jsonl").open("a", encoding="utf-8", newline="\n") as out:
            asyncio.run(generate_batches(engine, sampling, remaining, tokenizer, args, out, run["fingerprint"]))


if __name__ == "__main__":
    main()
