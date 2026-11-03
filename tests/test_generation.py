import asyncio
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from erb.common import read_jsonl
from erb.data import clean_rows
from erb.prompting import FIM, STOP, SYSTEM, build_prompt, native_tokens
from generate import generate_batches
from test_data import sample


class Tokenizer:
    unk_token_id = -1
    chat_template = "test chat"
    tokens = {t: 100000 + i for i, t in enumerate(dict.fromkeys((*FIM, *STOP, "<|im_start|>")))}

    def encode(self, text, add_special_tokens=False):
        if text in self.tokens:
            return [self.tokens[text]]
        return list(text.encode("utf-8"))

    def convert_tokens_to_ids(self, t):
        return self.tokens.get(t, -1)

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        assert messages[0] == {"role": "system", "content": SYSTEM}
        return "<|im_start|>system\n" + messages[0]["content"] + "<|im_end|>\n<|im_start|>user\n" + messages[1]["content"] + "<|im_end|>\n<|im_start|>assistant\n"


class PromptTests(unittest.TestCase):
    def test_fim_chat_once_and_limits_exact_substrings(self):
        task = clean_rows([dict(sample(), prefix_code="я  \n" * 400, suffix_code="\tя\n" * 400,
                                context_code=[["/sample/a.py", "a" * 400], ["/sample/b.py", "b" * 400]])])[0]
        out = build_prompt(Tokenizer(), task, 1024, 240, 100)
        self.assertLessEqual(len(out["prompt_token_ids"]) + 100, 1024)
        self.assertEqual(out["prompt"].count("<|im_start|>assistant"), 1)
        self.assertEqual(out["prompt"].count(FIM[0]), 1)
        self.assertTrue(task["prefix_code"].endswith(out["prompt_parts"]["prefix"]))
        self.assertTrue(task["suffix_code"].startswith(out["prompt_parts"]["suffix"]))
        self.assertNotIn("\ufffd", out["prompt"])
        self.assertEqual(native_tokens(Tokenizer())[FIM[0]], Tokenizer.tokens[FIM[0]])
        with self.assertRaises(ValueError):
            build_prompt(Tokenizer(), task, 300, 240, 100)

    def test_close_order(self):
        task = clean_rows([dict(sample(), context_code=[["/sample/a.py", "aaa"], ["/sample/b.py", "bbb"]])])[0]
        ctx = build_prompt(Tokenizer(), task)["prompt_parts"]["context"]
        self.assertLess(ctx.index("b.py"), ctx.index("a.py"))

    def test_missing_native_token(self):
        tok = Tokenizer()
        tok.tokens = dict(tok.tokens)
        tok.tokens.pop(FIM[0])
        with self.assertRaises(ValueError):
            native_tokens(tok)

    def test_incremental_exact_middle_survives_sibling_failure(self):
        class Engine:
            async def generate(self, prompt, sampling, request_id):
                if request_id == "1":
                    await asyncio.sleep(0.02)
                    raise RuntimeError("interrupted")
                yield SimpleNamespace(finished=True, prompt_token_ids=prompt["prompt_token_ids"],
                                      outputs=[SimpleNamespace(text=" \r\n\t", token_ids=[1, 2], finish_reason="length", stop_reason=None)])
        args = SimpleNamespace(window=8192, context_tokens=4096, max_new_tokens=1024, batch_size=8)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "g.jsonl"
            with path.open("w", encoding="utf-8", newline="\n") as out, self.assertRaises(RuntimeError):
                asyncio.run(generate_batches(Engine(), None, clean_rows([sample(), sample()]), Tokenizer(), args, out, "hash"))
            rows = list(read_jsonl(path))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["generated_middle"], " \r\n\t")


if __name__ == "__main__":
    unittest.main()
