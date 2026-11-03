"""CPU-only prompt check with the real public tokenizer; no model/vLLM load."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from erb.common import digest, write_json
from erb.data import load_dataset, select_tasks
from erb.prompting import FIM, STOP, build_prompt, native_tokens


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--selection", choices=["pilot", "full"], default="pilot")
    p.add_argument("--revision", default="main")
    p.add_argument("--backend", choices=["transformers", "tokenizers"], default="transformers")
    p.add_argument("--output", type=Path, default=Path("test-artifacts/tokenizer.json"))
    args = p.parse_args()
    name = "Qwen/Qwen3-Coder-30B-A3B-Instruct"
    with urllib.request.urlopen(f"https://huggingface.co/api/models/{name}/revision/{args.revision}", timeout=60) as r:
        revision = json.load(r)["sha"]
    if args.backend == "transformers":
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(name, revision=revision, trust_remote_code=False)
    else:
        # Independent native tokenizer + exact HF template, useful when the host's
        # Transformers dependencies are incompatible. Does not test AutoTokenizer.
        from tokenizers import Tokenizer
        from jinja2.sandbox import ImmutableSandboxedEnvironment
        cache = args.output.parent / ("tokenizer-" + revision)
        cache.mkdir(parents=True, exist_ok=True)
        for filename in ["tokenizer.json", "tokenizer_config.json"]:
            dest = cache / filename
            if not dest.exists():
                with urllib.request.urlopen(f"https://huggingface.co/{name}/resolve/{revision}/{filename}", timeout=60) as r:
                    dest.write_bytes(r.read())
        backend = Tokenizer.from_file(str(cache / "tokenizer.json"))
        config = json.loads((cache / "tokenizer_config.json").read_text("utf-8"))
        class Adapter:
            unk_token_id = None
            chat_template = config["chat_template"]

            def encode(self, text, add_special_tokens=False):
                return backend.encode(text, add_special_tokens=add_special_tokens).ids

            def convert_tokens_to_ids(self, token):
                return backend.token_to_id(token)

            def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
                template = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True).from_string(self.chat_template)
                return template.render(messages=messages, add_generation_prompt=add_generation_prompt)
        tokenizer = Adapter()
    tokens = native_tokens(tokenizer)
    assert [tokens[t] for t in STOP] == [151659, 151661, 151662, 151663, 151664, 151643, 151645]
    report = []
    for task in select_tasks(load_dataset(args.data), args.selection):
        prompt = build_prompt(tokenizer, task)
        assert len(prompt["prompt_token_ids"]) <= 8192 - 1024
        assert prompt["prompt"].count("<|im_start|>assistant\n") == 1
        assert prompt["prompt"].count(FIM[0]) == 1
        assert task["prefix_code"].endswith(prompt["prompt_parts"]["prefix"])
        assert task["suffix_code"].startswith(prompt["prompt_parts"]["suffix"])
        report.append(dict(task_id=task["task_id"], prompt_tokens=len(prompt["prompt_token_ids"]),
                           truncation=prompt["truncation"], prompt_sha256=digest(prompt["prompt"])))
        if len(report) % 100 == 0:
            print(f"Checked {len(report)} prompts", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, dict(model=name, revision=revision, native_tokens=tokens,
               backend=args.backend, tokenizers=importlib.metadata.version("tokenizers"),
               transformers=importlib.metadata.version("transformers") if args.backend == "transformers" else None, results=report,
               scope="Local CPU tokenizer/prompt check only; no model, CUDA, vLLM or server execution"))
    print(f"PASS: {len(report)} real-tokenizer prompts; revision={revision}; tokens={min(r['prompt_tokens'] for r in report)}..{max(r['prompt_tokens'] for r in report)}")


if __name__ == "__main__":
    main()
