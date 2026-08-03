import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.ollama_client import OllamaClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-live", action="store_true")
    args = parser.parse_args()

    if args.skip_live:
        print("Ollama smoke script imports successfully.")
        return

    client = OllamaClient()
    chat_content = client.chat_json_instruction(
        "Return JSON only. Extract goal_type and duration_weeks.",
        "I want fat loss over 8 weeks.",
    )
    embedding = client.embed("I want fat loss over 8 weeks.")

    print("Ollama chat API responded:")
    print(chat_content)
    print(f"Ollama embedding API responded with vector length: {len(embedding)}")


if __name__ == "__main__":
    main()
