"""Explicit Qwen3-Coder PSM-in-chat profile; never infer format from model name."""
SYSTEM = "You are a code completion assistant."
FIM = ("<|fim_prefix|>", "<|fim_suffix|>", "<|fim_middle|>")
STOP = ("<|fim_prefix|>", "<|fim_suffix|>", "<|fim_pad|>", "<|repo_name|>",
        "<|file_sep|>", "<|endoftext|>", "<|im_end|>")


def encode(tokenizer, text):
    return tokenizer.encode(text, add_special_tokens=False)


def native_tokens(tokenizer):
    tokens = {}
    for token in (*FIM, *STOP, "<|im_start|>"):
        ids = encode(tokenizer, token)
        idx = tokenizer.convert_tokens_to_ids(token)
        if len(ids) != 1 or ids[0] != idx or idx is None or idx == tokenizer.unk_token_id:
            raise ValueError(f"Tokenizer lacks native token: {token}")
        tokens[token] = idx
    if len(set(tokens.values())) != len(tokens):
        raise ValueError("Native protocol tokens must have distinct IDs")
    if not tokenizer.chat_template:
        raise ValueError("Qwen3-Coder profile requires a native chat template")
    return tokens


def clip(tokenizer, text, limit, tail=False):
    """Keep an exact substring, including whitespace; do not decode broken byte tokens."""
    if limit <= 0:
        return ""
    if len(encode(tokenizer, text)) <= limit:
        return text
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        candidate = text[-mid:] if tail else text[:mid]
        if len(encode(tokenizer, candidate)) <= limit:
            low = mid
        else:
            high = mid - 1
    return (text[-low:] if tail else text[:low]) if low else ""


def render(tokenizer, content):
    return tokenizer.apply_chat_template(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}],
        tokenize=False, add_generation_prompt=True)


def build_prompt(tokenizer, task, window=8192, context_limit=4096, generation_limit=1024):
    if window <= generation_limit or context_limit < 0 or generation_limit < 1:
        raise ValueError("Invalid window/context/generation budgets")
    budget = window - generation_limit
    # Count chat, FIM, file and repository headers before allocating source tokens.
    target_header = f"##{task['file_name']}##:\n"
    base = f"## Repository: {task['repo_name']}\n"
    def content(ctx, pre, suf):
        return base + ctx + target_header + FIM[0] + pre + FIM[1] + suf + FIM[2]
    overhead = len(encode(tokenizer, render(tokenizer, content("", "", ""))))
    if budget - overhead < 2:
        raise ValueError("Window cannot accommodate protocol headers and source")
    if context_limit > budget - overhead - 2:
        raise ValueError("Context limit leaves no in-file budget; choose explicit smaller limits")
    blocks = []
    for name, code in task["context_code"]:
        block = f"##{name}##:\n{code}\n"
        # close: relevance order is reversed only after selection, like upstream.
        remaining = context_limit - sum(len(encode(tokenizer, x)) for x in blocks)
        if len(encode(tokenizer, block)) <= remaining:
            blocks.append(block)
        else:
            partial = clip(tokenizer, block, remaining)
            if partial:
                blocks.append(partial)
            break
    ctx = "".join(reversed(blocks))
    # Retokenization across boundaries can change counts; enforce the whole context cap.
    ctx = clip(tokenizer, ctx, context_limit, tail=True)
    available = budget - len(encode(tokenizer, render(tokenizer, content(ctx, "", ""))))
    if available < 2:
        raise ValueError("Protocol/context exceeds window")
    pre_ids = len(encode(tokenizer, task["prefix_code"]))
    suf_ids = len(encode(tokenizer, task["suffix_code"]))
    pre_budget = min(pre_ids, available // 2)
    suf_budget = min(suf_ids, available - pre_budget)
    pre_budget = min(pre_ids, available - suf_budget)
    pre = clip(tokenizer, task["prefix_code"], pre_budget, tail=True)
    suf = clip(tokenizer, task["suffix_code"], suf_budget)
    prompt = render(tokenizer, content(ctx, pre, suf))
    ids = encode(tokenizer, prompt)
    # Preserve selected context and the configured output limit. Trim only in-file
    # source budgets if boundary tokenization makes the final prompt too long.
    while len(ids) > budget and (pre_budget or suf_budget):
        excess = len(ids) - budget
        if pre_budget >= suf_budget:
            pre_budget = max(0, pre_budget - excess)
            pre = clip(tokenizer, task["prefix_code"], pre_budget, tail=True)
        else:
            suf_budget = max(0, suf_budget - excess)
            suf = clip(tokenizer, task["suffix_code"], suf_budget)
        prompt = render(tokenizer, content(ctx, pre, suf))
        ids = encode(tokenizer, prompt)
    if len(ids) + generation_limit > window:
        raise ValueError("Final prompt exceeds the configured window")
    return {"prompt": prompt, "prompt_token_ids": ids,
            "prompt_parts": {"context": ctx, "prefix": pre, "suffix": suf},
            "truncation": {"prefix": pre != task["prefix_code"], "suffix": suf != task["suffix_code"],
                           "context_tokens": len(encode(tokenizer, ctx))}}
