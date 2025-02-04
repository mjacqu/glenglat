import copy
from collections import defaultdict
import datetime
from decimal import Decimal
import functools
import json
from pathlib import Path
import re
import shutil
from typing import Dict, Union, Optional, Literal
import unicodedata
import xml.etree.ElementTree as ET
import yaml

import fire
import frictionless
import jinja2
import numpy as np
import pandas as pd
import tablecloth.excel
import xlsxwriter
import xlsxwriter.format
import xlsxwriter.worksheet


ROOT = Path(__file__).parent
"""Path to repository root."""

TEMPLATES_PATH = ROOT.joinpath('templates')
"""Path to templates directory."""

README_PATH = ROOT.joinpath('README.md')
"""Path to readme file."""

DATAPACKAGE_PATH = ROOT.joinpath('datapackage.yaml')
"""Path to metadata file."""

DATA_PATH = ROOT.joinpath('data')
"""Path to data directory."""

SUBMISSION_DATAPACKAGE_PATH = ROOT.joinpath('submission/datapackage.yaml')
"""Path to submission metadata file."""

SUBMISSION_SPREADSHEET_PATH = ROOT.joinpath('submission/template.xlsx')
"""Path to submission spreadsheet template file."""

SOURCE_ID_REGEX = r'(?:^|\s|\()([a-z]+[0-9]{4}[a-z]?)(?:$|\s|\)|,|\.)'
"""Regular expression for extracting source ids from notes."""

EMAIL_REGEX = r'[\w\.\-]+@[\w\-]+(?:\.\w{2,})+'
"""Regular expression for an email address."""

ORCID_REGEX = r'[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]'
"""Regular expression for ORCID identifiers."""

# Phrase
outchar = r'[^\(\)\[\]\|\s]'
inchar = r'[^\(\)\[\]\|]'
phrase = fr'{outchar}{inchar}*?{outchar}'

PERSON_TITLE_REGEX = fr'(?P<name>{phrase})(?: \[(?P<latin>{phrase})\])?'
"""Regular expression for a person title."""

PERSON_REGEX = fr'^(?P<title>{PERSON_TITLE_REGEX})(?: \((?:(?P<orcid>{ORCID_REGEX})|(?P<email>{EMAIL_REGEX}))\))?$'
"""Regular expression for a person."""

RORID_REGEX = r'0[a-hj-km-np-tv-z|0-9]{6}[0-9]{2}'
"""Regular expression for ROR identifiers."""

# Phrase with parentheses
outchar = r'[^\[\]\|\s]'
inchar = r'[^\[\]\|]'
parphrase = fr'{outchar}{inchar}*?{outchar}'

FUNDING_REGEX = fr'^(?P<funder>{parphrase})(?: \[(?P<rorid>{RORID_REGEX})\])?(?: >(?: (?P<award>{parphrase}))?(?: \[(?P<number>{parphrase})\])?(?: (?P<url>https?:\/\/[^\)]+))?)?$'
"""Regular expression for a funding source."""

title_regex = fr'{phrase}(?: \[{phrase}\])?'
INVESTIGATOR_REGEX = fr'^(?P<person>{title_regex})?(?: ?\((?P<agencies>{title_regex}(?:; {title_regex})*)\))?(?: {{(?P<notes>[^\]]+)}})?$'
"""Regular expression for an investigator."""

# ---- Configure YAML rendering ----

def yaml_str_representer(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
  """
  Configures YAML to dump multiline strings with '|' style.

  See https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data
  """
  if len(data.splitlines()) > 1:
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
  return dumper.represent_scalar('tag:yaml.org,2002:str', data)


# Configure YAML handling of multiline strings
yaml.add_representer(str, yaml_str_representer)
yaml.representer.SafeRepresenter.add_representer(str, yaml_str_representer)


def render_yaml(data: dict) -> str:
  """Render dictionary as YAML string."""
  return yaml.dump(
    data,
    stream=None,
    indent=2,
    encoding='utf-8',
    allow_unicode=True,
    width=float('inf'),
    sort_keys=False
  ).decode('utf-8')


# ---- Configure Jinja2 rendering ----

class RelativeEnvironment(jinja2.Environment):
  """Enable relative template paths in Jinja2 templates."""

  def join_path(self, template: str, parent: str) -> str:
    return str(Path(parent).parent.joinpath(template))


def render_template(path: Union[Path, str], data: dict) -> str:
  """Render a Jinja2 template with relative paths."""
  path = Path(path)
  environment = RelativeEnvironment(
    loader=jinja2.FileSystemLoader(path.parent, encoding='utf-8'),
    lstrip_blocks=True,
    trim_blocks=True,
  )
  template = environment.get_template(path.name)
  return template.render(**data)


# ---- Read functions ----

def read_readme() -> str:
  """Read readme."""
  return README_PATH.read_text()


def read_metadata() -> dict:
  """Read metadata as dictionary."""
  return yaml.safe_load(DATAPACKAGE_PATH.read_text())


def read_package() -> frictionless.Package:
  """Read metadata as Frictionless Package."""
  return frictionless.Package(DATAPACKAGE_PATH)


PANDAS_DTYPES = {
  'string': 'string',
  'number': 'Float64',
  'integer': 'Int64',
  'boolean': 'boolean',
  'date': 'string',
  'time': 'string',
  'year': 'Int64'
}

def read_data(dtype: Optional[str] = None) -> Dict[str, pd.DataFrame]:
  """
  Read all data files and concatenate them by table name.

  A __path__ column is added to each DataFrame with the path to the file.

  Parameters
  ----------
  dtype
    Data type for all columns (typically 'string').
    If None, data types are inferred from metadata.
  """
  if dtype is None:
    package = read_package()
    dtypes = {
      resource.name: {
        field.name: PANDAS_DTYPES[field.type] for field in resource.schema.fields
      }
      for resource in package.resources
    }
  dfs: Dict[str, pd.DataFrame] = defaultdict(dict)
  for path in DATA_PATH.glob('**/*.csv'):
    dfs[path.stem][str(path.relative_to(ROOT))] = pd.read_csv(
      path, dtype=(dtypes[path.stem] if dtype is None else dtype)
    )
  for key, values in dfs.items():
    for path, df in values.items():
      # Include path to file in __path__ column
      df['__path__'] = pd.Series(path, index=df.index, dtype='string')
    dfs[key] = pd.concat(values, ignore_index=True)
  return dict(dfs)


# ---- Write functions ----

def write_readme(text: str) -> None:
  """Write readme."""
  README_PATH.write_text(text)


def write_submission_yaml() -> None:
  """Write submission metadata."""
  package = read_package()
  # --- Modify borehole table ---
  borehole = package.get_resource('borehole')
  # Filter columns
  borehole.schema.fields = [
    field for field in borehole.schema.fields
    if field.name not in ['source_id', 'location_origin', 'elevation_origin', 'curator']
  ]
  # Customize description of borehole.notes
  borehole.schema.get_field('notes').description = (
    'Additional remarks about the study site, the borehole, or the measurements therein. '
    'Literature references should be formatted as {url} or {author} {year} ({url}).'
  )
  # Drop foreign keys
  borehole.schema.foreign_keys = None
  # --- Modify measurement table ---
  measurement = package.get_resource('measurement')
  # Filter columns
  measurement.schema.fields = [
    field for field in measurement.schema.fields
    if field.name not in ['profile_id']
  ]
  # Drop primary key
  measurement.schema.primary_key = None
  # Replace foreign keys with direct reference to borehole table
  measurement.schema.foreign_keys = [{
    'fields': ['borehole_id'],
    'reference': {'resource': 'borehole', 'fields': ['id']}
  }]
  # Add columns from profile table
  profile = package.get_resource('profile')
  measurement.schema.fields += [
    field for field in profile.schema.fields
    if field.name not in ['id', 'borehole_id', 'source_id', 'measurement_origin', 'notes']
  ]
  # --- Drop tables other than borehole and measurement ---
  package.resources = [
    resource for resource in package.resources
    if resource.name in ['borehole', 'measurement']
  ]
  # --- Expand trueValues, falseValue to defaults ----
  for resource in package.resources:
    for field in resource.schema.fields:
      if field.type == 'boolean':
        field.true_values = ['True', 'true', 'TRUE']
        field.false_values = ['False', 'false', 'FALSE']
  # --- Strip path prefixes ---
  for resource in package.resources:
    if isinstance(resource.path, list):
      path = resource.path[0]
    else:
      path = resource.path
    resource.path = Path(path).name
    resource.extrapaths = None
  # --- Overwrite package metadata ---
  package.name = 'glenglat-submission'
  package.description = 'Submission format for the global englacial temperature database.'
  # Add created property to pass validation
  package.created = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
  package.title = None
  package.licenses = None
  package.contributors = None
  package.keywords = None
  package.custom = {}
  # --- Validate metadata ----
  metadata = package.to_dict()
  # HACK: Remove spurious csv key from dialects introduced by frictionless
  for resource in metadata['resources']:
    if 'dialect' in resource:
      dialect = resource['dialect']
      resource['dialect'] = {
        **{key: value for key, value in dialect.items() if key != 'csv'},
        **dialect['csv']
      }
  report = frictionless.Package.validate_descriptor(metadata)
  assert report.valid, report.to_summary()
  # --- Write datapackage.yaml ---
  # Remove created property to avoid unnecessary changes
  del metadata['created']
  text = render_yaml(metadata)
  SUBMISSION_DATAPACKAGE_PATH.write_text(text)


def write_submission_md() -> None:
  """Write the <submission-format> section of the readme."""
  # --- Render template ---
  package = yaml.safe_load(SUBMISSION_DATAPACKAGE_PATH.read_text())
  template_path = TEMPLATES_PATH.joinpath('package.md.jinja')
  text = render_template(template_path, data={'package': package})
  # --- Inject into README.md ---
  start = '<!-- <submission-format> -->'
  end = '<!-- </submission-format> -->'
  readme = read_readme()
  start_index = readme.index(start) + len(start)
  end_index = readme.index(end)
  new_readme = readme[:start_index] + '\n' + text.strip() + '\n' + readme[end_index:]
  write_readme(new_readme)


def write_submission_xlsx() -> None:
  """Write submission spreadsheet template."""
  package = yaml.safe_load(SUBMISSION_DATAPACKAGE_PATH.read_text())
  # --- Render column comments ---
  template_path = TEMPLATES_PATH.joinpath('comment.txt.jinja')
  template = jinja2.Template(template_path.read_text())
  comments = {
    resource['name']: [
      template.render(**field).strip().replace('\n\n\n', '\n\n')
      for field in resource['schema']['fields']
    ]
    for resource in package['resources']
  }
  # --- Write spreadsheet ---
  # Excel file is written with a fixed timestamp to avoid spurious changes
  book = tablecloth.excel.write_template(
    package,
    path=None,
    header_comments=comments,
    format_comments={'font_size': 11, 'x_scale': 3, 'y_scale': 4}
  )
  book.set_properties({'created': datetime.datetime(2000, 1, 1)})
  book.filename = str(SUBMISSION_SPREADSHEET_PATH)
  book.close()


def write_submission() -> None:
  """Write submission files."""
  write_submission_yaml()
  write_submission_md()
  write_submission_xlsx()


# ---- Reference list ----

def infer_name_parts(latin: str, name: str = None) -> Optional[dict]:
  """
  Infer given and family names from a name and its Latin transliteration.

  Examples
  --------
  >>> infer_name_parts('Jakob F. Steiner')
  {'latin': {'given': 'Jakob F.', 'family': 'Steiner'}}
  >>> infer_name_parts('N. G. Razumeiko', 'Н. Г. Разумейко')
  {'name': {'given': 'Н. Г.', 'family': 'Разумейко'},
  'latin': {'given': 'N. G.', 'family': 'Razumeiko'}, 'script': 'cyrillic'}
  >>> infer_name_parts('Sun Weijun', '孙维君')
  {'name': {'family': '孙', 'given': '维君'},
  'latin': {'family': 'Sun', 'given': 'Weijun'}, 'script': 'chinese'}
  >>> infer_name_parts('Sugiyama Shin', '杉山 慎')
  {'name': {'family': '杉山', 'given': '慎'},
  'latin': {'family': 'Sugiyama', 'given': 'Shin'}, 'script': 'kanji'}
  >>> infer_name_parts('Sugiyama Shin', 'スギヤマ シン')
  {'name': {'family': 'スギヤマ', 'given': 'シン'},
  'latin': {'family': 'Sugiyama', 'given': 'Shin'}, 'script': 'kana'}
  >>> infer_name_parts('Ahn Jinho', '안진호')
  {'name': {'family': '안', 'given': '진호'},
  'latin': {'family': 'Ahn', 'given': 'Jinho'}, 'script': 'hangul'}
  """
  latin_words = latin.split(' ')
  # Latin: Last word is family name
  if name is None:
    if (
      # more than two words and multiple consecutive words not ending with a period
      (len(latin_words) > 2 and re.search(r'[^ \.]+ [^ \.]+(?: |$)', latin))
      # last word ends with a period
      or latin_words[-1].endswith('.')
    ):
      return None
    return {'latin': {'given': ' '.join(latin_words[:-1]), 'family': latin_words[-1]}}
  words = name.split(' ')
  # Cyrillic: Last word is family name
  if re.search(r'[А-ЯЁа-яё]+', name):
    if len(words) < 2 or len(words) != len(latin_words):
      raise ValueError(f'Cyrillic name "{name} [{latin}]" is ambiguous')
    return {
      'name': {'given': ' '.join(words[:-1]), 'family': words[-1]},
      'latin': {'given': ' '.join(latin_words[:-1]), 'family': latin_words[-1]},
      'script': 'cyrillic'
    }
  # Chinese
  if re.search(r'[\u4e00-\u9fff]+', name):
    if len(words) > 2:
      return None
    # Kanji (Japanese): First word is family name
    if len(words) == 2:
      if len(latin_words) != 2:
        return None
      return {
        'name': {'family': words[0], 'given': words[1]},
        'latin': {'family': latin_words[0], 'given': latin_words[1]},
        'script': 'kanji'
      }
    # Chinese: First character of original and first word of latin is family name
    if len(latin_words) != 2:
        return None
    return {
      'name': {'family': name[0], 'given': name[1:]},
      'latin': {'family': latin_words[0], 'given': ' '.join(latin_words[1:])},
      'script': 'chinese'
    }
  # Hangul (Korean): First character of original and first word of latin is family name
  if re.search(r'[\uac00-\ud7af]+', name):
    if len(words) > 1:
        return None
    return {
      'name': {'family': name[0], 'given': name[1:]},
      'latin': {'family': latin_words[0], 'given': ' '.join(latin_words[1:])},
      'script': 'hangul'
    }
  # Kana (Japanese): First word is family name
  if re.search(r'[\u3040-\u30ff]+', name):
    if len(words) != 2 or len(latin_words) != 2:
      return None
    return {
      'name': {'family': words[0], 'given': words[1]},
      'latin': {'family': latin_words[0], 'given': latin_words[1]},
      'script': 'kana'
    }
  return None


def squeeze_whitespace(string: str) -> str:
  """
  Squeeze whitespace in a string.

  Examples
  --------
  >>> squeeze_whitespace('  Jakob  F.  Steiner  ')
  'Jakob F. Steiner'
  """
  return re.sub(r'\s+', ' ', string.strip())


def strip_curly_braces(string: str) -> str:
  """
  Strip curly braces from a string.

  Examples
  --------
  >>> strip_curly_braces('Emmanuel {Le Meur}')
  'Emmanuel Le Meur'
  """
  return re.sub(r'{|}', '', string)


def parse_name_parts(name: str) -> Optional[dict]:
  """
  Parse given and family names from a name with curly braces.

  Examples
  --------
  >>> parse_name_parts('Emmanuel {Le Meur}')
  {'family': 'Le Meur', 'given': 'Emmanuel'}
  >>> parse_name_parts('{Duan} Keqin')
  {'family': 'Duan', 'given': 'Keqin'}
  >>> parse_name_parts('Jon Ove {Hagen}')
  {'family': 'Hagen', 'given': 'Jon Ove'}
  >>> parse_name_parts('Duan Keqin') is None
  True
  """
  # Extract name within curly braces
  match = re.search(r'{(?P<family>[^}]+)}', name)
  if match is None:
    return None
  parts = match.groupdict()
  # Infer given name as remaining part of the name
  parts['given'] = squeeze_whitespace(name.replace(match.group(), ''))
  return parts


def parse_person_string(string: str) -> dict:
  """
  Parse person string.

  Returns {title, name, latin, orcid, email}, where name and latin have the format
  {name, family, given} but name may be None.
  Curly braces are removed from 'title' and 'orcid' is expanded to full URL.

  Example
  -------
  >>> parse_person_string('杉山 慎 [Sugiyama Shin] (0000-0001-5323-9558)')
  {'title': '杉山 慎 [Sugiyama Shin]',
  'name': {'name': '杉山 慎', 'family': '杉山', 'given': '慎'},
  'latin': {'name': 'Sugiyama Shin', 'family': 'Sugiyama', 'given': 'Shin'},
  'orcid': 'https://orcid.org/0000-0001-5323-9558', 'email': None}
  >>> parse_person_string('Emmanuel {Le Meur} (test@email.fr)')
  {'title': 'Emmanuel Le Meur', 'name': None,
  'latin': {'name': 'Emmanuel Le Meur', 'family': 'Le Meur', 'given': 'Emmanuel'},
  'orcid': None, 'email': 'test@email.fr'}
  """
  match = re.fullmatch(PERSON_REGEX, string)
  if match is None:
    raise ValueError(f'Invalid person string: {string}')
  groups = match.groupdict()
  # If there is no latinized form in square brackets, assume name is in latin script
  if not groups['latin']:
    groups['latin'] = groups['name']
    groups['name'] = None
  # Extract family and given names
  if re.search(r'{|}', groups['title']):
    for key in ('latin', 'name'):
      if groups[key]:
        if not re.search(r'{|}', groups[key]):
          raise ValueError(
            f"Curly braces missing from original or latin name: {groups['title']}"
          )
        parsed = parse_name_parts(groups[key])
        if not parsed:
          raise ValueError(f'Failed to parse name parts from curly braces: {string}')
        groups[key] = {'name': strip_curly_braces(groups[key]), **parsed}
  else:
    inferred = infer_name_parts(latin=groups['latin'], name=groups['name'])
    if not inferred:
      raise ValueError(f'Family name is ambiguous: {string}')
    groups['latin'] = {'name': groups['latin'], **inferred['latin']}
    if groups['name']:
      groups['name'] = {'name': groups['name'], **inferred['name']}
  # Strip curly braces from title
  groups['title'] = strip_curly_braces(groups['title'])
  # Expand ORCID to full URL
  if groups['orcid']:
    groups['orcid'] = f"https://orcid.org/{groups['orcid']}"
  return groups


def convert_source_to_csl(
  source: Dict[str, str],
  non_latin: Literal['literal', 'given'] = 'literal',
  zotero_citation_key: bool = False
) -> dict:
  """
  Convert source to CSL-JSON.

  To conform to the official JSON Schema for CSL data
  (https://github.com/citation-style-language/schema/blob/master/schemas/input/csl-data.json),
  type 'personal-communication' is replaced with 'personal_communication'.

  Parameters
  ----------
  source
    Dictionary representing a row in the source table.
  non_latin
    Authors and editors are represented as 'family, given' if Latin-only. Otherwise, if:

    * 'given': non-latin name is appended in square brackets to the latin given name
    * 'literal': original title ('name [latin]') is used as 'literal' attribute
  zotero_citation_key
    Add id to a note formatted as 'Citation key: id'. This is useful for Zotero with
    the Better BibTeX plugin.
  """
  # Format person names
  names = defaultdict(list)
  for key in ('author', 'editor'):
    if not source.get(key):
      continue
    strings = source[key].split(' | ')
    for string in strings:
      parsed = parse_person_string(string)
      if parsed['name']:
        if non_latin == 'given':
          name = {
            'family': parsed['latin']['family'],
            'given': f"{parsed['latin']['given']} [{parsed['name']['name']}]"
          }
        elif non_latin == 'literal':
          name = {'literal': parsed['title']}
        else:
          raise ValueError(f'Invalid non_latin: {non_latin}')
      else:
        name = {'family': parsed['latin']['family'], 'given': parsed['latin']['given']}
      names[key].append(name)
  # Use DOI instead of URL if available
  doi = None
  if source['url'] and source['url'].startswith('https://doi.org/'):
    doi = source['url'].replace('https://doi.org/', '')
  # Migrate 'personal-communication' to 'personal_communication'
  # Add a title to personal communications
  source_type = source['type']
  source_title = source['title']
  if source_type == 'personal-communication':
    source_type = 'personal_communication'
    source_title = 'Personal communication'
  csl = {
    'id': source['id'],
    'citation-key': source['id'],
    'author': names['author'],
    'issued': {'date-parts': [[int(source['year'])]]},
    'type': source_type,
    'title': source_title,
    'DOI': doi,
    'URL': None if doi else source['url'],
    'language': source['language'],
    'container-title': source['container_title'],
    'volume': source['volume'],
    'issue': source['issue'],
    'page': source['page'],
    'version': source['version'],
    'editor': names['editor'],
    'collection-title': source['collection_title'],
    'collection-number': source['collection_number'],
    'publisher': source['publisher']
  }
  if zotero_citation_key:
    csl['note'] = f"Citation key: {source['id']}"
  # Keep only truthy values
  return {key: value for key, value in csl.items() if value}


def render_sources_as_csl(
  non_latin: Literal['literal', 'given'] = 'literal',
  zotero_citation_key: bool = False
) -> str:
  """Render sources as CSL-JSON."""
  sources = pd.read_csv(DATA_PATH.joinpath('source.csv'), dtype='string')
  sources.replace({pd.NA: None}, inplace=True)
  csl = [
    convert_source_to_csl(
      source, non_latin=non_latin, zotero_citation_key=zotero_citation_key
    )
    for source in sources.to_dict(orient='records')
  ]
  return json.dumps(csl, indent=2, ensure_ascii=False)


# ---- Author list ----

@functools.lru_cache(maxsize=1)
def build_person_list() -> list[dict]:
  """
  Build list of person dictionaries.

  Returns a list of dictionaries formatted as
  {titles[], emails[], orcid, latin: {name, family, given}, name}.
  """
  df = pd.read_csv(DATA_PATH.joinpath('person.csv'))[
    ['titles', 'emails', 'orcid', 'latin_name', 'latin_family_name', 'name']
  ]
  # Split delimited lists
  list_keys = ('titles', 'emails')
  for key in list_keys:
    df[key] = df[key].str.split(' | ', regex=False)
  # Replace NA with None
  df.replace({pd.NA: None}, inplace=True)
  # Convert to list of dictionaries
  people = df.to_dict(orient='records')
  for person in people:
    # Replace None in list keys with empty list
    for key in list_keys:
      if person[key] is None:
        person[key] = []
    # Format latin name as {name, family, given}
    person['latin'] = {
      'name': person['latin_name'],
      'family': person['latin_family_name'],
      'given': extract_given_name(person['latin_name'], person['latin_family_name'])
    }
    del person['latin_name']
    del person['latin_family_name']
  return people


def find_person(title: str = None, orcid: str = None, email: str = None) -> Optional[dict]:
  """
  Find person in person list.

  Searches by keys (in decreasing order of priority): 'orcid', 'email', 'title'.
  Returns matching {latin: {name, family, given}, name, orcid}.

  Example
  -------
  >>> find_person(title='Shin Sugiyama', orcid='https://orcid.org/0000-0001-5323-9558')
  {'latin': {'name': 'Sugiyama Shin', 'family': 'Sugiyama', 'given': 'Shin'},
  'name': '杉山 慎', 'orcid': 'https://orcid.org/0000-0001-5323-9558'}
  """
  kwargs = {'title': title, 'orcid': orcid, 'email': email}
  matches = []
  for person in build_person_list():
    if (
      (orcid and person['orcid'] == orcid) or
      (email and email in person['emails']) or
      (title and title in person['titles'])
    ):
      matches.append(person)
  if not matches:
    return None
  if len(matches) > 1:
    raise ValueError(
      f'Multiple person matches for {kwargs}: {matches}'
    )
  person = matches[0]
  result = {key: person[key] for key in ('latin', 'name', 'orcid')}
  if orcid:
    if result['orcid'] and result['orcid'] != orcid:
      raise ValueError(
        f'ORCID mismatch for {kwargs} matched to {result}'
      )
    if not result['orcid']:
      print(f"ORCID missing for {result}: {orcid}")
      result['orcid'] = orcid
  return result


def extract_given_name(name: str, family: str) -> str:
  """
  Extract given name from full name.

  Examples
  --------
  >>> extract_given_name('Jakob F. Steiner', 'Steiner')
  'Jakob F.'
  >>> extract_given_name('Sugiyama Shin', 'Sugiyama')
  'Shin'
  """
  pattern = fr'( |^){family}(?: |$)'
  if not re.search(pattern, name):
    raise ValueError(f"Family name '{family}' not found in '{name}'")
  return re.sub(pattern, r'\1', name).strip()


def uppercase_family_name(name: str, family: str) -> str:
  """
  Uppercase family name in full name or title.

  Examples
  --------
  >>> uppercase_family_name('Jakob F. Steiner', 'Steiner')
  'Jakob F. STEINER'
  >>> uppercase_family_name('Sugiyama Shin', 'Sugiyama')
  'SUGIYAMA Shin'
  >>> uppercase_family_name('张通 [Zhang Tong]', 'Zhang')
  '张通 [ZHANG Tong]'
  """
  pattern = fr'(^| |\[){family}(?= |\]|$)'
  matches = re.findall(pattern, name)
  if not matches or len(matches) > 1:
    raise ValueError(f"Family name '{family}' not unique (or present) in '{name}'")
  return re.sub(pattern, fr'\1{family.upper()}', name)


def strip_diacritics(string: str) -> str:
  """
  Remove diacritics (accents, curls, strokes) from a string.

  Examples
  --------
  >>> strip_diacritics('Jakob F. Steiner')
  'Jakob F. Steiner'
  >>> strip_diacritics('Rune Strand Ødegård')
  'Rune Strand Odegard'
  """
  def replace_char(char: str) -> str:
    description = unicodedata.name(char)
    cutoff = description.find(' WITH ')
    if cutoff != -1:
      description = description[:cutoff]
      try:
        char = unicodedata.lookup(description)
      except KeyError:
        pass
    return char

  return ''.join(replace_char(char) for char in string)


def render_author_list() -> list[str]:
  """Render deduplicated and name-filled list of authors."""
  # Gather author strings
  df = pd.read_csv(DATA_PATH.joinpath('source.csv'))
  strings = (
    df['author'].str.split(' | ', regex=False)
    .dropna()
    .explode()
    .drop_duplicates()
  )
  # Parse and find people
  people = []
  missing = []
  for string in strings:
    person = parse_person_string(string)
    found = find_person(
      title=person['title'], orcid=person['orcid'], email=person['email']
    )
    if found:
      people.append({**person, **found})
    else:
      missing.append(string)
  if missing:
    missing_list = '\n'.join(missing)
    raise ValueError(f'People not found:\n{missing_list}')
  # Sort by uppercase latin family name, latin first name
  people = sorted(people, key=lambda x: (
    strip_diacritics(x['latin']['family']).upper(),
    strip_diacritics(x['latin']['given']).upper()
  ))
  # Format person string (uppercase latin family name in title)
  strings = []
  for person in people:
    string = uppercase_family_name(person['latin']['name'], person['latin']['family'])
    if person['name']:
      string = f"{person['name']} [{string}]"
    strings.append(string)
  # Drop duplicates
  return list(dict.fromkeys(strings))


# ---- Data subset ----

def extract_source_ids(s: pd.Series) -> pd.Series:
  """
  Extract source ids from notes.

  For each string, returns a list of source ids or null if none were found.

  Example
  -------
  >>> extract_source_ids(pd.Series(['See an2016 (or zhang1993)', 'none', pd.NA]))
  0    [an2016, zhang1993]
  1                   <NA>
  2                   <NA>
  dtype: object
  """
  return s.apply(
    lambda x: pd.NA if pd.isna(x) else re.findall(SOURCE_ID_REGEX, x) or pd.NA
  )


def gather_source_ids(*args: pd.DataFrame) -> tuple[set[str], set[str]]:
  """
  Gather primary and secondary source ids from tables.

  Parameters
  ----------
  args
    DataFrames to extract source ids from.
  """
  primary = set()
  secondary = set()
  for df in args:
    if 'source_id' in df:
      primary |= set(df['source_id'])
    if 'notes' in df:
      secondary |= set(extract_source_ids(df['notes']).dropna().explode())
  return primary, secondary


def select_rows_by_origin(
  df: pd.DataFrame,
  source: Optional[str] = None,
  curator: Optional[str] = None,
  secondary_sources: bool = False
) -> pd.Series:
  """
  Build boolean mask of rows matching either source OR curator.

  Parameters
  ----------
  df
    Table to mask.
  source
    Select rows with a matching source in `source_id` or
    `notes` (if `secondary_sources` is True).
  curator
    Select rows with a matching curator in `curator` column.
  secondary_sources
    Include secondary sources in `notes` column.
  """
  mask = pd.Series(False, index=df.index)
  if curator and 'curator' in df:
    mask |= df['curator'].str.split(' | ', regex=False).dropna().apply(
      lambda x: curator in x
    ).reindex(df.index, fill_value=False)
  if source and 'source_id' in df:
    source_mask = df['source_id'].eq(source)
    if secondary_sources and 'notes' in df:
      source_mask |= extract_source_ids(df['notes']).dropna().apply(
        lambda x: source in x
      ).reindex(df.index, fill_value=False)
    mask |= source_mask
  return mask


def build_subset_from_selection(
  dfs: dict[str, pd.DataFrame],
  masks: dict[str, pd.DataFrame],
  secondary_sources: bool = False
) -> dict[str, pd.DataFrame]:
  """
  Build data subset.

  Based on a selection of boreholes and profiles, build a subset of all related tables:
  * Add profiles of selected measurements
  * Add boreholes of selected + added profiles
  * Add profiles of selected boreholes
  * Add measurements of selected profiles and those added for selected boreholes
  * Add all sources of the included boreholes and profiles

  Parameters
  ----------
  dfs
    Data tables.
  masks
    Boolean selection masks for each table (matching a key in `dfs`).
  secondary_sources
    Whether to include sources referenced in `notes` columns.
  """
  # Initialize selection
  masks = copy.deepcopy(masks)
  for key in dfs:
    if key not in masks or masks[key] is None:
      masks[key] = pd.Series(False, index=dfs[key].index)
  if not any(masks[key].any() for key in dfs):
    raise ValueError(f'Empty selection')
  # Store initial borehole and profile masks
  initial_borehole_mask = masks['borehole'].copy()
  initial_profile_mask = masks['profile'].copy()
  # Add profiles of selected measurements
  select_measurement_index = pd.MultiIndex.from_frame(
    dfs['measurement'][masks['measurement']][['borehole_id', 'profile_id']]
  )
  profile_index = pd.MultiIndex.from_frame(dfs['profile'][['borehole_id', 'id']])
  masks['profile'] |= profile_index.isin(select_measurement_index)
  # Add boreholes of selected + added profiles
  masks['borehole'] |= dfs['borehole']['id'].isin(
    dfs['profile'][masks['profile']]['borehole_id']
  )
  # Add profiles of selected boreholes
  is_profile_of_selected_borehole = dfs['profile']['borehole_id'].isin(
    dfs['borehole']['id'][initial_borehole_mask]
  )
  masks['profile'] |= is_profile_of_selected_borehole
  # Add measurements of selected profiles + those added for selected boreholes
  select_profile_index = profile_index[initial_profile_mask | is_profile_of_selected_borehole]
  measurement_index = pd.MultiIndex.from_frame(dfs['measurement'][['borehole_id', 'profile_id']])
  masks['measurement'] |= measurement_index.isin(select_profile_index)
  # Add sources
  primary, secondary = gather_source_ids(
    *(dfs[key][masks[key]] for key in ('borehole', 'profile'))
  )
  masks['source'] |= dfs['source']['id'].isin(
    primary | secondary if secondary_sources else primary
  )
  return {key: dfs[key][masks[key]] for key in dfs}


def write_excel_sheet(
  df: pd.DataFrame,
  sheet: xlsxwriter.worksheet.Worksheet,
  header_format: Optional[xlsxwriter.format.Format] = None,
  data_format: Optional[xlsxwriter.format.Format] = None,
  freeze: Optional[tuple[int, int]] = None
):
  """
  Write DataFrame to an Excel sheet.

  Parameters
  ----------
  df
    DataFrame to write.
  sheet
    Excel sheet to write to.
  header_format
    Format of header cells.
  data_format
    Format of data cells.
  freeze
    Row and column to freeze (zero-indexed).
  """
  df = df.replace({float('inf'): 'INF', float('-inf'): '-INF'}).fillna('')
  # HACK: Ensure that column names are also strings due to tablecloth bug (v <= 0.1.0)
  df.columns = df.columns.astype('string')
  tablecloth.excel.write_table(
    sheet,
    header=df.columns,
    format_header=header_format,
    freeze_header=False
  )
  for i, row in enumerate(df.values):
    sheet.write_row(i + 1, 0, row)
  if freeze:
    sheet.freeze_panes(*freeze)
  # Infer content width
  # TODO: Use tablecloth.excel functions for calculating column widths (v > 0.1.0)
  min_width, max_width = 10, 30
  column_widths = (
    df.astype('string', copy=False)
    .apply(lambda s: s.str.len())
    .apply(lambda s: max(len(str(s.name)), s.max()))
    .mul(1.25)
    .clip(min_width, max_width)
  )
  for i, width in enumerate(column_widths):
    sheet.set_column(i, i, width, data_format)


def write_subset(
  path: Union[str, Path],
  source: Optional[str] = None,
  curator: Optional[str] = None,
  secondary_sources: bool = False,
  source_files: bool = False
) -> None:
  """
  Write data subset.

  Boreholes and profiles are selected by source and/or curator,
  then all related records are included as needed.
  See `select_by_origin` and `build_subset_from_selection` for details.

  Writes a CSV file for each table (data/*.csv), an Excel file (data.xlsx), and
  source directories (sources/*) if `source_files` is True.

  Parameters
  ----------
  path
    Path to write the subset.
  source
    Select boreholes and profiles by source.
  curator
    Select boreholes by curator.
  secondary_sources
    Whether to consider sources in `notes` columns.
  source_files
    Whether to include source directories of included sources (sources/*).
  """
  # ---- Build subset ----
  dfs = read_data(dtype='string')
  masks = {
    key: select_rows_by_origin(
      dfs[key],
      source=source,
      curator=curator,
      secondary_sources=secondary_sources
    )
    for key in ('borehole', 'profile')
  }
  dfs = build_subset_from_selection(
    dfs, masks=masks, secondary_sources=secondary_sources
  )
  # Drop __path__ column and empty tables
  dfs = {
    key: df.drop(columns=['__path__'], errors='ignore')
    for key, df in dfs.items()
    if not df.empty
  }
  if not dfs:
    raise ValueError('Subset is empty')
  # ---- Write subset ----
  path = Path(path)
  # Write CSV files
  path.joinpath('data').mkdir(parents=True, exist_ok=True)
  for key, df in dfs.items():
    csv_path = path.joinpath(f'data/{key}.csv')
    df.to_csv(csv_path, index=False)
  # Write Excel file
  excel_path = path.joinpath('data.xlsx')
  book = xlsxwriter.Workbook(excel_path)
  header_format = book.add_format({'bold': True, 'bg_color': '#d3d3d3'})
  data_format = book.add_format({'valign': 'top', 'text_wrap': True})
  # source and borehole tables (transposed)
  for key in ('source', 'borehole'):
    if key not in dfs:
      continue
    sheet = book.add_worksheet(key)
    df = dfs[key].transpose().reset_index()
    df.columns = df.iloc[0]
    write_excel_sheet(
      df=df.iloc[1:],
      sheet=sheet,
      header_format=header_format,
      data_format=data_format,
      freeze=(1, 1)
    )
  # profile_measurement tables (complex transpose)
  if 'profile' in dfs and 'measurement' in dfs:
    sheet = book.add_worksheet('profile_measurement')
    profile_index = pd.MultiIndex.from_frame(dfs['profile'][['borehole_id', 'id']])
    # Build transposed profiles
    profiles = dfs['profile'].rename(columns={'id': 'profile_id'}).transpose().reset_index()
    profiles.columns = profiles.iloc[0]
    profiles = profiles.iloc[1:]
    # Temporarily use profile multi-index as a unique index for reindexing
    profiles.columns = [profiles.columns[0], *profile_index.to_list()]
    profiles = profiles.reindex(
      columns=[profiles.columns[0], *[x for col in profile_index for x in (col, '')]]
    )
    profiles.columns = [
      profiles.columns[0],
      *[x for col in profile_index.get_level_values(level=0) for x in (col, '')]
    ]
    write_excel_sheet(
      df=profiles,
      sheet=sheet,
      header_format=header_format,
      data_format=data_format,
      freeze=(2, 1)
    )
    # Also format second row (profile_id) as header
    sheet.write_row(1, 0, profiles.iloc[0].fillna(''), header_format)
    # Add depth-temperature profiles
    measurements = dfs['measurement'].set_index(['borehole_id', 'profile_id']).sort_index()
    blocks = [measurements.loc[index].reset_index(drop=True) for index in profile_index]
    measurements = pd.concat(blocks, axis=1)
    start_row_index = profiles.shape[0] + 1
    sheet.write_row(start_row_index, 1, measurements.columns, header_format)
    for i, row in enumerate(measurements.replace({pd.NA: None}).values):
      sheet.write_row(i + start_row_index + 1, 1, row)
  book.close()
  # Write source directories
  if source_files:
    source_ids = dfs['source']['id']
    for source_id in source_ids:
      base_path = Path('sources').joinpath(source_id)
      origin = ROOT.joinpath(base_path)
      if origin.is_dir():
        shutil.copytree(
          src=origin,
          dst=path.joinpath(base_path),
          dirs_exist_ok=True
        )


def read_plotdigitizer_xml(path: Union[str, Path]) -> pd.DataFrame:
  path = Path(path)
  tree = ET.parse(path)
  root = tree.getroot()
  # Image file
  image = root.find('image')
  if image is None:
    raise ValueError('Missing <image>')
  if 'file' not in image.attrib:
    raise ValueError('Missing <image.file>')
  file = image.attrib['file']
  if file in (None, '', 'none', 'null'):
    raise ValueError(f'Invalid <image.file>: {file}')
  filepath = path.parent / file
  if not filepath.is_file():
    raise FileNotFoundError(f'Image does not exist: {filepath}')
  # Axes
  axes = root.find('axesnames')
  if axes is None:
    raise ValueError('Missing <axesnames>')
  if 'x' not in axes.attrib:
    raise ValueError('Missing <axisnames.x>')
  if 'y' not in axes.attrib:
    raise ValueError('Missing <axisnames.y>')
  points = root.findall('point')
  if not points:
    raise ValueError('No <point> elements found')
  df = pd.DataFrame([point.attrib for point in points]).astype(float)
  if not df['n'].is_monotonic_increasing:
    raise ValueError('Points are not sorted')
  if df[['dx', 'dy']].isnull().any(axis=None):
    raise ValueError('Points contain null values')
  return (
    df[['dx', 'dy']].rename(columns={'dx': axes.attrib['x'], 'dy': axes.attrib['y']})
  )


def convert_date_to_decimal_year(date: datetime.datetime) -> float:
  """
  Convert date to decimal year.

  Examples
  --------
  >>> convert_date_to_decimal_year(datetime.datetime(1969, 1, 1))
  1969.0
  >>> convert_date_to_decimal_year(datetime.datetime(1969, 10, 1))
  1969.7479452054795
  >>> convert_date_to_decimal_year(datetime.datetime(1969, 11, 30))
  1969.9123287671232
  """
  begin = datetime.datetime(date.year, 1, 1)
  end = datetime.datetime(date.year + 1, 1, 1)
  return date.year + (date - begin).total_seconds() / (end - begin).total_seconds()


def round_date(date: datetime.datetime) -> datetime.datetime:
  """
  Round date to nearest date.

  Examples
  --------
  >>> round_date(datetime.datetime(1969, 10, 1, 0, 0, 0, 1))
  datetime.datetime(1969, 10, 1, 0, 0)
  >>> round_date(datetime.datetime(1969, 10, 1, 12))
  datetime.datetime(1969, 10, 2, 0, 0)
  >>> round_date(datetime.datetime(1969, 11, 29, 23, 59, 59, 999997))
  datetime.datetime(1969, 11, 30, 0, 0)
  """
  return (date + datetime.timedelta(hours=12)).replace(
    hour=0, minute=0, second=0, microsecond=0
  )


def convert_decimal_year_to_date(year: float) -> datetime.datetime:
  """
  Convert decimal year to ISO8601 date format.

  Examples
  --------
  >>> convert_decimal_year_to_date(1969.0)
  datetime.datetime(1969, 1, 1, 0, 0)
  >>> convert_decimal_year_to_date(1969 + 1/365)
  datetime.datetime(1969, 1, 1, 23, 59, 59, 999999)
  >>> year = convert_date_to_decimal_year(datetime.datetime(1969, 10, 1))
  >>> round_date(convert_decimal_year_to_date(year))
  datetime.datetime(1969, 10, 1, 0, 0)
  >>> year = convert_date_to_decimal_year(datetime.datetime(1969, 11, 30))
  >>> round_date(convert_decimal_year_to_date(year))
  datetime.datetime(1969, 11, 30, 0, 0)
  """
  full_years = int(year)
  remainder = year - full_years
  begin = datetime.datetime(full_years, 1, 1)
  end = datetime.datetime(full_years + 1, 1, 1)
  last_year_length = datetime.timedelta(seconds=(end - begin).total_seconds())
  return begin + remainder * last_year_length


def interpolate_depth_timeseries(
  dfs: Dict[Union[str, int, Decimal], pd.DataFrame],
  years: list[float],
  borehole_id: int,
) -> Dict[str, pd.DataFrame]:
  """
  Interpolate temperature-depth profiles from temperatures at different depths.

  Parameters
  ----------
  dfs
    Dictionary of DataFrames with columns (decimal) 'year' and 'temperature',
    where keys are thermistor depth.
  Years
    List of decimal years to interpolate.
  borehole_id
    Borehole id to assign to profiles.

  Returns
  -------
  A 'profile' DataFrame with columns
  'borehole_id', 'id' (index of date in dates with measurements), and 'date',
  and a 'measurement' DataFrame with columns
  'borehole_id', 'profile_id', 'depth', and 'temperature' for each date.
  Measurements with no temperature and profiles with no measurements are dropped.
  """
  # Initialize profiles
  profiles = pd.DataFrame({
    'borehole_id': borehole_id,
    'id': np.arange(len(years)) + 1,
    'date': [round_date(convert_decimal_year_to_date(year)) for year in years]
  })
  # Interpolate temperatures
  measurements = []
  for depth, df in dfs.items():
    if df.empty:
      continue
    temperature = np.interp(
      x=years,
      xp=df['year'].astype(float),
      fp=df['temperature'].astype(float),
      left=np.nan,
      right=np.nan
    )
    measurement = pd.DataFrame({
      'borehole_id': borehole_id,
      'profile_id': profiles['id'].values,
      'depth': Decimal(depth),
      'temperature': temperature
    })
    measurements.append(measurement)
  measurements = pd.concat(measurements, ignore_index=True)
  # Order measurements by profile id and depth
  measurements.sort_values(['profile_id', 'depth'], inplace=True)
  # Drop measurements with no temperature
  measurements.dropna(subset=['temperature'], inplace=True)
  measurements.reset_index(inplace=True, drop=True)
  # Drop profiles with no measurements
  mask = profiles['id'].isin(measurements['profile_id'])
  profiles = profiles[mask].reset_index(drop=True)
  profiles.index += 1
  # Renumber profile ids
  remap = dict(zip(profiles['id'], profiles.index))
  profiles['id'].map(remap)
  measurements['profile_id'] = measurements['profile_id'].map(remap)
  return {'profile': profiles, 'measurement': measurements}


def interpolate_plotdigitizer_depth_timeseries(
  glob: str,
  n: int,
  coverage: Literal['any', 'all'] = 'any',
  ignore_coverage: list[str] = None
) -> Dict[str, pd.DataFrame]:
  """
  Interpolate temperature-depth profiles from PlotDigitizer XML files for each depth.

  Parameters
  ----------
  glob
    Glob pattern to match XML files.
  n
    Number of equal-length time intervals to divide temporal coverage into.
    Interpolation is performed at the endpoints of these intervals (so n + 1 profiles).
  coverage
    Whether to run interpolation from the earliest to latest time with temperature at
    any depth, or at the earliest to latest time with temperature at all depths.
  ignore_coverage
    Depths to ignore for coverage check.
  """
  # Load thermistors
  paths = list((ROOT / 'sources').glob(glob))
  borehole_ids = {path.stem.split('_')[0] for path in paths}
  if len(set(borehole_ids)) > 1:
    raise ValueError(f'Multiple boreholes found: {borehole_ids}')
  borehole_id = int(borehole_ids.pop())
  dfs = {}
  for path in paths:
    depth = path.stem.split('_')[1]
    if depth[-1] != 'm':
      raise ValueError(f'Invalid depth: {depth}')
    depth = depth.replace('m', '')
    if depth in dfs:
      raise ValueError(f'Duplicate depth: {depth}')
    dfs[depth] = read_plotdigitizer_xml(path)
  # Interpolate thermistors
  ignore = [] if ignore_coverage is None else ignore_coverage
  if coverage == 'any':
    min_year = min(df['year'].min() for depth, df in dfs.items() if depth not in ignore)
    max_year = max(df['year'].max() for depth, df in dfs.items() if depth not in ignore)
    years = np.linspace(min_year, max_year, n + 1)
  elif coverage == 'all':
    min_year = max(df['year'].min() for depth, df in dfs.items() if depth not in ignore)
    max_year = min(df['year'].max() for depth, df in dfs.items() if depth not in ignore)
    years = np.linspace(min_year, max_year, n + 1)
  else:
    raise ValueError(f'Invalid coverage: {coverage}')
  return interpolate_depth_timeseries(dfs, years, borehole_id)


# Generate command line interface
if __name__ == '__main__':
  fire.Fire()
