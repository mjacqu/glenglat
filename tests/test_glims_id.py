import os

try:
  import geopandas as gpd
except ImportError:
  gpd = None
import pandas as pd
import pytest

from load import dfs

# Determine whether tests can be run
GLIMS_PATH = os.environ.get('GLIMS_PATH')
if not GLIMS_PATH:
  pytest.skip(
    (
      'Set the GLIMS_PATH environment variable to run the tests: '
      'GLIMS_PATH=path/to/glims.parquet pytest'
    ),
    allow_module_level=True
  )
elif gpd is None:
  pytest.skip(
    (
      'Install geopandas to run the tests: '
      'pip install geopandas OR conda install -c conda-forge geopandas'
    ),
    allow_module_level=True
  )


def test_borehole_coordinates_match_glims_id() -> None:
  """Borehole latitude, longitude match the GLIMS ID."""
  df = dfs['borehole'].set_index('id')
  points = gpd.points_from_xy(df['longitude'], df['latitude'], crs='EPSG:4326')
  sindex = points.sindex
  # Load GLIMS polygons
  glims = gpd.read_parquet(GLIMS_PATH, columns=['glac_id', 'geometry'])
  # Intersect with GLIMS Polygons
  poly_idx, point_idx = sindex.query(glims.geometry, 'contains')
  df['glims_ids'] = pd.DataFrame({
    'id': df.index[point_idx].values,
    'glims_ids': glims['glac_id'].iloc[poly_idx].values
  }).drop_duplicates().groupby('id')['glims_ids'].agg(list)
  df['glims_ids'] = df['glims_ids'].fillna('').apply(list)
  # Evaluate matches
  valid = df.apply(
    lambda row: (
      (pd.isna(row['glims_id']) and not row['glims_ids'])
      or not pd.isna(row['glims_id']) and (
        not row['glims_ids'] or row['glims_id'] in row['glims_ids']
      )
    ),
    axis=1
  )
  assert valid.all(), df.loc[
    ~valid, ['glacier_name', 'latitude', 'longitude', 'glims_ids']
  ]
