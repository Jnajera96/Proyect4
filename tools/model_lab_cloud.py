"""Optional cloud GPU experiment. No imports from installed application runtime.

Load only in a separately provisioned GPU notebook. No remote custom Python code
and no automatic acceptance of gated model licenses.
"""

from __future__ import annotations

import json
import re
import time

from tools.model_lab import GateRequired
from tools.model_lab_cases import CASES, task_success


def benchmark_cloud(model_id: str, revision: str, *, max_download_bytes: int = 2_000_000_000):
    """Run role cases on GPU/CPU with pinned Hub revision and a download-size gate.

    torch, transformers and huggingface_hub belong to the cloud notebook environment,
    never to the Windows application's required dependencies.
    """
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("pin a full Hub commit SHA before downloading weights")
    import torch
    from huggingface_hub import HfApi
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

    info = HfApi().model_info(model_id, revision=revision, files_metadata=True)
    weights = [s for s in (info.siblings or []) if s.rfilename.endswith(".safetensors")]
    if not weights or any(s.size is None for s in weights):
        raise GateRequired("cannot establish safetensors download size")
    if sum(s.size for s in weights) > max_download_bytes:
        raise GateRequired("weight download exceeds the configured size gate")
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, revision=revision, trust_remote_code=False, use_safetensors=True
    )
    generator = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        device=0 if torch.cuda.is_available() else -1,
    )
    rows = []
    for case in CASES:
        messages = [
            {
                "role": "system",
                "content": "Return only JSON matching this schema: "
                + json.dumps(case.schema.model_json_schema()),
            },
            {"role": "user", "content": case.prompt},
        ]
        started = time.perf_counter()
        generated = generator(
            messages, max_new_tokens=512, do_sample=False, return_full_text=False
        )[0]["generated_text"]
        if isinstance(generated, list):
            generated = generated[-1]["content"]
        valid, success = False, False
        try:
            parsed = case.schema.model_validate_json(generated)
            valid, success = True, task_success(case, parsed)
        except ValueError:
            pass
        rows.append(
            {
                "model_id": model_id,
                "revision": revision,
                "role": case.role,
                "case_id": case.case_id,
                "schema_valid": valid,
                "task_success": success,
                "latency_ms": (time.perf_counter() - started) * 1000,
                "device": "cuda" if torch.cuda.is_available() else "cpu",
                "input_tokens": len(tokenizer.apply_chat_template(messages)),
                "output_tokens": len(tokenizer.encode(generated, add_special_tokens=False)),
                "cost_usd": None,
                "cost_basis": "cloud hardware billing not observed",
            }
        )
    return rows
