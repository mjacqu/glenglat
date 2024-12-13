import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
  parser.addoption('--fast', action='store_true', default=False, help='Skip slow tests')


def pytest_configure(config: pytest.Config) -> None:
  config.addinivalue_line('markers', 'slow: Mark test as slow')


def pytest_collection_modifyitems(
  config: pytest.Config,
  items: list[pytest.Item]
) -> None:
  if config.getoption('--fast'):
    skip_slow = pytest.mark.skip(reason='--fast skips slow tests')
    for item in items:
      if 'slow' in item.keywords:
        item.add_marker(skip_slow)
