"""Exact API bodies shared by budgeting, persistence and transport."""
import json


def strict_schema(model):
    schema = model.model_json_schema()
    def normalize(node):
        if isinstance(node, dict):
            node.pop('default', None)
            if 'properties' in node:
                node['required'] = list(node['properties'])
                node['additionalProperties'] = False
            for value in node.values(): normalize(value)
        elif isinstance(node, list):
            for value in node: normalize(value)
    normalize(schema)
    return schema


def venice_options(settings):
    return {'include_venice_system_prompt': settings.venice_include_system_prompt,
        'disable_thinking': settings.venice_disable_thinking, 'enable_web_search': 'off',
        'enable_web_scraping': False, 'enable_x_search': False}


def venice_reasoning(settings):
    if settings.venice_disable_thinking:
        return {'reasoning':{'enabled':False}}
    effort=getattr(settings,'venice_reasoning_effort',None)
    return {'reasoning':{'effort':effort}} if effort else {}


def generation_request(stage, settings, system, user, fragments):
    from ..generation.models import StoryBlueprint, WritersBrief
    from ..memory.models import MemorySnapshot
    from ..memory.journal import MemoryOperations
    from ..generation.copyediting import CopyEdits
    provider = settings.provider
    body = {'model': provider.model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
        'max_tokens': settings.max_output_tokens, 'temperature': settings.temperature, 'stream': True}
    if settings.stop_sequences: body['stop'] = settings.stop_sequences
    if provider.include_usage: body['stream_options'] = {'include_usage': True}
    if provider.provider == 'venice':
        body['venice_parameters'] = venice_options(provider)
        body.update(venice_reasoning(provider))
    structured = stage in {'prepare', 'brief', 'memory','classify','publication_suggest'} or (stage == 'edit' and settings.edit_mode == 'patches')
    if provider.response_mode == 'json_schema' and structured:
        if stage=='publication_suggest':
            from ..publication_suggestions import PublicationSuggestions
            model=PublicationSuggestions
        elif stage=='classify':
            from ..generation.edit_classification import Classification
            model=Classification
        else:
            model = CopyEdits if stage == 'edit' else MemoryOperations if stage == 'memory' and settings.memory_mode == 'evidence_delta' else {'prepare': StoryBlueprint, 'brief': WritersBrief, 'memory': MemorySnapshot}[stage]
        schema = strict_schema(model)
        if stage == 'memory' and settings.memory_mode == 'snapshot' and fragments.get('expected_source_prose_ids'):
            allowed = json.loads(fragments['expected_source_prose_ids'])
            schema['properties']['source_prose_ids'].update({'minItems': len(allowed), 'maxItems': len(allowed), 'items': {'type': 'string', 'enum': allowed}})
            schema['$defs']['MemoryEntry']['properties']['source_version_id']['enum'] = allowed
        body['response_format'] = {'type': 'json_schema', 'json_schema': {'name': stage, 'strict': True, 'schema': schema}}
    return body


def evaluation_request(config, request):
    body = {'model': config.model, 'messages': request.messages, 'max_tokens': request.max_output_tokens}
    if request.temperature is not None: body['temperature'] = request.temperature
    if request.response_mode == 'json_schema':
        body['response_format'] = {'type': 'json_schema', 'json_schema': {'name': 'story_evaluation', 'strict': True, 'schema': request.response_schema}}
        if config.provider == 'openrouter': body['provider'] = {'require_parameters': True}
    if config.provider == 'venice':
        body['venice_parameters'] = venice_options(config)
        body.update(venice_reasoning(config))
    return body


def sdk_arguments(body):
    """The SDK's extra_body becomes these same top-level JSON fields."""
    args = dict(body)
    extra = {key: args.pop(key) for key in ('venice_parameters', 'provider', 'reasoning') if key in args}
    if extra: args['extra_body'] = extra
    return args
