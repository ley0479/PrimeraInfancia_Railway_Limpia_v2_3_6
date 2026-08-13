from datetime import datetime

from backend.modules.institucional_normativo import _branding_version


def test_branding_version_fits_postgresql_integer_and_is_ordered():
    before = _branding_version(datetime(2026, 8, 11, 0, 59, 0))
    after = _branding_version(datetime(2026, 8, 11, 1, 0, 0))

    assert 0 < before <= 2_147_483_647
    assert after == before + 1
