import json
import yaml
import pandas as pd


with open('datapackage.yaml', 'r') as file:
  package = yaml.safe_load(file)

sources = pd.read_csv('data/source.csv')


def convert_contributor_to_zenodo(person: dict, attribute: str = 'creators') -> dict:
  """Convert Data Package contributor to Zenodo creator or contributor."""
  attributes = ['creators', 'contributors']
  if attribute not in attributes:
    raise ValueError(f'Attribute must be one of {attributes}')
  result = {'name': person['title']}
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


# ---- Build zenodo.json ----

zenodo = {
  'upload_type': 'dataset',
  # Title is optional since it is read from the GitHub repository title
  'title': f"{package['name']}: {package['title']}",
  'language': 'eng',
  # Description is optional since it is read from the README.md file
  # 'description': package['description'],
  'keywords': package['keywords'],
  'access_right': 'open',
  # License is optional since it is read from the LICENSE.md file
  # 'license': 'cc-by-4.0',
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
  # Include sources with identifiers
  'related_identifiers': [
    {'identifier': source['url'], 'relation': 'references'}
    for source in sources.to_dict(orient='records')
    if isinstance(source['url'], str)
  ]
}

with open('.zenodo.json', 'w') as file:
  json.dump(zenodo, file, indent=2, ensure_ascii=False)
