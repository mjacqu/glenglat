import frictionless
import numpy as np
import pandas as pd
import pytest

from load import (
  dfs,
  package,
  TRANSLATED_COLUMNS,
  TRANSLATED_REGEX,
  PEOPLE_COLUMNS
)
import glenglat


@pytest.mark.slow
def test_datapackage_is_valid() -> None:
  """Frictionless datapackage is valid."""
  report = frictionless.validate('datapackage.yaml')
  assert report.valid, report.to_summary()


# ---- source ----

def test_profile_date_min_less_than_date_max() -> None:
  """Profile date range is consistent."""
  df = dfs['profile']
  valid = df['date_min'].le(df['date_max'])
  assert valid.all(), df[~valid]


def test_borehole_date_min_less_than_date_max() -> None:
  """Borehole date range is consistent."""
  df = dfs['borehole']
  valid = df['date_min'].le(df['date_max'])
  assert valid.all(), df.loc[~valid, ['id', 'date_min', 'date_max']]


def test_profile_date_after_borehole_date() -> None:
  """Profile date range is aligned with or after borehole date range."""
  df = dfs['profile'].set_index('borehole_id').join(
    dfs['borehole'].set_index('id')[['date_min', 'date_max']], rsuffix='_b'
  )
  valid = (
    df['date_min'].ge(df['date_min_b']) &
    df['date_max'].ge(df['date_max_b'])
  )
  assert valid.all(), df.loc[~valid, ['id', 'date_min_b', 'date_max_b', 'date_min', 'date_max']]


def test_borehole_id_in_profile_table() -> None:
  """All boreholes have at least one profile."""
  df = dfs['borehole']
  valid = df['id'].isin(dfs['profile']['borehole_id'])
  assert valid.all(), df.loc[~valid, ['id', 'source_id']]


def test_profile_id_in_measurement_table() -> None:
  """All profiles have at least one measurement."""
  df = dfs['profile']
  profiles = pd.MultiIndex.from_frame(
    df[['borehole_id', 'id']].rename(columns={'id': 'profile_id'})
  )
  measurements = pd.MultiIndex.from_frame(
    dfs['measurement'][['borehole_id', 'profile_id']].drop_duplicates()
  )
  valid = profiles.isin(measurements)
  assert valid.all(), df[~valid]


def test_measurement_origin_submitted_only_for_submission() -> None:
  df = dfs['profile'].merge(
    dfs['source'][['id', 'type']].rename(columns={'id': 'source_id'}),
    how='left'
  )
  valid = (
    (
      df['type'].eq('personal-communication') &
      df['measurement_origin'].eq('submitted')
    ) |
    (
      df['type'].ne('personal-communication') &
      df['measurement_origin'].ne('submitted')
    )
  )
  assert valid.all(), df.loc[~valid, ['borehole_id', 'source_id', 'type', 'measurement_origin']]


def test_ice_depth_less_than_borehole_depth() -> None:
  """Ice depth is less than total borehole depth."""
  df = dfs['borehole']
  valid = ~np.isfinite(df['ice_depth']) | (df['ice_depth'] <= df['depth'])
  assert valid.all(), df.loc[~valid, ['id', 'ice_depth', 'depth']]


def test_borehole_max_measurement_depth_is_positive() -> None:
  """Borehole maximum measurement depth is positive."""
  max_depth = dfs['measurement'].groupby('borehole_id')['depth'].max()
  valid = max_depth.gt(0)
  assert valid.all(), max_depth[~valid]


def test_borehole_measurement_depth_less_than_total_depth() -> None:
  """Borehole measurement depth is less than total depth (within tolerance)."""
  EXCEPTIONS = [
    201,  # thompson1995 (Summit core): 16 m core depth vs 17.2 m digitized measurement
    845,  # kronenberg2022b: Original depth 17.75 m increasing to 23.1 m due to snow
  ]
  df = (
    dfs['profile']
    .rename(columns={'id': 'profile_id'})
    .query('~(borehole_id in @EXCEPTIONS)')
    .set_index(['borehole_id', 'profile_id'])
  )
  df['max_depth'] = (
    dfs['measurement']
    .groupby(['borehole_id', 'profile_id'])['depth']
    .max()
  )
  df = df.join(dfs['borehole'].set_index('id')[['depth']], on='borehole_id')
  ratio = df['max_depth'] / df['depth']
  diff = (df['max_depth'] - df['depth']).abs()
  valid = (
    # Within 3% for first profile
    ((df.index.get_level_values('profile_id') == 1) & ratio.lt(1.03)) |
    # Within 16% for subsequent profiles or < 2 m difference
    ((df.index.get_level_values('profile_id') != 1) & (ratio.lt(1.16) | diff.lt(2)))
  )
  assert valid.all(), df.loc[~valid, ['depth', 'max_depth']]


def test_borehole_min_profile_id_is_1() -> None:
  """Borehole minimum profile ID is 1."""
  min_profile_id = dfs['profile'].groupby('borehole_id')['id'].min()
  valid = min_profile_id.eq(1)
  assert valid.all(), min_profile_id[~valid]


def test_borehole_profile_ids_increment_by_1() -> None:
  """Borehole profile IDs increment by 1."""
  EXCEPTIONS = [
    766,  # kronenberg2022: Later single profile from machguth2023 in main tables
  ]
  df = dfs['profile']
  df = df[~df['borehole_id'].isin(EXCEPTIONS)]
  db = df['borehole_id'].diff()
  dp = df['id'].diff()
  valid = db.ne(0) | dp.eq(1)
  assert valid.all(), df[~valid]


@pytest.mark.parametrize('table, column', TRANSLATED_COLUMNS)
def test_translations_have_correct_format(table: str, column: str) -> None:
  """Translated text is formatted as {text} [{translation}]."""
  s = dfs[table].set_index('id')[column]
  valid = s.str.match(TRANSLATED_REGEX)
  assert valid.all(), s[~valid]


@pytest.mark.parametrize('table, column', PEOPLE_COLUMNS)
def test_people_have_correct_format(table: str, column: str) -> None:
  """People are formatted as {text} [{translation}] ({orcid}) | ."""
  s = dfs[table].set_index('id')[column]
  people = s.str.split(' | ', regex=False).explode()
  valid = people.str.match(glenglat.PERSON_REGEX)
  assert valid.all(), s[~valid]


def test_profile_ids_are_chronological() -> None:
  """Borehole profile ids are chronological."""
  EXCEPTIONS = [
    460,  # carturan2023: Borehole with timeseries from two different thermistor chains
    766,  # kronenberg2022: Later single profile from machguth2023 in main tables
  ]
  df = dfs['profile']
  # By date
  groupby = df.groupby('borehole_id')
  valid = (
    groupby['date_min'].apply(lambda s: s.dropna().is_monotonic_increasing) &
    groupby['date_max'].apply(lambda s: s.dropna().is_monotonic_increasing)
  )
  valid.loc[EXCEPTIONS] = True
  assert valid.all(), valid.index[~valid]
  # By datetime
  mask = (
    df['date_min'].notnull() &
    df['date_max'].notnull() &
    df['date_min'].eq(df['date_max']) &
    df['time'].notnull()
  )
  df = df[mask]
  datetime = df['date_min'] + 'T' + df['time']
  valid = datetime.groupby(df['borehole_id']).apply(lambda s: s.is_monotonic_increasing)
  valid.loc[valid.index.intersection(EXCEPTIONS)] = True
  assert valid.all(), valid.index[~valid]


def test_profile_ids_are_chronological_by_datetime() -> None:
  """Borehole profile ids are chronological by datetime."""
  EXCEPTIONS = [
    460,  # carturan2023: Borehole with timeseries from two different thermistor chains
    766,  # kronenberg2022: Later single profile from machguth2023 in main tables
  ]
  df = dfs['profile']
  groupby = df.groupby('borehole_id')
  valid = (
    groupby['date_min'].apply(lambda s: s.dropna().is_monotonic_increasing) &
    groupby['date_max'].apply(lambda s: s.dropna().is_monotonic_increasing)
  )
  valid.loc[EXCEPTIONS] = True
  assert valid.all(), valid.index[~valid]
