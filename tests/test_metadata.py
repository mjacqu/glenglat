import pandas as pd

from load import dfs, package
from glenglat import PEOPLE_REGEX, PERSON_REGEX


def test_personal_communication_author_listed_as_contributor() -> None:
  """Personal communication author is listed in data package contributors."""
  df = dfs['source']
  mask = df['type'].eq('personal-communication')
  people = (
    df['author'][mask].str.extract(PEOPLE_REGEX)
    .unstack()
    .droplevel(0, axis='index')
    .dropna()
    .drop_duplicates()
    .str.extract(PERSON_REGEX)
    .reset_index(drop=True)
  )
  people['path'] = 'https://orcid.org/' + people['path']
  contributors = pd.DataFrame([
    person for person in package.contributors
    if 'contributor' in person['role'].split(' | ')
  ])
  # Fill missing ORCID from matching name in contributors
  people = people.merge(
    contributors[['title', 'path']],
    on='title',
    how='left',
    validate='1:1'
  )
  people['path'] = people['path_x'].combine_first(people['path_y'])
  # Compare to contributors
  merge = people[['title', 'path']].reset_index().merge(
    contributors[['title', 'path']].reset_index(),
    on=['title', 'path'],
    how='outer'
  ).convert_dtypes()
  valid = merge['index_x'].notnull() & merge['index_y'].notnull()
  assert valid.all(), merge[~valid]


def test_curator_listed_as_curator() -> None:
  """Curator is listed in data package contributors."""
  df = dfs['borehole']
  people = (
    df['curator'].str.extract(PEOPLE_REGEX)
    .unstack()
    .droplevel(0, axis='index')
    .dropna()
    .drop_duplicates()
    .str.extract(PERSON_REGEX)
    .reset_index(drop=True)
  )
  people['path'] = 'https://orcid.org/' + people['path']
  contributors = pd.DataFrame([
    person for person in package.contributors
    if 'curator' in person['role'].split(' | ')
  ])
  # Fill missing ORCID from matching name in contributors
  people = people.merge(
    contributors[['title', 'path']],
    on='title',
    how='left',
    validate='1:1'
  )
  people['path'] = people['path_x'].combine_first(people['path_y'])
  # Compare to contributors
  merge = people[['title', 'path']].reset_index().merge(
    contributors[['title', 'path']].reset_index(),
    on=['title', 'path'],
    how='outer'
  ).convert_dtypes()
  valid = merge['index_x'].notnull() & merge['index_y'].notnull()
  assert valid.all(), merge[~valid]
