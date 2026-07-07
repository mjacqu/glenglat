import pandas as pd
import pytest

from load import dfs, glenglat, package


def test_personal_communication_author_listed_as_contributor() -> None:
  """Personal communication author is listed in data package contributors."""
  df = dfs['source']
  mask = df['type'].eq('personal-communication')
  strings = df['author'][mask].str.split(' | ', regex=False).explode().drop_duplicates()
  parsed = [glenglat.parse_person_string(string) for string in strings]
  people = pd.DataFrame({
    'title': [person['title'] for person in parsed],
    'path': [person['orcid'] for person in parsed]
  })
  contributors = pd.DataFrame([
    person for person in package.contributors
    if person['role'] == 'DataCollector'
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
  people_dfs = [
    (
      dfs[table]['curator'].str.split(' | ', regex=False)
      .explode()
      .drop_duplicates()
      .str.extract(glenglat.PERSON_REGEX)
      .reset_index(drop=True)
    )
    for table in ['borehole', 'cts_survey']
  ]
  people = pd.concat(people_dfs, ignore_index=True).drop_duplicates()
  people['path'] = 'https://orcid.org/' + people['orcid']
  contributors = pd.DataFrame([
    person for person in package.contributors
    if person['role'] in ('ProjectLeader', 'DataCurator')
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


@pytest.mark.parametrize('table, column', glenglat.FUNDING_COLUMNS.items())
def test_funding_has_correct_format(table: str, column: str) -> None:
  """Funding strings are in the correct format."""
  df = dfs[table][column]
  funding = (
    df.str.split(' | ', regex=False)
    .explode()
    .dropna()
    .drop_duplicates()
  )
  valid = funding.str.fullmatch(glenglat.FUNDING_REGEX)
  assert valid.all(), funding[~valid].to_list()


@pytest.mark.parametrize('table, column', glenglat.INVESTIGATOR_COLUMNS.items())
def test_investigators_have_correct_format(table: str, column: str) -> None:
  """Investigator strings are in the correct format."""
  df = dfs[table][column]
  investigators = (
    df.str.split(' | ', regex=False)
    .explode()
    .dropna()
    .drop_duplicates()
  )
  valid = investigators.str.fullmatch(glenglat.INVESTIGATOR_REGEX)
  assert valid.all(), investigators[~valid].to_list()


@pytest.mark.parametrize('table, column', glenglat.AGENCY_COLUMNS.items())
def test_agencies_have_correct_format(table: str, column: str) -> None:
  """Agency strings are in the correct format."""
  df = dfs[table][column]
  agencies = (
    df.str.split(' | ', regex=False)
    .explode()
    .dropna()
    .drop_duplicates()
  )
  valid = agencies.str.fullmatch(glenglat.AGENCY_REGEX)
  assert valid.all(), agencies[~valid].to_list()


def test_all_authors_and_editors_are_parseable() -> None:
  """All author and editor strings are fully parseable."""
  strings = (
    set(dfs['source']['author'].str.split(' | ', regex=False).explode().dropna()) |
    set(dfs['source']['editor'].str.split(' | ', regex=False).explode().dropna())
  )
  errors = []
  for string in strings:
    try:
      glenglat.parse_person_string(string)
    except ValueError as error:
      errors.append(error)
  assert not errors, errors


def test_csl_renders() -> None:
  """CSL renders successfully."""
  glenglat.render_sources_as_csl(non_latin='literal')
  glenglat.render_sources_as_csl(non_latin='given')

