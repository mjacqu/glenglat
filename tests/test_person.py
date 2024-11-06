import re

import pandas as pd
import pytest

from load import dfs
from glenglat import PERSON_TITLE_REGEX

df = dfs['person']


@pytest.mark.parametrize('column', ['matches', 'emails', 'urls'])
def test_person_list_column_is_unique(column: str) -> None:
  """Values in list column are unique throughout."""
  values: pd.Series = (
    df[column].str.split(' | ', regex=False)
    .dropna()
    .explode(ignore_index=False)
  )
  duplicated = values.duplicated()
  assert not duplicated.any(), values[duplicated]


def test_person_title_is_valid() -> None:
  """Person title is valid."""
  valid = df['title'].str.fullmatch(PERSON_TITLE_REGEX) | df['title'].isnull()
  assert valid.all(), df['title'][~valid]


def test_person_latin_family_name_is_once_in_title() -> None:
  """Person Latin family name is present and unique in title."""
  names = df['title'].str.extract(PERSON_TITLE_REGEX)
  latin = names['latin'].combine_first(names['name'])
  valid = pd.concat([latin, df['latin_family']], axis=1).apply(
    lambda x: len(re.findall(fr"(?: |^){x['latin_family']}(?: |$)", x['latin'])) == 1,
    axis=1
  )
  assert valid.all(), df.loc[~valid, ['title', 'latin_family']]
