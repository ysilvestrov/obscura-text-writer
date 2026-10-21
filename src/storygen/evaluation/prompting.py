import json
from importlib.resources import files

from .inputs import parse_json
from .models import EvaluationCase, EvaluationRequest, EvaluatorConfig, JudgeReport, Rubric


def resource_text(name: str) -> str:
    return files("storygen.evaluation").joinpath("resources", name).read_text(encoding="utf-8")


def load_rubric() -> Rubric:
    return Rubric.model_validate(parse_json(resource_text("rubric_v1.json")))


def required_criteria(case: EvaluationCase, rubric: Rubric) -> set[str]:
    return {c.id for c in rubric.criteria if case.mode in c.required_modes} | set(case.required_criteria)


def build_request(case: EvaluationCase, rubric: Rubric, config: EvaluatorConfig, reverse_pair: bool = False) -> EvaluationRequest:
    schema = JudgeReport.model_json_schema()
    def strict(node):
        if isinstance(node, dict):
            node.pop('default', None)
            if 'properties' in node:
                node['required'] = list(node['properties'])
                node['additionalProperties'] = False
            for value in node.values():
                strict(value)
        elif isinstance(node, list):
            for value in node:
                strict(value)
    strict(schema)
    data = case.model_dump()
    data["required_criteria"] = sorted(required_criteria(case, rubric))
    if reverse_pair and case.mode == "revision":
        targets = set(case.target_ids)
        others = [d for d in data["documents"] if d["id"] not in targets]
        ordered = [next(d for d in data["documents"] if d["id"] == key) for key in reversed(case.target_ids)]
        data["documents"] = others + ordered
    data["rubric"] = rubric.model_dump()
    system = resource_text("evaluator_uk_v1.txt")
    if config.response_mode == "prompt_json":
        system += "\nJSON Schema:\n" + json.dumps(schema, ensure_ascii=False)
    return EvaluationRequest(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": json.dumps(data, ensure_ascii=False)}],
        response_schema=schema, response_mode=config.response_mode,
        max_output_tokens=config.max_output_tokens, temperature=config.temperature,
    )
