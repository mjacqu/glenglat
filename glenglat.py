from collections import defaultdict
import datetime
import json
from pathlib import Path
import sys
from typing import Dict, Union
import yaml
import zipfile

import frictionless
import jinja2
import pandas as pd
import tablecloth.excel


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
  """Render a dictionary as YAML string."""
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

def read_data() -> Dict[str, pd.DataFrame]:
  """
  Read all data files and concatenate them by table name.

  A __path__ column is added to each DataFrame with the path to the file.
  """
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
      path, dtype=dtypes[path.stem]
    )
  for key, values in dfs.items():
    for path, df in values.items():
      # Include path to file in __path__ column
      df['__path__'] = pd.Series(path, index=df.index, dtype='string')
    dfs[key] = pd.concat(values, ignore_index=True)
  return dict(dfs)


# ---- Write functions ----

def write_release_zip() -> Path:
  """
  Write a zip archive of glenglat data as `build/glenglat-v{version}.zip`.

  Returns:
    Path to the zip archive.
  """
  # List files in desired order (although order is not respected by Zenodo display)
  files = [
    'README.md',
    'LICENSE.md',
    'datapackage.yaml',
    'data/source.csv',
    'data/borehole.csv',
    'data/profile.csv',
    'data/measurement.csv'
  ]
  for path in sorted(DATA_PATH.iterdir()):
    if path.is_dir():
      files += [
        str(path.relative_to(ROOT).joinpath(file))
        for file in ('profile.csv', 'measurement.csv')
      ]
  # Look up version
  metadata = read_metadata()
  version = metadata['version']
  # Create zip archive
  path = ROOT.joinpath(f'build/glenglat-v{version}.zip')
  with zipfile.ZipFile(path, 'w') as zip:
    for file in files:
      zip.write(filename=ROOT.joinpath(file), arcname=file)
  return path


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
    'Literature references should be formatted as `{url}` or `{author} {year} ({url})`.'
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
  # --- Drop source and profile tables ---
  package.resources = [
    resource for resource in package.resources
    if resource.name not in ['source', 'profile']
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


# ---- Citation Syntax Language (CSL) ----

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


# Run function from command line and print result
if __name__ == '__main__':
  args = sys.argv
  # args[0]: Current file
  # args[1]: Function name
  result = globals()[args[1]]()
  if result is not None:
    print(result)
