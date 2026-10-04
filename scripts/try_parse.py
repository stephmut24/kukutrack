"""Try KukuTrack's local Ollama parser from the command line."""

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from app.services.assistant import AssistantBadOutput, AssistantUnavailable, parse_entry
from app.services.logs import current_utc_date


def main() -> None:
    """Parse one sentence with the configured local Ollama model."""
    parser = argparse.ArgumentParser(description="Teste l'analyse locale Ollama de KukuTrack.")
    parser.add_argument("sentence", help="phrase à analyser")
    arguments = parser.parse_args()
    try:
        entry = parse_entry(arguments.sentence, current_utc_date())
    except AssistantUnavailable:
        print("Ollama est indisponible. Vérifiez qu'il est lancé et que le modèle est installé.")
        return
    except AssistantBadOutput:
        print("La phrase n'a pas pu être comprise. Essayez de préciser les nombres et les unités.")
        return
    print(entry.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
