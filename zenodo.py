import datetime
import json
import os
from pathlib import Path
import re
import shutil
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

# Load environment variables from .env
dotenv.load_dotenv(ROOT.joinpath('.env'))


# ---- Helpers ----

def read_metadata_for_zenodo() -> dict:
  """Read package metadata for Zenodo."""
  dfs = glenglat.read_data()
  package = glenglat.read_metadata()
  # Limit to select tables
  package['resources'] = [
    resource for resource in package['resources']
    if resource['name'] in ('source', 'borehole', 'profile', 'measurement')
  ]
  # Extract funding from borehole table
  if 'funding' in package:
    raise ValueError('Funding already present in package metadata')
  package['funding'] = (
    dfs['borehole']['funding']
    .dropna()
    .str.split(' | ', regex=False)
    .explode()
    .drop_duplicates()
    .str.extract(glenglat.FUNDING_REGEX)
    .convert_dtypes()
    .replace({pd.NA: None})
    .to_dict(orient='records')
  )
  return package


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
      'package': read_metadata_for_zenodo()
    }
  )
  return markdown.markdown(md, extensions=['tables'])


def build_zenodo_readme(
  doi: Optional[str] = None, time: Optional[datetime.datetime] = None
) -> Path:
  """Write Zenodo readme as `build/README.md`."""
  metadata = read_metadata_for_zenodo()
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
  metadata = read_metadata_for_zenodo()
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
  metadata = read_metadata_for_zenodo()
  # Extract data file paths from metadata
  data_paths = []
  for resource in metadata['resources']:
    if isinstance(resource['path'], str):
      data_paths.append(resource['path'])
    else:
      data_paths.extend(resource['path'])
  # List files to include
  time = time or datetime.datetime.now(datetime.timezone.utc)
  built_files = [
    build_zenodo_readme(doi=doi, time=time),
    build_metadata_as_json(doi=doi, time=time),
  ]
  unchanged_files = [
    ROOT.joinpath('LICENSE.md'),
    *sorted([ROOT.joinpath(path) for path in data_paths])
  ]
  # Build zip archive
  version = metadata['version']
  path = BUILD_PATH.joinpath(f'glenglat-v{version}.zip')
  with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as zip:
    for file in built_files:
      zip.write(filename=file, arcname=file.relative_to(BUILD_PATH))
    for file in unchanged_files:
      zip.write(filename=file, arcname=file.relative_to(ROOT))
    # Extract files for review, cleaning up any existing directory
    extract_path = BUILD_PATH.joinpath(f'glenglat-v{version}')
    if extract_path.exists():
      shutil.rmtree(extract_path)
    zip.extractall(path=extract_path)
  return path


# ---- Zenodo metadata ----

def convert_contributor_to_zenodo(person: dict) -> dict:
  """Convert Data Package contributor to Zenodo creator or contributor."""
  # https://inveniordm.docs.cern.ch/reference/metadata/#creators-1-n
  found = glenglat.find_person(title=person['title'], orcid=person.get('path'))
  if not found:
    raise ValueError(f"Contributor '{person['title']}' not found in person table")
  return {
    'person_or_org': {
      'type': 'personal',
      'given_name': found['latin']['given'],
      'family_name': found['latin']['family'],
      'identifiers': [] if 'path' not in person else [
        {
          'scheme': 'orcid',
          'identifier': person['path'].replace('https://orcid.org/', '')
        }
      ]
    },
    'role': {'id': person['role'].lower()},
    'affiliations': [
      {
        'name': agency['name'],
        **({'id': agency['rorid']} if 'rorid' in agency else {})
      }
      for agency in person.get('affiliations', [])
    ]
  }


def convert_source_to_reference(source: dict) -> dict:
  """Convert source to Zenodo reference."""
  result = {'reference': glenglat.render_source_as_reference(source)}
  if source.get('url'):
    if source['url'].startswith('https://doi.org/'):
      result['scheme'] = 'doi'
      result['identifier'] = source['url'].replace('https://doi.org/', '')
    else:
      result['scheme'] = 'url'
      result['identifier'] = source['url']
  return result


def convert_funding_to_zenodo(funding: dict) -> dict:
  """Convert funding to Zenodo funding."""
  # https://inveniordm.docs.cern.ch/reference/metadata/#funding-references-0-n
  result = {'funder': {'name': funding['funder']}}
  if 'rorid' in funding and funding['rorid']:
    result['funder']['id'] = funding['rorid']
  if any(key in funding and funding[key] for key in ('award', 'number', 'url')):
    result['award'] = {}
  if 'award' in funding and funding['award']:
    # HACK: Language codes other than 'en' (at least 'da') result in error
    result['award'] = {'title': {'en': funding['award']}}
  if 'number' in funding and funding['number']:
    if '::' in funding['number']:
      # Award number in OpenAIRE format (rorid::number)
      result['award']['id'] = funding['number']
    else:
      result['award']['number'] = funding['number']
  if 'url' in funding and funding['url']:
    result['award']['identifiers'] = [{'scheme': 'url', 'identifier': funding['url']}]
  if 'award' in result:
    if 'title' not in result['award'] and 'number' in result['award']:
      # HACK: Award title is required to display number
      result['award']['title'] = {'en': result['award']['number']}
      del result['award']['number']
  return result


def render_zenodo_metadata(time: Optional[datetime.datetime] = None) -> dict:
  """Render Zenodo metadata."""
  # https://inveniordm.docs.cern.ch/reference/metadata/#metadata
  # https://github.com/inveniosoftware/invenio-rdm-records/tree/master/invenio_rdm_records/fixtures/data/vocabularies
  time = time or datetime.datetime.now(datetime.timezone.utc)
  description = render_zenodo_description()
  package = read_metadata_for_zenodo()
  dfs = glenglat.read_data()
  start_date, end_date = get_measurement_interval(dfs)
  # List all grants, dropping duplicates
  grants = []
  for person in package['contributors']:
    for grant in person.get('funding', []):
      grants.append(grant)
  grants.extend(package.get('funding', []))
  grants = list({frozenset(grant.items()): grant for grant in grants}.values())
  # HACK: Convert source to string to facilitate printing as a reference
  dfs['source'] = dfs['source'].astype('string')
  return {
    'resource_type': {'id': 'dataset'},
    'creators': [
      convert_contributor_to_zenodo(person)
      for person in package['contributors']
      if person['status'] == 'creator'
    ],
    'title': f"{package['name']}: {package['title']}",
    'publication_date': time.strftime('%Y-%m-%d'),
    'description': description,
    'rights': [{'id': license['name'].lower() for license in package['licenses']}],
    'contributors': [
      convert_contributor_to_zenodo(person)
      for person in package['contributors']
      if person['status'] == 'contributor'
    ],
    'subjects': [{'subject': keyword} for keyword in package['keywords']],
    'languages': [{'id': 'eng'}],
    'dates': [
      {
        'date': f'{start_date}/{end_date}',
        'type': {'id': 'collected'},
        'description': 'Date range of temperature measurements'
      }
    ],
    'version': package['version'],
    'publisher': 'Zenodo',
    'related_identifiers': [
      # Adds 'Is supplement to' and maybe 'External resources: Available in GitHub'
      {
        'identifier': package['homepage'],
        'scheme': 'url',
        'relation_type': {'id': 'issupplementto'},
        'resource_type': {'id': 'dataset'}
      }
    ],
    'funding': [convert_funding_to_zenodo(grant) for grant in grants],
    # References
    'references': [
      convert_source_to_reference(source)
      for source in (
        dfs['source']
        .query('type.ne("personal-communication")')
        .replace({pd.NA: None})
        .to_dict(orient='records')
      )
    ]
  }


# ---- Zenodo API ----

def build_base_url(sandbox: bool = True) -> str:
  """Build base Zenodo API URL."""
  subdomain = 'sandbox.' if sandbox else ''
  return f'https://{subdomain}zenodo.org/api/records'


def is_sandbox(url: str) -> bool:
  """Check if URL is for the Zenodo Sandbox API."""
  return 'sandbox.zenodo' in url


def get_headers(sandbox: bool = True, invenio: bool = False) -> str:
  """Get Zenodo request headers."""
  if sandbox:
    if 'ZENODO_SANDBOX_ACCESS_TOKEN' not in os.environ:
      raise ValueError('Missing ZENODO_SANDBOX_ACCESS_TOKEN in .env')
    token = os.environ['ZENODO_SANDBOX_ACCESS_TOKEN']
  else:
    if 'ZENODO_ACCESS_TOKEN' not in os.environ:
      raise ValueError('Missing ZENODO_ACCESS_TOKEN in .env')
    token = os.environ['ZENODO_ACCESS_TOKEN']
  return {
    'Authorization': f'Bearer {token}',
    'Accept': 'application/vnd.inveniordm.v1+json' if invenio else 'application/json'
  }


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


def create_draft(metadata: dict = {}, sandbox: bool = True) -> dict:
  """Create a draft record."""
  # https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#create-a-draft-record
  response = requests.post(
    url=build_base_url(sandbox=sandbox),
    json={'metadata': metadata},
    headers=get_headers(sandbox=sandbox, invenio=True)
  )
  raise_error(response)
  return response.json()


def find_record(
  q: str = 'glenglat',
  sort: str = 'newest',
  allversions: bool = False,
  sandbox: bool = True
) -> Optional[dict]:
  """Find a record."""
  # https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#search-records
  response = requests.get(
    url=build_base_url(sandbox=sandbox),
    params={
      'q': q,
      'sort': sort,
      'allversions': allversions,
    },
    headers=get_headers(sandbox=sandbox, invenio=True)
  )
  raise_error(response)
  result = response.json()
  records = result['hits']['hits']
  if len(records) > 1:
    link_text = '\n'.join(record['links']['self_html'] for record in records)
    raise Exception(f'Multiple records found:\n{link_text}')
  return records[0] if records else None


def create_or_get_new_version_draft(record: dict) -> dict:
  """Create or get a new version draft of a record."""
  # https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#create-a-new-version
  url = record['links']['versions']
  response = requests.post(
    url=url,
    headers=get_headers(sandbox=is_sandbox(url), invenio=True)
  )
  raise_error(response)
  return response.json()


def raise_error_if_not_draft(record: dict) -> None:
  """Raise an exception if the record is not a draft."""
  if not record.get('is_draft', False):
    raise Exception('Record is not a draft.')


def clear_draft(record: dict) -> dict:
  """Clear a draft record's files and metadata."""
  raise_error_if_not_draft(record)
  # List files
  # https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#list-a-drafts-files
  url = f"{record['links']['self']}/files"
  response = requests.get(
    url=url,
    headers=get_headers(sandbox=is_sandbox(url), invenio=False)
  )
  raise_error(response)
  result = response.json()
  files = result['entries']
  # Delete files
  for file in files:
    response = requests.delete(
      url=file['links']['self'],
      headers=get_headers(sandbox=is_sandbox(url), invenio=False)
    )
    raise_error(response)
  # Clear metadata
  return edit_draft(record, metadata={})


def edit_draft(record: dict, metadata: dict) -> dict:
  """Edit draft record."""
  # https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#update-a-draft-record
  raise_error_if_not_draft(record)
  url = record['links']['self']
  response = requests.put(
    url=url,
    json={'metadata': metadata},
    headers=get_headers(sandbox=is_sandbox(url), invenio=True)
  )
  raise_error(response)
  return response.json()


def add_file_to_draft(record: dict, path: Union[Path, str]) -> dict:
  """Add file to a draft record."""
  raise_error_if_not_draft(record)
  url = record['links']['files']
  path = Path(path)
  # Register file
  # https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#start-draft-file-uploads
  response = requests.post(
    url=url,
    json=[{'key': path.name}],
    headers=get_headers(sandbox=is_sandbox(url))
  )
  raise_error(response)
  result = response.json()
  upload = result['entries'][0]
  # Upload file content
  # https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#upload-a-draft-files-content
  with open(path, 'rb') as file:
    response = requests.put(
      url=upload['links']['content'],
      data=file,
      headers={
        **get_headers(sandbox=is_sandbox(url)),
        'Content-Type': 'application/octet-stream'
      }
    )
  raise_error(response)
  # Commit upload
  # https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#complete-a-draft-file-upload
  response = requests.post(
    url=upload['links']['commit'],
    headers=get_headers(sandbox=is_sandbox(url))
  )
  raise_error(response)
  return response.json()


def reserve_draft_doi(record: dict) -> dict:
  """Reserve a DOI for a draft record."""
  raise_error_if_not_draft(record)
  if 'doi' in record.get('pids', {}):
    return record
  url = record['links']['reserve_doi']
  response = requests.post(
    url=url,
    headers=get_headers(sandbox=is_sandbox(url), invenio=True)
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
  # Tag is not already in use
  REPO.remotes['origin'].fetch()
  tag = 'v' + read_metadata_for_zenodo()['version']
  existing_tags = [repo_tag for repo_tag in REPO.tags if repo_tag.name == tag]
  if existing_tags:
    commit = existing_tags[0].commit
    raise Exception(f'Tag {tag} is already in use (commit: {commit}).')
  return REPO.head.commit, tag


def publish_to_zenodo(sandbox: bool = True, new: bool = False) -> None:
  """
  Publish glenglat as a Zenodo deposition.

  Builds glenglat for release,
  creates a new record draft (or a new version draft if a record already exists),
  and adds the release file to the record.

  Parameters
  ----------
  sandbox
    Use the Zenodo Sandbox rather than the production Zenodo.
  new
    Create a new record draft rather than a new version draft
    (sandbox only).
  """
  # Render metadata
  time = datetime.datetime.now(datetime.timezone.utc)
  metadata = render_zenodo_metadata(time=time)
  version = metadata['version']
  # Check repository
  if not sandbox:
    commit, tag = is_repo_publishable()
    print(f'Publishing commit {commit} as {tag}.')
  # Create record
  if new:
    if not sandbox:
      raise ValueError('Forcing a new record draft is only supported in the sandbox.')
    draft = create_draft(sandbox=sandbox)
  else:
    record = find_record(q='glenglat', allversions=False, sandbox=sandbox)
    if not record:
      print('No existing records found. A new draft will be created.')
      draft = create_draft(sandbox=sandbox)
    else:
      zenodo_version = record['metadata']['version']
      if version == zenodo_version:
        raise Exception(
          f"A record for v{version} already exists: {record['links']['self_html']}"
        )
      print(
        f'Found a record for v{zenodo_version}. A draft for v{version} will be created.'
      )
      draft = create_or_get_new_version_draft(record)
      draft = clear_draft(draft)
  # Update deposition metadata
  draft = edit_draft(draft, metadata=metadata)
  # Reserve a DOI
  draft = reserve_draft_doi(draft)
  # Build and submit data
  doi = f"https://doi.org/{draft['pids']['doi']['identifier']}"
  data_path = build_for_zenodo(doi=doi, time=time)
  add_file_to_draft(draft, path=data_path)
  print(
    f"Draft record for v{version} ready for review: {draft['links']['self_html']}"
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
