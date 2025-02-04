from pathlib import Path
import sys

ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))
import glenglat
import dotenv


# ---- Load environment ----

dfs = glenglat.read_data()
package = glenglat.read_package()
dotenv.load_dotenv(ROOT.joinpath('.env'))


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

DIGITIZER_FILE_REGEX = (
  r'^sources\/(?P<source_id>[^\/]+)\/' +
  r'(?P<borehole_id>[0-9]+)(?:-(?P<max_borehole_id>[0-9]+))?' +
  r'_(?:(?P<profile_id>[0-9]+)(?:-(?P<max_profile_id>[0-9]+))?|(?P<depth>[\-0-9\.]+)m)' +
  r'(?:_(?P<suffix>.+))?\.xml$'
)
"""Regular expression for digitizer file paths."""

DATA_SUBDIR_REGEX = r'^[a-z]+[0-9]{4}[a-z]?(?:-[a-z0-9]+)*$'
"""Regular expression for data subdirectory names."""
