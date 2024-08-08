from pathlib import Path
import re

import pandas as pd
import pytest

from load import dfs, package, DATA_SUBDIR_REGEX, ROOT


data_subdirs = [path for path in ROOT.joinpath('data').iterdir() if path.is_dir()]
profile_ids = pd.MultiIndex.from_frame(dfs['profile'][['borehole_id', 'id']])
measurement_ids = pd.MultiIndex.from_frame(
  dfs['measurement'][['borehole_id', 'profile_id']]
)


def test_data_files_are_used_and_correctly_named() -> None:
  """Data files are used by the package and named {table}.csv."""
  present = [
    str(path.relative_to(ROOT))
    for path in ROOT.joinpath('data').glob('**/*')
    if path.is_file() and not path.name.startswith('.')
  ]
  invalid = []
  for resource in package.resources:
    for path in resource.paths:
      if not (path in present and Path(path).name == f'{resource.name}.csv'):
        invalid.append(path)
  assert not invalid, invalid


@pytest.mark.parametrize('dir', data_subdirs)
def test_data_subdir_only_contains_profile_and_measurement(dir: Path) -> None:
  """Data subdirectory only contains profile and measurement tables."""
  csvs = {path.stem for path in dir.glob('*.csv')}
  assert csvs == {'profile', 'measurement'}, csvs


@pytest.mark.parametrize('dir', data_subdirs)
def test_data_subdir_contains_unique_profiles(dir: Path) -> None:
  """Data subdirectory only contains profiles not mentioned elsewhere."""
  in_profile = dfs['profile']['__path__'] == str(dir / 'profile.csv')
  in_measurement = dfs['measurement']['__path__'] == str(dir / 'measurement.csv')
  valid = (
    profile_ids[in_profile].isin(measurement_ids[in_measurement]) &
    ~profile_ids[in_profile].isin(profile_ids[~in_profile]) &
    ~profile_ids[in_profile].isin(measurement_ids[~in_measurement])
  )
  assert valid.all(), profile_ids[~valid]


@pytest.mark.parametrize('dir', data_subdirs)
def test_data_subdir_contains_only_profiles_from_named_source(dir: Path) -> None:
  """Data subdirectory only contains profiles from the named source."""
  source_id = dir.name.split('-', maxsplit=1)[0]
  in_profile = dfs['profile']['__path__'] == str(dir.relative_to(ROOT) / 'profile.csv')
  borehole_ids = dfs['profile']['borehole_id'][in_profile].drop_duplicates()
  source_ids = (
    dfs['borehole'].set_index('id')
    .loc[borehole_ids]['source_id']
    .drop_duplicates()
  )
  assert len(source_ids) == 1 and source_ids.iloc[0] == source_id, source_ids


@pytest.mark.parametrize('dir', data_subdirs)
def test_data_subdir_suffix_is_kebab_case(dir: Path) -> None:
  """Data subdirectory suffix is latinized kebab-case."""
  assert re.match(DATA_SUBDIR_REGEX, dir.name), dir.name
