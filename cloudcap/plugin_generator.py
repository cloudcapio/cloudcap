import re
import anthropic
from cloudcap.prompt_builder import build

MODEL = "claude-opus-4-7"


def generate(resource_type: str) -> str:
    prompt = build(resource_type)
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    text_block = next(b for b in message.content if isinstance(b, anthropic.types.TextBlock))
    return _extract_code(text_block.text)


def _extract_code(text: str) -> str:
    match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
    if not match:
        raise ValueError("No Python code block found in LLM response")
    return match.group(1).strip()
