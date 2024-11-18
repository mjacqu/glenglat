import copy
from collections import defaultdict
import datetime
import json
from pathlib import Path
import re
import shutil
from typing import Dict, Union, Optional
import unicodedata
import yaml

import fire
import frictionless
import jinja2
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

ochar = r'[^\(\)\[\]\|\s]'
ichar = r'[^\(\)\[\]\|]'
phrase = fr'{ochar}{ichar}*{ochar}'

EMAIL_REGEX = r'[\w\.\-]+@[\w\-]+(?:\.\w{2,})+'
"""Regular expression for an email address."""

ORCID_REGEX = r'[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]'
"""Regular expression for ORCID identifiers."""

person = fr'{phrase}(?: \[{phrase}\])?(?: \({ORCID_REGEX}\))?'

PERSON_TITLE_REGEX = fr'(?P<name>{phrase})(?: \[(?P<latin>{phrase})\])?'
"""Regular expression for a person title."""

PERSON_REGEX = fr'(?P<title>{PERSON_TITLE_REGEX})(?: \((?:(?P<orcid>{ORCID_REGEX})|(?P<email>{EMAIL_REGEX}))\))?'
"""Regular expression for a person."""

RORID_REGEX = r'0[a-hj-km-np-tv-z|0-9]{6}[0-9]{2}'
"""Regular expression for ROR identifiers."""

FUNDING_REGEX = fr'(?P<funder>{phrase})(?: \[(?P<rorid>{RORID_REGEX})\])?(?: >(?: (?P<award>{phrase}))?(?: \[(?P<number>{phrase})\])?(?: \((?P<url>https?:\/\/[^\)]+)\))?)?'
"""Regular expression for a funding source."""

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


# ---- Sources ----

def parse_person_string(person: str) -> dict:
  """
  Parse person string.

  Example
  -------
  >>> parse_person_string('杉山 慎 [Sugiyama Shin] (0000-0001-5323-9558)')
  {'title': '杉山 慎 [Sugiyama Shin]', 'name': '杉山 慎', 'latin': 'Sugiyama Shin',
  'orcid': 'https://orcid.org/0000-0001-5323-9558', 'email': None}
  """
  match = re.fullmatch(PERSON_REGEX, person)
  if match is None:
    raise ValueError(f'Invalid person string: {person}')
  groups = match.groupdict()
  if groups['orcid']:
    groups['orcid'] = f'https://orcid.org/{groups["orcid"]}'
  return groups


def find_person(person: dict, df: pd.DataFrame) -> Optional[dict]:
  """
  Find person in person table.

  Searches by keys (in decreasing order): 'orcid', 'email', 'title'.
  Returns keys 'title', 'latin' (family and given), and 'orcid'.

  Example
  -------
  >>> dfs = read_data()
  >>> find_person(
  ...   {'title': 'Shin Sugiyama', 'orcid': 'https://orcid.org/0000-0001-5323-9558'},
  ...   dfs['person']
  ... )
  {'title': '杉山 慎 [Sugiyama Shin]', 'latin': {'family': 'Sugiyama', 'given': 'Shin'},
  'orcid': 'https://orcid.org/0000-0001-5323-9558'}
  """
  matches = []
  if person.get('orcid'):
    mask = df['orcid'].eq(person['orcid'])
    matches.append(df.index[mask])
  if person.get('email'):
    mask = (
      df['emails'].str.split(' | ', regex=False)
      .apply(lambda x: False if x is pd.NA else person['email'] in x)
    )
    matches.append(df.index[mask])
  if person.get('title'):
    mask = (
      df['matches'].str.split(' | ', regex=False)
      .apply(lambda x: False if x is pd.NA else person['title'] in x)
    )
    matches.append(df.index[mask])
  index = set()
  for indices in matches:
    index |= set(indices)
  if not index:
    return None
  if len(index) > 1:
    raise ValueError(f'Multiple matches for person {person}')
  row = df.loc[index.pop()]
  title_parts = re.fullmatch(PERSON_TITLE_REGEX, row['title']).groupdict()
  result = {
    'title': row['title'],
    'latin': {
      'family': row['latin_family'],
      'given': re.sub(
        fr"( |^){row['latin_family']}(?: |$)", '\\1',
        title_parts['latin'] or title_parts['name']
      ).strip()
    },
    'orcid': None if pd.isna(row['orcid']) else row['orcid']
  }
  if person['orcid']:
    if result['orcid'] != person['orcid']:
      raise ValueError(f'ORCID mismatch for {person} matched to {result}')
    if not result['orcid']:
      print(f"ORCID missing for {result}: {person['orcid']}")
      result['orcid'] = person['orcid']
  return result


def infer_name_parts(name: str, latin: str = None) -> dict:
  """
  Infer given and family names from a name and its Latin transliteration.

  Examples
  --------
  >>> infer_name_parts('Jakob F. Steiner')
  {'name': {'given': 'Jakob F.', 'family': 'Steiner'}, 'script': 'latin'}
  >>> infer_name_parts('Н. Г. Разумейко', 'N. G. Razumeiko')
  {'name': {'given': 'Н. Г.', 'family': 'Разумейко'},
  'latin': {'given': 'N. G.', 'family': 'Razumeiko'}, 'script': 'cyrillic'}
  >>> infer_name_parts('孙维君', 'Sun Weijun')
  {'name': {'family': '孙', 'given': '维君'},
  'latin': {'family': 'Sun', 'given': 'Weijun'}, 'script': 'chinese'}
  >>> infer_name_parts('杉山 慎', 'Sugiyama Shin')
  {'name': {'family': '杉山', 'given': '慎'},
  'latin': {'family': 'Sugiyama', 'given': 'Shin'}, 'script': 'kanji'}
  >>> infer_name_parts('スギヤマ シン', 'Sugiyama Shin')
  {'name': {'family': 'スギヤマ', 'given': 'シン'},
  'latin': {'family': 'Sugiyama', 'given': 'Shin'}, 'script': 'kana'}
  >>> infer_name_parts('안진호', 'Ahn Jinho')
  {'name': {'family': '안', 'given': '진호'},
  'latin': {'family': 'Ahn', 'given': 'Jinho'}, 'script': 'hangul'}
  """
  words = name.split(' ')
  # Latin: Last word is family name
  if latin is None:
    if (
      # more than two words and multiple consecutive words not ending with a period
      (len(words) > 2 and re.search(r'[^ \.]+ [^ \.]+(?: |$)', name))
      # last word ends with a period
      or words[-1].endswith('.')
    ):
      raise ValueError(f'Name "{name}" is amgiuous')
    return {
      'name': {'given': ' '.join(words[:-1]), 'family': words[-1]},
      'script': 'latin'
    }
  latin_words = latin.split(' ')
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
      raise ValueError(f'Chinese character name "{name} [{latin}]" is ambiguous')
    # Kanji (Japanese): First word is family name
    if len(words) == 2:
      if len(latin_words) != 2:
        raise ValueError(f'Chinese character name "{name} [{latin}]" is ambiguous')
      return {
        'name': {'family': words[0], 'given': words[1]},
        'latin': {'family': latin_words[0], 'given': latin_words[1]},
        'script': 'kanji'
      }
    # Chinese: First character of original and first word of latin is family name
    if len(latin_words) != 2:
        raise ValueError(f'Chinese character name "{name} [{latin}]" is ambiguous')
    return {
      'name': {'family': name[0], 'given': name[1:]},
      'latin': {'family': latin_words[0], 'given': ' '.join(latin_words[1:])},
      'script': 'chinese'
    }
  # Hangul (Korean): First character of original and first word of latin is family name
  if re.search(r'[\uac00-\ud7af]+', name):
    if len(words) > 1:
        raise ValueError(f'Hangul (Korean) name "{name} [{latin}]" is ambiguous')
    return {
      'name': {'family': name[0], 'given': name[1:]},
      'latin': {'family': latin_words[0], 'given': ' '.join(latin_words[1:])},
      'script': 'hangul'
    }
  # Kana (Japanese): First word is family name
  if re.search(r'[\u3040-\u30ff]+', name):
    if len(words) != 2 or len(latin_words) != 2:
      raise ValueError(f'Kana (Japanese) name "{name} [{latin}]" is ambiguous')
    return {
      'name': {'family': words[0], 'given': words[1]},
      'latin': {'family': latin_words[0], 'given': latin_words[1]},
      'script': 'kana'
    }
  raise NotImplementedError(f'Unsupported script for name "{name} [{latin}]"')


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


def render_author_list(
  personal_communication: bool = False,
  secondary_sources: bool = False,
  infer: bool = False
) -> list[str]:
  """
  Render list of authors.

  Parameters
  ----------
  personal_communication
    Include personal communication authors.
  secondary_sources
    Include secondary sources in `notes` column.
  infer
    Infer given and family names from the name and its Latin transliteration,
    if not found in the person table.
  """
  dfs = read_data()
  # Gather source ids
  source_ids, secondary = gather_source_ids(*dfs.values())
  if secondary_sources:
    source_ids |= secondary
  # Gather authors
  mask = dfs['source']['id'].isin(source_ids)
  if not personal_communication:
    mask &= dfs['source']['type'].ne('personal-communication')
  authors = (
    dfs['source']['author'][mask].str.split(' | ', regex=False)
    .dropna()
    .explode()
    .drop_duplicates()
  )
  # Parse and find people
  people = []
  missing = []
  ambiguous = []
  for person_string in authors:
    person = parse_person_string(person_string)
    found = find_person(person, dfs['person'])
    if found:
      person = found
    else:
      if infer:
        try:
          person = {**person, **infer_name_parts(person['name'], person.get('latin'))}
          if person.get('latin') is None:
            person['latin'] = person['name']
        except (ValueError, NotImplementedError):
          ambiguous.append(person_string)
      else:
        missing.append(person_string)
    people.append(person)
  if missing:
    raise ValueError('People not found:\n' + '\n'.join(missing))
  if ambiguous:
    raise ValueError('Family name could not be inferred:\n' + '\n'.join(ambiguous))
  # Sort by uppercase latin family name, latin first name
  people = sorted(people, key=lambda x: (
    strip_diacritics(x['latin']['family']).upper(),
    strip_diacritics(x['latin']['given']).upper()
  ))
  # Format person string (uppercase latin family name in title)
  people = [
    re.sub(
      fr"(^| |\[){person['latin']['family']}(\]| |$)",
      fr"\1{person['latin']['family'].upper()}\2",
      person['title']
    )
    for person in people
  ]
  # Drop duplicates
  return list(dict.fromkeys(people))


def convert_source_to_csl(source: Dict[str, str]) -> dict:
  """
  Convert source to CSL-JSON.

  Names of people are currently represented with their full names only:
  `{"literal": "Name"}`.
  Extracting given and family names could be achieved with the following heuristics,
  depending on the writing system:

  * Latin: Assume last word is the family name
    (e.g. "Jakob F. Steiner" -> {"family": "Steiner", "given": "Jakob F."}).
    Although this assumption is valid in most cases, it is wrong when
    particles (e.g. "Ward J. J. Van Pelt", "Roderik S. W. van de Wal"),
    suffixes (e.g. "E. Calvin Alexander Jr."),
    or double family names ("Guillermo Cobos Campos") are present.
  * Cyrillic: Assume last word of the original and transliteration is the
    family name (e.g. "Н. Г. Разумейко [N. G. Razumeiko]" ->
    {"family": "Иванов [Razumeiko]", "given": "Н. Г. [N. G.]"}).
  * Chinese: Assume first character and word of the original and
    transliteration, respectively, is the family name (e.g. "孙维君 [Sun Weijun]" ->
    "family": "孙 [Sun]", "given": "Weijun [维君]").
  * Hangul: Same as for Chinese (e.g. "안진호 [Ahn Jinho]" ->
    {"family": "안 [Ahn]", "given": "진호 [Jinho]"}).
  """
  csl = {
    'id': source['id'],
    'author': [
      {'literal': author}
      for author in source['author'].split(' | ')
    ],
    'issued': {'date-parts': [[int(source['year'])]]},
    'type': source['type'],
    'title': source['title'],
    'URL': source['url'],
    'language': source['language'],
    'container-title': source['container_title'],
    'volume': source['volume'],
    'issue': source['issue'],
    'page': source['page'],
    'version': source['version'],
    'editor': [
      {'literal': editor}
      for editor in source['editor'].split(' | ')
    ] if source['editor'] else None,
    'collection-title': source['collection_title'],
    'collection-number': source['collection_number'],
    'publisher': source['publisher']
  }
  # Remove None values
  return {key: value for key, value in csl.items() if value is not None}


def render_sources_as_csl() -> str:
  """Render sources as CSL-JSON."""
  sources = pd.read_csv(DATA_PATH.joinpath('source.csv'), dtype='string')
  sources.replace({pd.NA: None}, inplace=True)
  csl = [convert_source_to_csl(source) for source in sources.to_dict(orient='records')]
  return json.dumps(csl, indent=2, ensure_ascii=False)


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


# Generate command line interface
if __name__ == '__main__':
  fire.Fire()
