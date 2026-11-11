"""SECURITY-002: state, write and removal of a provider key in the OS store. The value is never returned."""
from fastapi import APIRouter
from pydantic import Field

from ..domain import DomainModel
from ..providers import secrets

router=APIRouter()


class KeyValue(DomainModel):
    # Longer than the stored limit so that surrounding whitespace of a pasted key does not fail the request shape.
    value: str = Field(min_length=1,max_length=secrets.MAX_VALUE+64)


def _state(name: str) -> dict:
    if not secrets.valid_name(name):raise ValueError('Некоректна назва ключа')
    return {'name':name,'source':secrets.key_source(name),'stored':secrets.stored(name),'store_available':secrets.store_available()}


@router.get('/api/provider-keys/{name}')
def get_provider_key(name: str):
    return _state(name)


@router.put('/api/provider-keys/{name}')
def put_provider_key(name: str,body: KeyValue):
    secrets.store_key(name,body.value)
    return _state(name)


@router.delete('/api/provider-keys/{name}')
def delete_provider_key(name: str):
    secrets.delete_key(name)
    return _state(name)
