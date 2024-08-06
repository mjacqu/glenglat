import frictionless

import sys
sys.path.append('scripts')
import glenglat


# ---- Load data ----

dfs = glenglat.read_data()


# ---- Load metadata ----

package = frictionless.Package('datapackage.yaml')


# ---- Constants ----

ochar = r'[^\[\]\s]'
ichar = r'[^\[\]]'
phrase = fr'{ochar}{ichar}*{ochar}'
TRANSLATED_REGEX = fr'^{phrase}(?: \[{phrase}\])?$'
"""Regular expression for translated text."""

TRANSLATED_COLUMNS: list[tuple[str, str]] = [
  ('source', 'title'),
  ('source', 'container_title'),
  ('source', 'collection_title'),
  ('source', 'publisher'),
  ('borehole', 'glacier_name')
]
"""Columns that contain translated text (table, column)."""

# Person and ORCID patterns
ochar = r'[^\(\)\[\]\|\s]'
ichar = r'[^\(\)\[\]\|]'
phrase = fr'{ochar}{ichar}*{ochar}'
orcid = r'[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]'
person = fr'{phrase}(?: \[{phrase}\])?(?: \({orcid}\))?'
PERSON_REGEX = fr'(?P<title>{phrase}(?: \[{phrase}\])?)(?: \((?P<path>{orcid})\))?'
"""Regular expression for a person."""

PEOPLE_REGEX = fr'^({person})(?: \| ({person}))*$'
"""Regular expression for people."""

PEOPLE_COLUMNS: list[tuple[str, str]] = [
  ('source', 'author'),
  ('source', 'editor'),
  ('borehole', 'curator')
]
"""Columns that contain people (table, column)."""

DEFAULT_AXIS_NAMES = {'temperature', 'depth'}
"""Default digitized axis names."""

SPECIAL_AXIS_NAMES = {'elevation', 'days', 'year'}
"""Special digitized axis names."""

SOURCE_ID_REGEX = r'(?:^|\s|\()([a-z]+[0-9]{4}[a-z]?)(?:$|\s|\)|,|\.)'
"""Regular expression for extracting source ids from notes."""

DIGITIZER_FILE_REGEX = (
  r'^sources\/(?P<source_id>[^\/]+)\/' +
  r'(?P<borehole_id>[0-9]+)(-(?P<max_borehole_id>[0-9]+))?_' +
  r'(?P<profile_id>[0-9]+)(-(?P<max_profile_id>[0-9]+))?' +
  r'(_(?P<suffix>.+))?\.xml$'
)
"""Regular expression for digitizer file paths."""

DATA_SUBDIR_REGEX = r'^[a-z]+[0-9]{4}[a-z]?(?:-[a-z0-9]+)*$'
"""Regular expression for data subdirectory names."""
