from pathlib import Path
import xml.etree.ElementTree as ET
import re

import pandas as pd
import pytest

from load import (
  dfs,
  DEFAULT_AXIS_NAMES,
  SPECIAL_AXIS_NAMES,
  SOURCE_ID_REGEX,
  DIGITIZER_FILE_REGEX
)


# ---- Derived variables ----

# All source ids
source_ids = set(dfs['source']['id'])
# Source ids used as measurement origin
primary_source_ids = set(dfs['borehole']['source_id'])
# Source ids cited in borehole notes
secondary_source_ids = set(dfs['borehole']['notes'].str.extractall(SOURCE_ID_REGEX)[0])

# Paths and suffix of all digitized profiles
digitizer_paths = []
pattern = re.compile(DIGITIZER_FILE_REGEX)
results = []
for path in Path('sources').glob('**/*.xml'):
  match = pattern.match(str(path))
  if not match:
    continue
  parsed = match.groupdict()
  digitizer_paths.append((path, parsed['suffix']))
  parsed['max_borehole_id'] = parsed['max_borehole_id'] or parsed['borehole_id']
  parsed['max_profile_id'] = parsed['max_profile_id'] or parsed['profile_id']
  borehole_ids = range(int(parsed['borehole_id']), int(parsed['max_borehole_id']) + 1)
  for borehole_id in borehole_ids:
    profile_ids = range(int(parsed['profile_id']), int(parsed['max_profile_id']) + 1)
    for profile_id in range(int(parsed['profile_id']), int(parsed['max_profile_id']) + 1):
      results.append({
        'source_id': parsed['source_id'],
        'borehole_id': borehole_id,
        'profile_id': profile_id,
        'suffix': parsed['suffix']
      })

# All digitizer files
digitizer_files = pd.DataFrame(results)
temp = (
  dfs['profile'][['borehole_id', 'id']]
  .rename(columns={'id': 'profile_id'})
  .merge(dfs['borehole'][['source_id', 'id', 'measurement_origin']]
  .rename(columns={'id': 'borehole_id'}), how='left')
)
temp = temp[temp['measurement_origin'].eq('digitized')]

# All digitized profiles
digitized_profiles = temp[['source_id', 'borehole_id', 'profile_id']].drop_duplicates()


# ---- Tests ----

def test_sources_are_used() -> None:
  """All sources are used in borehole.source_id or borehole.notes."""
  invalid = source_ids - (primary_source_ids.union(secondary_source_ids))
  assert not invalid, invalid


def test_source_ids_in_borehole_notes_exist() -> None:
  """All source ids in borehole notes exist."""
  invalid = secondary_source_ids - source_ids
  assert not invalid, invalid


def test_source_dirs_match_source_ids() -> None:
  """All source directories match a source id."""
  source_paths = [path.name for path in Path('sources').iterdir() if path.is_dir()]
  invalid = set(source_paths) - source_ids
  assert not invalid, invalid


def test_digitized_profiles_match_at_most_one_file_without_a_suffix() -> None:
  """Digitized profiles match <= 1 files without a suffix."""
  mask = digitizer_files['suffix'].isnull()
  invalid = (
    digitizer_files.loc[mask, ['source_id', 'borehole_id', 'profile_id']]
    .duplicated(keep=False)
  )
  assert not invalid.any(), digitizer_files[mask][invalid]


def test_digitized_profiles_match_digitizer_files() -> None:
  """Digitized profiles and digitizer files have the same ids."""
  files = pd.MultiIndex.from_frame(
    digitizer_files[digitized_profiles.columns].drop_duplicates().astype('string'),
  ).sort_values()
  profiles = pd.MultiIndex.from_frame(digitized_profiles.astype('string')).sort_values()
  pd.testing.assert_index_equal(files, profiles)


@pytest.mark.parametrize('path, suffix', digitizer_paths)
def test_digitizer_file_is_valid(path: Path, suffix: str) -> None:
  """Digitizer file is valid."""
  tree = ET.parse(path)
  root = tree.getroot()
  # Image file
  image = root.find('image')
  assert image is not None, 'Missing <image>'
  assert 'file' in image.attrib, 'Missing <image.file>'
  file = image.attrib['file']
  assert file not in [None, '', 'none', 'null'], f'Invalid <image.file>: {file}'
  filepath = path.parent / file
  assert filepath.is_file(), f'Image does not exist: {filepath}'
  # Axes
  axes = root.find('axesnames')
  assert axes is not None, 'Missing <axesnames>'
  assert 'x' in axes.attrib, 'Missing <axisnames.x>'
  assert 'y' in axes.attrib, 'Missing <axisnames.y>'
  names = {axes.attrib['x'], axes.attrib['y']}
  valid_names = DEFAULT_AXIS_NAMES
  if suffix:
    valid_names = valid_names.union(SPECIAL_AXIS_NAMES)
  assert not (names - valid_names), f'Unexpected axes names: {names}'
