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


def test_author_list_renders() -> None:
  """Author list renders successfully."""
  glenglat.render_author_list()
