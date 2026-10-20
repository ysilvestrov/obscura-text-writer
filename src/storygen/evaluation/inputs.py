import json
from pathlib import Path

from .models import EvaluationCase


def parse_json(text: str):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Повтор ключа JSON")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("Неприпустиме число JSON")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)


def read_json(path: Path):
    try:
        return parse_json(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Не вдалося прочитати JSON: {path.name}") from exc


def contained_file(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ValueError("Потрібен відносний шлях у каталозі прикладу")
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ValueError("Файл відсутній або виходить за межі прикладу")
    return resolved


def load_case(path: Path) -> EvaluationCase:
    data = read_json(path)
    try:
        for doc in data["documents"]:
            if "path" in doc:
                if "text" in doc:
                    raise ValueError("Документ не може містити і path, і text")
                doc["text"] = contained_file(path.parent, doc.pop("path")).read_text(encoding="utf-8-sig")
        return EvaluationCase.model_validate(data)
    except (OSError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Некоректний маніфест прикладу") from exc
