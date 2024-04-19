from pathlib import Path

from load import package


def test_data_files_are_used_and_correctly_named() -> None:
  """Data files are used by the package and named {table}.csv."""
  present = [
    str(path)
    for path in Path('data').glob('**/*')
    if path.is_file() and not path.name.startswith('.')
  ]
  invalid = []
  for resource in package.resources:
    for path in resource.paths:
      if not (path in present and Path(path).name == f'{resource.name}.csv'):
        invalid.append(path)
  assert not invalid, invalid


def test_data_subdirs_only_contain_profile_and_measurement() -> None:
  """Data subdirectories only contain profile and/or measurement tables."""
  invalid = []
  for resource in package.resources:
    for path in resource.paths:
      path = Path(path)
      if (
        path.parent.name != 'data' and
        path.stem not in ['profile', 'measurement']
      ):
        invalid.append(path)
  assert not invalid, invalid
