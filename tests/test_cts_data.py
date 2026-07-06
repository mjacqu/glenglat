import numpy as np
import pandas as pd

from load import dfs
import glenglat


def test_survey_id_in_profile_table() -> None:
  """All surveys have at least one profile."""
  df = dfs['cts_survey']
  valid = df['id'].isin(dfs['cts_profile']['cts_survey_id'])
  assert valid.all(), df.loc[~valid, ['id', 'source_id']]


def test_profile_id_in_measurement_table() -> None:
  """All profiles have at least one measurement."""
  df = dfs['cts_profile']
  profiles = pd.MultiIndex.from_frame(
    df[['cts_survey_id', 'id']].rename(columns={'id': 'cts_profile_id'})
  )
  measurements = pd.MultiIndex.from_frame(
    dfs['cts_measurement'][['cts_survey_id', 'cts_profile_id']].drop_duplicates()
  )
  valid = profiles.isin(measurements)
  assert valid.all(), df[~valid]


def test_depth_less_than_bed_depth() -> None:
  """CTS depth is less than bed depth."""
  df = dfs['cts_measurement']
  valid = ~np.isfinite(df['depth']) | (df['depth'] <= df['bed_depth'])
  assert valid.all(), df.loc[~valid, ['cts_survey_id', 'cts_profile_id', 'id', 'depth', 'bed_depth']]


def test_survey_min_profile_id_is_1() -> None:
  """Survey minimum profile ID is 1."""
  min_profile_id = dfs['cts_profile'].groupby('cts_survey_id')['id'].min()
  valid = min_profile_id.eq(1)
  assert valid.all(), min_profile_id[~valid]


def test_survey_profile_ids_increment_by_1() -> None:
  """Survey profile IDs increment by 1."""
  df = dfs['cts_profile']
  db = df['cts_survey_id'].diff()
  dp = df['id'].diff()
  valid = db.ne(0) | dp.eq(1)
  assert valid.all(), df[~valid]


def test_profile_min_measurement_id_is_1() -> None:
  """Profile minimum measurement ID is 1."""
  min_measurement_id = dfs['cts_measurement'].groupby(
    ['cts_survey_id', 'cts_profile_id']
  )['id'].min()
  valid = min_measurement_id.eq(1)
  assert valid.all(), min_measurement_id[~valid]


def test_profile_measurement_ids_increment_by_1() -> None:
  """Profile measurement IDs increment by 1."""
  df = dfs['cts_measurement']
  db = df[['cts_survey_id', 'cts_profile_id']].diff().ne(0).any(axis=1)
  dp = df['id'].diff()
  valid = db | dp.eq(1)
  assert valid.all(), df[~valid]


def test_profile_ids_are_chronological() -> None:
  """Profile ids are chronological within each survey."""
  df = dfs['cts_profile']
  valid = df.groupby('cts_survey_id')['date'].apply(lambda s: s.is_monotonic_increasing)
  assert valid.all(), df[~valid]
