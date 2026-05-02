"""Quick diagnostic — run one benchmark item and print exactly what comes back."""
import os, sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

key = os.environ.get("ANTHROPIC_API_KEY","")
if not key:
    print("ANTHROPIC_API_KEY not set"); sys.exit(1)

try:
    import anthropic
except ImportError:
    print("anthropic package not installed — run: pip install anthropic"); sys.exit(1)

client = anthropic.Anthropic(api_key=key)

# Load first item
items_path = Path(__file__).parent / "items.jsonl"
if not items_path.exists():
    print(f"items.jsonl not found at {items_path}"); sys.exit(1)

item = json.loads(items_path.read_text().splitlines()[0])
print(f"Testing item: {item['id']}  ({item['domain']}, answer_kind={item['answer_kind']})")
print(f"Prompt: {item['prompt']}")
print(f"Ground truth: {item['ground_truth']!r}")
print()

try:
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=64,
        system=(
            "You are answering benchmark questions. Follow the format requested in "
            "each prompt exactly: a single word for yes/no questions, or a single "
            "decimal number for numeric questions. Do not add explanation."
        ),
        messages=[{"role": "user", "content": item["prompt"]}],
    )
    reply = resp.content[0].text.strip()
    print(f"Model reply: {reply!r}")
    print(f"Stop reason: {resp.stop_reason}")
    print(f"Usage: input={resp.usage.input_tokens} output={resp.usage.output_tokens} tokens")
    first_word = reply.strip().split()[0] if reply.strip() else ""
    import re
    parsed = re.sub(r"[^a-z]", "", first_word.lower())
    want = str(item["ground_truth"]).lower()
    print(f"\nParsed answer: {parsed!r}  want: {want!r}  match: {parsed == want}")
except Exception as e:
    print(f"API error type: {type(e).__name__}")
    print(f"Full error: {e}")
    if hasattr(e, 'status_code'):
        print(f"Status code: {e.status_code}")
    if hasattr(e, 'body'):
        print(f"Body: {e.body}")
    if hasattr(e, 'message'):
        print(f"Message: {e.message}")
