import pandas as pd
import pytest

from load import dfs


def test_source_sorted_by_id() -> None:
  """Sources are sorted by ascending id."""
  df = dfs['source']
  valid = df['id'].index == df['id'].sort_values().index
  assert valid.all(), df.loc[~valid, ['id']]


def test_borehole_sorted_by_id() -> None:
  """Boreholes are sorted by ascending id."""
  df = dfs['borehole']
  valid = df['id'].index == df['id'].sort_values().index
  assert valid.all(), df.loc[~valid, ['id']]


@pytest.mark.parametrize(
  'path',
  dfs['profile']['__path__'].drop_duplicates().to_list()
)
def test_profile_sorted_by_ids(path: str) -> None:
  """Profiles (in each file) are sorted by ascending borehole and profile id."""
  mask = dfs['profile']['__path__'].eq(path)
  df = dfs['profile'][mask]
  index = pd.MultiIndex.from_frame(df[['borehole_id', 'id']])
  valid = index == index.sort_values()
  assert valid.all(), df[~valid]


@pytest.mark.parametrize(
  'path',
  dfs['measurement']['__path__'].drop_duplicates().to_list()
)
def test_measurement_sorted_by_ids(path: str) -> None:
  """Measurements (in each file) are sorted by ascending borehole and profile id."""
  mask = dfs['measurement']['__path__'].eq(path)
  df = dfs['measurement'][mask]
  index = pd.MultiIndex.from_frame(df[['borehole_id', 'profile_id']])
  valid = index == index.sort_values()
  assert valid.all(), df.loc[~valid, ['borehole_id', 'profile_id']].drop_duplicates()


@pytest.mark.parametrize(
  'path',
  dfs['measurement']['__path__'].drop_duplicates().to_list()
)
def test_measurement_sorted_by_ids_and_depth(path: str) -> None:
  """Measurements (in each file) are sorted by ascending ids and depth."""
  mask = dfs['measurement']['__path__'].eq(path)
  df = dfs['measurement'][mask]
  index = pd.MultiIndex.from_frame(df[['borehole_id', 'profile_id', 'depth']])
  valid = index == index.sort_values()
  assert valid.all(), df.loc[~valid, ['borehole_id', 'profile_id']].drop_duplicates()



def test_cts_survey_sorted_by_id() -> None:
  """CTS surveys are sorted by ascending id."""
  df = dfs['cts_survey']
  valid = df['id'].index == df['id'].sort_values().index
  assert valid.all(), df.loc[~valid, ['id']]


@pytest.mark.parametrize(
  'path',
  dfs['cts_profile']['__path__'].drop_duplicates().to_list()
)
def test_cts_profile_sorted_by_ids(path: str) -> None:
  """CTS profiles (in each file) are sorted by ascending survey and profile id."""
  mask = dfs['cts_profile']['__path__'].eq(path)
  df = dfs['cts_profile'][mask]
  index = pd.MultiIndex.from_frame(df[['cts_survey_id', 'id']])
  valid = index == index.sort_values()
  assert valid.all(), df[~valid]


@pytest.mark.parametrize(
  'path',
  dfs['cts_measurement']['__path__'].drop_duplicates().to_list()
)
def test_cts_measurement_sorted_by_ids(path: str) -> None:
  """CTS measurements (in each file) are sorted by ascending survey and profile id."""
  mask = dfs['cts_measurement']['__path__'].eq(path)
  df = dfs['cts_measurement'][mask]
  index = pd.MultiIndex.from_frame(df[['cts_survey_id', 'cts_profile_id']])
  valid = index == index.sort_values()
  assert valid.all(), df.loc[~valid, ['cts_survey_id', 'cts_profile_id']].drop_duplicates()
