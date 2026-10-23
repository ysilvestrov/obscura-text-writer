import pytest
from storygen.billing.pricing import from_catalog
from storygen.providers.accounting import normalize_cost


def test_catalog_units_and_unknown_rates():
    venice = from_catalog('venice', 'm', {'model_spec': {'pricing': {'input': {'usd': 1}, 'output': {'usd': 2}}}})
    router = from_catalog('openrouter', 'm', {'pricing': {'prompt': '0.000001', 'completion': '0.000002', 'request': '0'}})
    assert venice.price(1000, 1000) == router.price(1000, 1000) == 3000000
    with pytest.raises(ValueError): from_catalog('openrouter', 'm', {'pricing': {'prompt': '-1', 'completion': '0'}})


def test_cost_normalization_preserves_actual_and_diem():
    assert normalize_cost('venice', {'usd': '0.001', 'diem': 0}, {}) == ('0.001', '0')
    assert normalize_cost('openrouter', None, {'cost': '0.002'}) == ('0.002', None)
    assert normalize_cost('venice', {'usd': -1, 'diem': 'NaN'}, {}) == (None, None)
