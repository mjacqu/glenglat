import datetime
import json
import os
from pathlib import Path
import re
from typing import Dict, Optional, Tuple, Union
import zipfile

import dotenv
import fire
import git
import markdown
import pandas as pd
import requests

import glenglat


ROOT = Path(__file__).parent
"""Path to repository root."""

DATA_PATH = ROOT.joinpath('data')
"""Path to data directory."""

BUILD_PATH = ROOT.joinpath('build')
"""Path to build directory."""

REPO = git.Repo(ROOT)
"""Git repository."""

FAMILY_GIVEN_NAMES = {
  'Lander Van Tricht': 'Van Tricht, Lander',
  '张通 [Zhang Tong]': 'Zhang, Tong',
}
"""
Custom Zenodo name format (family name, given names) for contributors.

If not specified, the last word is assumed to be the family name.
"""

# Load environment variables from .env
dotenv.load_dotenv(ROOT.joinpath('.env'))


# ---- Helpers ----

def strip_internal_links_from_markdown(md: str) -> str:
  """
  Strip internal links (defined as non-http) from markdown.

  Example:
    >>> strip_internal_links_from_markdown(
    ...   '[internal](path), [`internal`](path), and [external](https://example.com)'
    ... )
    'internal, `internal`, and [external](https://example.com)'
  """
  pattern = re.compile(r'\[(?P<label>[^\]]+)\]\((?P<url>[^)]+)\)')
  for match in pattern.finditer(md):
    groups = match.groupdict()
    if not re.match('^https?:', groups['url'], re.IGNORECASE):
      md = md.replace(match.group(0), groups['label'])
  return md


def flatten_field_description(text: str) -> str:
  r"""
  Flatten multiline field description for use in markdown table.

  Example:
    >>> flatten_field_description('Title:\n\n- item: value\n- item: value\n\nText.')
    'Title: <br><br> - item: value <br> - item: value <br><br> Text.'
  """
  pattern = re.compile(r'(\n+)')
  for match in pattern.finditer(text):
    n = len(match.group(0))
    text = text.replace(match.group(0), ' ' + '<br>' * n + ' ')
  return text


def render_json(data: dict) -> str:
  """Render dictionary as JSON string."""
  return json.dumps(
    data,
    ensure_ascii=False,
    indent=2,
    sort_keys=False
  )


def get_measurement_interval(
  dfs: Optional[Dict[str, pd.DataFrame]] = None
) -> Tuple[str, str]:
  """Get measurement interval from data."""
  dfs = dfs or glenglat.read_data()
  start = dfs['profile']['date_min'].min()
  end = dfs['profile']['date_max'].max()
  return start, end


# ---- Readme ----

def extract_readme_introduction() -> str:
  """Extract introduction from readme."""
  readme = glenglat.read_readme()
  # Extract from README.md
  start = '<!-- <for-zenodo> -->'
  end = '<!-- </for-zenodo> -->'
  start_index = readme.index(start) + len(start)
  end_index = readme.index(end)
  text = readme[start_index:end_index].strip()
  # Strip internal links
  text = strip_internal_links_from_markdown(text)
  # Replace 'datapackage.yaml' with 'datapackage.json'
  text = text.replace('datapackage.yaml', 'datapackage.json')
  return text


def render_zenodo_description() -> str:
  """Render Zenodo description as html."""
  md = glenglat.render_template(
    ROOT.joinpath('templates/zenodo-description.md.jinja'),
    {
      'introduction': extract_readme_introduction(),
      'package': glenglat.read_metadata()
    }
  )
  return markdown.markdown(md, extensions=['tables'])


def build_zenodo_readme(
  doi: Optional[str] = None, time: Optional[datetime.datetime] = None
) -> Path:
  """Write Zenodo readme as `build/README.md`."""
  metadata = glenglat.read_metadata()
  time = time or datetime.datetime.now(datetime.timezone.utc)
  doi = doi or metadata['id']
  # Render description with flattened field descriptions
  for resource in metadata['resources']:
    for field in resource['schema']['fields']:
      field['description'] = flatten_field_description(field['description'])
  description = glenglat.render_template(
    ROOT.joinpath('templates/zenodo-description.md.jinja'),
    {
      'introduction': extract_readme_introduction(),
      'package': metadata
    }
  )
  text = glenglat.render_template(
    ROOT.joinpath('templates/zenodo-readme.md.jinja'),
    {
      'description': description,
      'version': metadata['version'],
      'date': time.strftime('%Y-%m-%d'),
      'doi': doi
    }
  )
  path = BUILD_PATH.joinpath('README.md')
  path.parent.mkdir(exist_ok=True)
  path.write_text(text)
  return path


def build_metadata_as_json(
  doi: Optional[str] = None, time: Optional[datetime.datetime] = None
) -> Path:
  """Write package metadata to `build/datapackage.json`."""
  if time:
    if not time.tzinfo:
      raise ValueError('time must be timezone-aware')
    time = time.astimezone(datetime.timezone.utc)
  else:
    time = datetime.datetime.now(datetime.timezone.utc)
  metadata = glenglat.read_metadata()
  if doi:
    metadata['id'] = doi
  metadata['created'] = time.strftime('%Y-%m-%dT%H:%M:%SZ')
  start_date, end_date = get_measurement_interval()
  metadata['temporalCoverage'] = f'{start_date}/{end_date}'
  path = BUILD_PATH.joinpath('datapackage.json')
  path.write_text(render_json(metadata))
  return path


# ---- Data ----

def build_for_zenodo(
  doi: Optional[str] = None, time: Optional[datetime.datetime] = None
) -> Path:
  """
  Write a zip archive of glenglat data as `build/glenglat-v{version}.zip`.

  The zip archive is extracted to `build/glenglat-v{version}` for review.

  Args:
    doi: DOI of the Zenodo deposition. If not provided, defaults to the concept DOI.
    time: Time of the build. If not provided, defaults to the current time.

  Returns:
    Path to the zip archive.
  """
  BUILD_PATH.mkdir(exist_ok=True)
  # List files to include
  time = time or datetime.datetime.now(datetime.timezone.utc)
  built_files = [
    build_zenodo_readme(doi=doi, time=time),
    build_metadata_as_json(doi=doi, time=time),
  ]
  unchanged_files = [
    ROOT.joinpath('LICENSE.md'),
    *sorted(DATA_PATH.rglob('*.csv'))
  ]
  # Build zip archive
  metadata = glenglat.read_metadata()
  version = metadata['version']
  path = BUILD_PATH.joinpath(f'glenglat-v{version}.zip')
  with zipfile.ZipFile(path, 'w') as zip:
    for file in built_files:
      zip.write(filename=file, arcname=file.relative_to(BUILD_PATH))
    for file in unchanged_files:
      zip.write(filename=file, arcname=file.relative_to(ROOT))
    # Extract files for review
    zip.extractall(path=BUILD_PATH.joinpath(f'glenglat-v{version}'))
  return path


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


def render_zenodo_metadata(time: Optional[datetime.datetime] = None) -> dict:
  """Render Zenodo metadata."""
  time = time or datetime.datetime.now(datetime.timezone.utc)
  description = render_zenodo_description()
  package = glenglat.read_metadata()
  dfs = glenglat.read_data()
  start_date, end_date = get_measurement_interval(dfs)
  # HACK: Convert source to string to facilitate printing as a reference
  dfs['source'] = dfs['source'].astype('string')
  return {
    'upload_type': 'dataset',
    'publication_date': time.strftime('%Y-%m-%d'),
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
        'start': start_date,
        'end': end_date,
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


# ---- Zenodo API ----

def build_base_url(sandbox: bool = True) -> str:
  """Build base Zenodo API URL."""
  subdomain = 'sandbox.' if sandbox else ''
  return f'https://{subdomain}zenodo.org/api/deposit/depositions'


def is_sandbox(url: str) -> bool:
  """Check if URL is for the Zenodo Sandbox API."""
  return 'sandbox.zenodo' in url


def get_access_token(sandbox: bool = True) -> str:
  """Get Zenodo access token."""
  if sandbox:
    if 'ZENODO_SANDBOX_ACCESS_TOKEN' not in os.environ:
      raise ValueError('Missing ZENODO_SANDBOX_ACCESS_TOKEN in .env')
    return os.environ['ZENODO_SANDBOX_ACCESS_TOKEN']
  if 'ZENODO_ACCESS_TOKEN' not in os.environ:
    raise ValueError('Missing ZENODO_ACCESS_TOKEN in .env')
  return os.environ['ZENODO_ACCESS_TOKEN']


def raise_error(response: requests.Response) -> None:
  """Raise an exception if the response is an error."""
  if response.status_code < 400:
    return None
  content = response.json()
  error = f'Error {response.status_code}'
  if 'message' in content:
    # Standard error response.
    error = f"{error}: {content['message']}"
    if 'errors' in content:
      error = f"{error}\n{content['errors']}"
  else:
    # Unexpected response. Raise the entire content.
    error = f'{error}: {content}'
  raise Exception(error)


def create_deposition(metadata: dict = {}, sandbox: bool = True) -> dict:
  """Create a deposition."""
  response = requests.post(
    url=build_base_url(sandbox=sandbox),
    json={'metadata': metadata},
    params={'access_token': get_access_token(sandbox=sandbox)},
  )
  raise_error(response)
  return response.json()


def find_deposition(
  q: str = 'glenglat',
  sort: str = 'mostrecent',
  all_versions: bool = False,
  sandbox: bool = True
) -> Optional[dict]:
  """
  Find a deposition.

  Returns:
    Deposition, if one was found.

  Raises:
    Exception: Multiple depositions found.
  """
  response = requests.get(
    url=build_base_url(sandbox=sandbox),
    params={
      'access_token': get_access_token(sandbox=sandbox),
      'q': q,
      'sort': sort,
      'all_versions': str(all_versions).lower(),
    },
  )
  raise_error(response)
  depositions = response.json()
  if len(depositions) > 1:
    link_text = '\n'.join(deposition['links']['html'] for deposition in depositions)
    raise Exception(f'Multiple depositions found:\n{link_text}')
  return depositions[0] if depositions else None


def create_new_deposition_version(deposition: dict) -> dict:
  """Create a new version of a deposition."""
  url = deposition['links']['newversion']
  response = requests.post(
    url=url,
    params={'access_token': get_access_token(sandbox=is_sandbox(url))}
  )
  raise_error(response)
  deposition = response.json()
  new_version_url = deposition['links']['latest_draft']
  return get_deposition(new_version_url)


def get_deposition(url: str) -> dict:
  """Get a deposition."""
  response = requests.get(
    url=url,
    params={'access_token': get_access_token(sandbox=is_sandbox(url))}
  )
  raise_error(response)
  return response.json()


def raise_error_if_submitted(deposition: dict) -> None:
  """Raise an exception if the deposition is submitted."""
  if deposition['submitted']:
    raise Exception('Cannot edit a submitted deposition')


def clear_deposition(deposition: dict) -> dict:
  """Clear deposition files and metadata."""
  raise_error_if_submitted(deposition)
  # List files
  url = f"{deposition['links']['latest_draft']}/files"
  access_token = get_access_token(sandbox=is_sandbox(url))
  response = requests.get(url=url, params={'access_token': access_token})
  raise_error(response)
  files = response.json()
  # Delete files
  for file in files:
    response = requests.delete(
      url=file['links']['self'],
      params={'access_token': access_token}
    )
    raise_error(response)
  # Clear metadata
  return edit_deposition(deposition, metadata={})


def edit_deposition(deposition: dict, metadata: dict) -> dict:
  """Edit deposition metadata."""
  raise_error_if_submitted(deposition)
  url = deposition['links']['latest_draft']
  response = requests.put(
    url=url,
    json={'metadata': metadata},
    params={'access_token': get_access_token(sandbox=is_sandbox(url))}
  )
  raise_error(response)
  return response.json()


def add_file_to_deposition(
  deposition: dict, path: Union[Path, str], filename: str = None
) -> dict:
  """Add a file to a deposition."""
  raise_error_if_submitted(deposition)
  filename = filename or Path(path).name
  url = f"{deposition['links']['bucket']}/{filename}"
  with open(path, 'rb') as file:
    response = requests.put(
      url=url,
      data=file,
      params={'access_token': get_access_token(sandbox=is_sandbox(url))},
    )
  raise_error(response)
  return response.json()


def is_repo_publishable() -> Tuple[str, str]:
  """
  Whether repository can be published.

  Returns the current publishable commit hash and tag,
  or raises an exception if the repository cannot be published.
  """
  branch = REPO.active_branch.name
  # Main branch
  if branch != 'main':
    raise Exception(
      f'Repository is on branch {branch}. Publishing requires the main branch.'
    )
  # Clean repo
  if REPO.is_dirty():
    raise Exception(
      'Repository has uncommitted changes. Publishing requires a clean state.'
    )
  # All tests pass (pytest)
  print('Running: pytest')
  if os.system('pytest') != 0:
    raise Exception('Pytest tests failed. Publishing requires passing tests.')
  print('Running: frictionless validate datapackage.yaml')
  if os.system('frictionless validate datapackage.yaml') != 0:
    raise Exception(
      'Frictionless tests failed. Publishing requires passing tests.'
    )
  # Tag is not already in use
  REPO.remotes['origin'].fetch()
  tag = 'v' + glenglat.read_metadata()['version']
  existing_tags = [repo_tag for repo_tag in REPO.tags if repo_tag.name == tag]
  if existing_tags:
    commit = existing_tags[0].commit
    raise Exception(f'Tag {tag} is already in use (commit: {commit}).')
  return REPO.head.commit, tag


def publish_to_zenodo(sandbox: bool = True) -> None:
  """
  Publish glenglat as a Zenodo deposition.

  Builds glenglat for release,
  creates a new deposition (or a new version if one already exists),
  and adds the release to the deposition.

  Args:
    sandbox: Use the Zenodo Sandbox rather than the production Zenodo.
  """
  # Render metadata
  time = datetime.datetime.now(datetime.timezone.utc)
  metadata = render_zenodo_metadata(time=time)
  version = metadata['version']
  # Check repository
  if not sandbox:
    commit, tag = is_repo_publishable()
    print(f'Publishing commit {commit} as {tag}.')
  # Create deposition
  deposition = find_deposition(q='glenglat', all_versions=False, sandbox=sandbox)
  if not deposition:
    print('No existing depositions found. A new one will be created.')
    deposition = create_deposition(sandbox=sandbox)
  else:
    zenodo_version = deposition['metadata']['version']
    if deposition['submitted']:
      if version == zenodo_version:
        raise Exception(
          f"Deposition for v{version} already submitted: {deposition['links']['html']}"
        )
      print(
        f'Found a submitted deposition for v{zenodo_version}.',
        f'A draft for v{version} will be created.'
      )
      deposition = create_new_deposition_version(deposition)
    else:
      print('Found an existing draft deposition.', 'It will be reused.')
    deposition = clear_deposition(deposition)
  # Update deposition metadata
  deposition = edit_deposition(deposition, metadata=metadata)
  # Build and submit data
  doi = 'https://doi.org/' + deposition['metadata']['prereserve_doi']['doi']
  data_path = build_for_zenodo(doi=doi, time=time)
  add_file_to_deposition(deposition, path=data_path, filename=data_path.name)
  print(
    f'Draft deposition for version {version} ready for review:',
    deposition['links']['latest_draft_html']
  )
  if not sandbox:
    print(
      f'If deposition is published, make sure to tag and push this commit:',
      f'git tag {tag} {commit}',
      'git push',
      f'git push origin {tag}',
      sep='\n'
    )


# Generate command line interface
if __name__ == '__main__':
  fire.Fire()
