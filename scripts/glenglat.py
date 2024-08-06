from collections import defaultdict
from pathlib import Path
from typing import Dict

import pandas as pd


def read_data():
  """
  Read data from CSV files.

  __path__ column is added to each DataFrame with the path to the CSV file.
  """
  dfs: Dict[str, pd.DataFrame] = defaultdict(dict)
  root = Path(__file__).parent.parent
  for path in root.glob('data/**/*.csv'):
    dfs[path.stem][str(path.relative_to(root))] = pd.read_csv(path)
  for key, values in dfs.items():
    for path, df in values.items():
      # Include path to file in __path__ column
      df['__path__'] = path
    dfs[key] = pd.concat(values, ignore_index=True).convert_dtypes()
  return dfs
