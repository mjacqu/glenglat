import datetime
from pathlib import Path
import re
import sys
from typing import Optional, Union

import dotenv
import markdown
import pandas as pd
import requests

import glenglat


FAMILY_GIVEN_NAMES = {
  'Lander Van Tricht': 'Van Tricht, Lander',
  '张通 [Zhang Tong]': 'Zhang, Tong',
}
"""
Custom Zenodo name format (family name, given names) for contributors.

If not specified, the last word is assumed to be the family name.
"""

# Load environment variables from .env
ENV = dotenv.dotenv_values(Path(__file__).parent.parent.joinpath('.env'))


# ---- Zenodo metadata ----

def convert_contributor_to_zenodo(person: dict, attribute: str = 'creators') -> dict:
  """Convert Data Package contributor to Zenodo creator or contributor."""
  attributes = ['creators', 'contributors']
  if attribute not in attributes:
    raise ValueError(f'Attribute must be one of {attributes}')
  name = person['title']
  if name in FAMILY_GIVEN_NAMES:
    name = FAMILY_GIVEN_NAMES[name]
  else:
    parts = name.split(' ')
    if len(parts) == 1:
      name = parts[0]
    else:
      name = parts[-1] + ', ' + ' '.join(parts[:-1])
  result = {'name': name}
  if 'path' in person and 'orcid' in person['path']:
    result['orcid'] = person['path'].replace('https://orcid.org/', '')
  if 'organization' in person:
    result['affiliation'] = person['organization']
  if attribute == 'contributors':
    if 'curator' in person['role']:
      result['type'] = 'DataCurator'
    elif 'contributor' in person['role']:
      result['type'] = 'DataCollector'
  return result


def convert_people_to_english_list(people: str) -> str:
  """Convert pipe-delimited people to English list."""
  people = people.split(' | ')
  if len(people) == 1:
    return people[0]
  if len(people) == 2:
    return ' and '.join(people)
  return ', '.join(people[:-1]) + ', and ' + people[-1]


def convert_source_to_reference(source: pd.Series) -> str:
  """Convert source to Zenodo reference."""
  source = source[source.notnull()]
  if 'author' not in source or 'year' not in source or 'title' not in source:
    raise ValueError('Source must have author, year, and title')
  # {authors} ({year}): {title}.
  s = f'{convert_people_to_english_list(source.author)} ({source.year}): {source.title}.'
  # Version {version}. {container_title}. {editors} (editors).
  if 'version' in source:
    s += f' Version {source.version}.'
  if 'container_title' in source:
    s += f' {source.container_title}.'
  if 'editor' in source:
    s += f' {convert_people_to_english_list(source.editor)} (editors).'
  # Volume {volume} ({issue}): {page} | Issue {issue}: {page} | Pages {page}
  if 'volume' in source or 'issue' in source or 'page' in source:
    if 'volume' in source:
      s += f' Volume {source.volume}'
    if 'issue' in source:
      if 'volume' in source:
        s += f' ({source.issue})'
      else:
        s += f' Issue {source.issue}'
    if 'page' in source:
      if 'volume' in source or 'issue' in source:
        s += f': {source.page}'
      else:
        s += f' Pages {source.page}'
    s += '.'
  # {collection_title} {collection_number}. {publisher}. {url}
  if 'collection_title' in source:
    s += f' {source.collection_title}'
    if 'collection_number' in source:
      s += f' {source.collection_number}'
    s += '.'
  if 'publisher' in source:
    s += f' {source.publisher}.'
  if 'url' in source:
    s += f' {source.url}'
  return s


def build_zenodo_description() -> str:
  """Build Zenodo description from readme."""
  readme = glenglat.read_readme()
  # Extract from README.md
  start = '<!-- <for-zenodo> -->'
  end = '<!-- </for-zenodo> -->'
  start_index = readme.index(start) + len(start)
  end_index = readme.index(end)
  description_md = readme[start_index:end_index].strip()
  # Render markdown as html
  description_html = markdown.markdown(description_md)
  # Remove relative links
  # <a href="data"><code>data</code></a> -> <code>data</code>
  pattern = re.compile(r'<a href="([^"]+)">(.*?)</a>')
  for match in pattern.finditer(description_html):
    if match.group(1).startswith('http'):
      continue
    description_html = description_html.replace(match.group(0), match.group(2))
  return description_html


def build_zenodo_metadata() -> dict:
  """Build Zenodo metadata."""
  description = build_zenodo_description()
  package = glenglat.read_metadata()
  dfs = glenglat.read_data()
  # HACK: Convert source to string to facilitate printing as a reference
  dfs['source'] = dfs['source'].astype('string')
  return {
    'upload_type': 'dataset',
    'publication_date': datetime.date.today().isoformat(),
    'title': f"{package['name']}: {package['title']}",
    'version': package['version'],
    'language': 'eng',
    'grants': [
      # Schweizerischer Nationalfonds zur Förderung der wissenschaftlichen Forschung
      {'id': '10.13039/501100001711::184634'}
    ],
    'description': description,
    'keywords': package['keywords'],
    'access_right': 'open',
    'license': 'cc-by-4.0',
    'creators': [
      convert_contributor_to_zenodo(person, attribute='creators')
      for person in package['contributors']
      if 'author' in person['role']
    ],
    'contributors': [
      convert_contributor_to_zenodo(person, attribute='contributors')
      for person in package['contributors']
      if 'author' not in person['role']
    ],
    'dates': [
      {
        'start': dfs['profile']['date_min'].min(),
        'end': dfs['profile']['date_max'].max(),
        'type': 'Collected',
        'description': 'Date range of temperature measurements'
      }
    ],
    # Include sources with identifiers
    'related_identifiers': [
      # Adds 'Is supplement to' and maybe 'External resources: Available in GitHub'
      {
        'relation': 'isSupplementTo',
        'identifier': 'https://github.com/mjacqu/glenglat',
        'resource_type': 'dataset'
      }
    ],
    # References
    'references': [
      convert_source_to_reference(dfs['source'].loc[i])
      for i in dfs['source'].query('type.ne("personal-communication")').index
    ]
  }

