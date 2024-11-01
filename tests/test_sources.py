from pathlib import Path
import xml.etree.ElementTree as ET
import re
import warnings

import numpy as np
import pandas as pd
import pytest

from load import (
  glenglat,
  dfs,
  DEFAULT_AXIS_NAMES,
  SPECIAL_AXIS_NAMES,
  DIGITIZER_FILE_REGEX,
  ROOT
)


# ---- Derived variables ----

# All source ids
source_ids = set(dfs['source']['id'])
# Source ids used as measurement origin
# Source ids cited in notes
primary_source_ids, secondary_source_ids = glenglat.gather_source_ids(
  dfs['borehole'], dfs['profile']
)

# Paths and suffix of all digitized profiles
digitizer_paths = []
pattern = re.compile(DIGITIZER_FILE_REGEX)
results = []
for path in ROOT.joinpath('sources').glob('**/*.xml'):
  match = pattern.match(str(path.relative_to(ROOT)))
  if not match:
    continue
  parsed = match.groupdict()
  parsed['borehole_id'] = int(parsed['borehole_id'])
  parsed['profile_id'] = int(parsed['profile_id'])
  parsed['max_borehole_id'] = int(parsed['max_borehole_id'] or parsed['borehole_id'])
  parsed['max_profile_id'] = int(parsed['max_profile_id'] or parsed['profile_id'])
  digitizer_paths.append((path, parsed))
  borehole_ids = range(parsed['borehole_id'], parsed['max_borehole_id'] + 1)
  for borehole_id in borehole_ids:
    profile_ids = range(parsed['profile_id'], parsed['max_profile_id'] + 1)
    for profile_id in range(parsed['profile_id'], parsed['max_profile_id'] + 1):
      results.append({
        'source_id': parsed['source_id'],
        'borehole_id': borehole_id,
        'profile_id': profile_id,
        'suffix': parsed['suffix']
      })

# All digitizer files
digitizer_files = pd.DataFrame(results)
temp = dfs['profile'].rename(columns={'id': 'profile_id'})
temp = temp[temp['measurement_origin'].eq('digitized')]

# All digitized profiles
digitized_profiles = temp[['source_id', 'borehole_id', 'profile_id']].drop_duplicates()


# ---- Tests ----

def test_sources_are_used() -> None:
  """All sources are used in *.source_id or borehole.notes."""
  invalid = source_ids - (primary_source_ids.union(secondary_source_ids))
  assert not invalid, invalid


def test_source_ids_in_borehole_notes_exist() -> None:
  """All source ids in borehole notes exist."""
  invalid = secondary_source_ids - source_ids
  assert not invalid, invalid


def test_source_dirs_match_source_ids() -> None:
  """All source directories match a source id."""
  source_paths = [
    path.name for path in ROOT.joinpath('sources').iterdir() if path.is_dir()
  ]
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
  assert files.difference(profiles).empty, files.difference(profiles)
  assert profiles.difference(files).empty, profiles.difference(files)


# Indexed measurements (for speed)
indexed_measurements = (
  dfs['measurement'].set_index(['borehole_id', 'profile_id'])
)


@pytest.mark.parametrize('path, parsed', digitizer_paths)
def test_digitizer_file_is_valid(path: Path, parsed: dict) -> None:
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
  if parsed['suffix']:
    valid_names = valid_names.union(SPECIAL_AXIS_NAMES)
  assert not (names - valid_names), f'Unexpected axes names: {names}'
  # Profile
  if (
    parsed['max_borehole_id'] != parsed['borehole_id'] or
    parsed['max_profile_id'] != parsed['profile_id'] or
    parsed['suffix']
  ):
    return None
  points = root.findall('point')
  df = pd.DataFrame([point.attrib for point in points]).astype(float)
  assert not df.empty, 'No points found'
  assert (df['n'].sort_values() == df['n']).all(), 'Points are not sorted'
  assert df[['dx', 'dy']].notnull().all(axis=None), 'Points contain null values'
  columns = ['dx', 'dy']
  if axes.attrib['x'] == 'temperature':
    columns = columns[::-1]
  xml_data = df[columns]
  # Ignore performance warning due to unsorted index
  with warnings.catch_warnings():
    warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)
    csv_data = (
      indexed_measurements
      .loc[(parsed['borehole_id'], parsed['profile_id']), ['depth', 'temperature']]
    )
  # Determine rounding level from CSV data
  for index in range(2):
    decimals = (
      csv_data.iloc[:, index].astype(str)
      .str.replace(r'^[^\.]+\.0?', '', regex=True)
      .str.len()
      .max()
    )
    xml_data.iloc[:, index] = xml_data.iloc[:, index].round(decimals)
  np.testing.assert_array_almost_equal(csv_data, xml_data, decimal=2)
