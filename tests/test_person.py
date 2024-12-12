import re

import pandas as pd
import pytest

from load import dfs, glenglat


@pytest.mark.parametrize('column', ['titles', 'emails', 'urls'])
def test_list_column_is_unique(column: str) -> None:
  """Values in list column are unique throughout."""
  df = dfs['person']
  values: pd.Series = (
    df[column].str.split(' | ', regex=False)
    .dropna()
    .explode(ignore_index=False)
  )
  duplicated = values.duplicated()
  assert not duplicated.any(), values[duplicated]


def test_family_name_is_once_in_name() -> None:
  """Latin family name is present once in the Latin full name."""
  df = dfs['person']
  valid = df.apply(
    lambda x: (
      len(re.findall(fr"(?: |^){x['latin_family_name']}(?= |$)", x['latin_name'])) == 1
    ),
    axis=1
  )
  assert valid.all(), df.loc[~valid, ['latin_name', 'latin_family_name']]


def test_each_title_contains_family_name_or_is_unambiguous() -> None:
  """Each matching title contains the Latin family name or is unambiguous."""
  df = dfs['person'].copy()
  df['titles'] = df['titles'].str.split(' | ', regex=False)
  df = df.explode('titles')
  valid = df.apply(
    lambda x: (
      len(re.findall(fr"(?: |^|\[){x['latin_family_name']}(?= |$|\])", x['titles'])) == 1
    ),
    axis=1
  )
  # If not matching, check that at least the last name is unambiguous
  df = df[~valid]
  valid = (
    df['titles']
    .apply(glenglat.parse_person_string)
    .apply(
      lambda x: glenglat.infer_name_parts(latin=x['latin'], name=x['name'])
    )
    .notnull()
  )
  assert valid.all(), df.loc[~valid, ['titles', 'latin_family_name']]
