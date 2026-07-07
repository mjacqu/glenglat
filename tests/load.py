from pathlib import Path
import sys

import dotenv

ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))
import glenglat
import zenodo


# ---- Load environment ----

dfs = glenglat.read_data()
package = glenglat.read_package()
dotenv.load_dotenv(ROOT.joinpath('.env'))
