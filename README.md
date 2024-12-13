# `glenglat`: Global englacial temperature database

| Download & Cite | [![DOI](https://zenodo.org/badge/doi/10.5281/zenodo.11516611.svg)](https://zenodo.org/doi/10.5281/zenodo.11516611) |
| :- | :- |
[Tutorial notebook](tutorial.ipynb) | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/mjacqu/glenglat/blob/main/tutorial.ipynb)
Version history | [![GitHub Release](https://img.shields.io/github/v/release/mjacqu/glenglat?label=latest)](https://github.com/mjacqu/glenglat/releases)
Tests | [![Frictionless](https://github.com/mjacqu/glenglat/actions/workflows/frictionless.yaml/badge.svg)](https://github.com/mjacqu/glenglat/actions/workflows/frictionless.yaml) [![Pytest](https://github.com/mjacqu/glenglat/actions/workflows/pytest.yaml/badge.svg)](https://github.com/mjacqu/glenglat/actions/workflows/pytest.yaml)

_Our paper is currently in public review at [Earth System Science Data](https://essd.copernicus.org). Preview it and consider reviewing it at https://essd.copernicus.org/preprints/essd-2024-249/!_

<!-- <for-zenodo> -->
Open-access database of englacial temperature measurements compiled from data submissions and published literature. It is developed on [GitHub](https://github.com/mjacqu/glenglat) and published to [Zenodo](https://doi.org/10.5281/zenodo.11516611).

## Dataset structure

The dataset adheres to the Frictionless Data [Tabular Data Package](https://specs.frictionlessdata.io/tabular-data-package) specification. The metadata in [`datapackage.yaml`](datapackage.yaml) describes, in detail, the contents of the tabular data files in the [`data`](data) folder:

* [`source.csv`](data/source.csv): Description of each data source (either a personal communication or the reference to a published study).
* [`borehole.csv`](data/borehole.csv): Description of each borehole (location, elevation, etc), linked to `source.csv` via `source_id` and less formally via source identifiers in `notes`.
* [`profile.csv`](data/profile.csv): Description of each profile (date, etc), linked to `borehole.csv` via `borehole_id` and to `source.csv` via `source_id` and less formally via source identifiers in `notes`.
* [`measurement.csv`](data/measurement.csv): Description of each measurement (depth and temperature), linked to `profile.csv` via `borehole_id` and `profile_id`.

For boreholes with many profiles (e.g. from automated loggers), pairs of `profile.csv` and `measurement.csv` are stored separately in subfolders of [`data`](data) named `{source.id}-{glacier}`, where `glacier` is a simplified and kebab-cased version of the glacier name (e.g. [`flowers2022-little-kluane`](data/flowers2022-little-kluane)).

### Supporting information

The folder [`sources`](sources), available on [GitHub](https://github.com/mjacqu/glenglat) but omitted from dataset releases on [Zenodo](https://doi.org/10.5281/zenodo.11516611), contains subfolders (with names matching column `source.id`) with files that document how and from where the data was extracted.
<!-- </for-zenodo> -->

Files with a `.png`, `.jpg`, or `.pdf` extension are figures, tables, maps, or text from the publication. Pairs of files with `.pgw` and `.{png|jpg}.aux.xml` extensions georeference a `.{png|jpg}` image, and files with `.geojson` extension are the subsequently-extracted spatial coordinates. Files with an `.xml` extension document how numeric values were extracted from maps and figures using [Plot Digitizer](https://plotdigitizer.sourceforge.net). Of these, digitized temperature profiles are named `{borehole.id}_{profile.id}{suffix}` where `borehole.id` and `profile.id` are either a single value or a hyphenated range (e.g. `1-8`). Those without the optional `suffix` use `temperature` and `depth` as axis names. Those with a `suffix` are unusual cases which, for example, may be part of a series (e.g. `_lower`) or use a non-standard axis (e.g. `_date`).

_The repository's [license](LICENSE.md) does not extend to figures, tables, maps, or text extracted from publications. These are included in the `sources` folder for transparency and reproducibility._

## Submitter guide

*We welcome submissions of new data as well as corrections and improvements to existing data.*

To submit data, send an email to jacquemart@vaw.baug.ethz.ch or open a GitHub [issue](https://github.com/mjacqu/glenglat/issues). Please structure your data as either comma-separated values (CSV) files (`borehole.csv` and `measurement.csv`) or as an Excel file (with sheets `borehole` and `measurement`). The required and optional columns for each table are described below and in the submission metadata: [`submission/datapackage.yaml`](submission/datapackage.yaml). Consider using our handy Excel template: [`submission/template.xlsx`](submission/template.xlsx)! For corrections and improvements to existing data, you can also describe the changes that need to be made or make the changes directly via a GitHub [pull request](https://github.com/mjacqu/glenglat/pulls).

### Authorship policy

By submitting data to glenglat, you agree to be listed as a contributor in the metadata and have your original submission preserved in the `sources` folder. You will also be invited to become a co-author on the next dataset release (with the option to opt-out or suggest someone in your stead) and asked to confirm your name, affiliation, funding sources, and that your data was correctly integrated into glenglat. Unless you opt-out, you will remain an author on all subsequent releases in which your data still appears.

<!-- <submission-format> -->
### `borehole`

| name | description | type | constraints |
| - | - | - | - |
| `id` | Unique identifier. | integer | required: True<br>unique: True<br>minimum: 1 |
| `glacier_name` | Glacier or ice cap name (as reported). | string | required: True<br>pattern: `[^\s]+( [^\s]+)*` |
| `glims_id` | Global Land Ice Measurements from Space (GLIMS) glacier identifier. | string | pattern: `G[0-9]{6}E[0-9]{5}[NS]` |
| `latitude` | Latitude (EPSG 4326). | number [degree] | required: True<br>minimum: -90<br>maximum: 90 |
| `longitude` | Longitude (EPSG 4326). | number [degree] | required: True<br>minimum: -180<br>maximum: 180 |
| `elevation` | Elevation above sea level. | number [m] | required: True<br>maximum: 9999.0 |
| `mass_balance_area` | Mass balance area.<br>- ablation: Ablation area<br>- equilibrium: Near the equilibrium line<br>- accumulation: Accumulation area | string | enum: ['ablation', 'equilibrium', 'accumulation'] |
| `label` | Borehole name (e.g. as labeled on a plot). | string |  |
| `date_min` | Begin date of drilling, or if not known precisely, the first possible date (e.g. 2019 → 2019-01-01). | date | format: `%Y-%m-%d`<br> |
| `date_max` | End date of drilling, or if not known precisely, the last possible date (e.g. 2019 → 2019-12-31). | date | format: `%Y-%m-%d`<br> |
| `drill_method` | Drilling method.<br>- mechanical: Push, percussion, rotary<br>- thermal: Hot point, electrothermal, steam<br>- combined: Mechanical and thermal | string | enum: ['mechanical', 'thermal', 'combined'] |
| `ice_depth` | Starting depth of continuous ice. Infinity (INF) indicates that only snow, firn, or intermittent ice was reached. | number [m] |  |
| `depth` | Total borehole depth (not including drilling in the underlying bed). | number [m] |  |
| `to_bed` | Whether the borehole reached the glacier bed. | boolean |  |
| `temperature_uncertainty` | Estimated temperature uncertainty (as reported). | number [°C] |  |
| `notes` | Additional remarks about the study site, the borehole, or the measurements therein. Literature references should be formatted as {url} or {author} {year} ({url}). | string | pattern: `[^\s]+( [^\s]+)*` |
| `investigators` | Names of people and/or agencies who performed the work, as a pipe-delimited list. Each entry should be in the format {person} ({agencies}) [{notes}], where either person or at least one (semicolon-delimited) agencies is required. | string | pattern: `[^\s]+( [^\s]+)*` |
| `funding` | Funding sources as a pipe-delimited list. Each entry should be in the format {funder} [{rorid}] > {award} [{number}] ({url}), where only the funder is required and rorid is the funder's ROR (https://ror.org) ID (e.g. 01jtrvx49). | string | pattern: `[^\s]+( [^\s]+)*` |

### `measurement`

| name | description | type | constraints |
| - | - | - | - |
| `borehole_id` | Borehole identifier. | integer | required: True |
| `depth` | Depth below the glacier surface. | number [m] | required: True |
| `temperature` | Temperature. | number [°C] | required: True |
| `date_min` | Measurement date, or if not known precisely, the first possible date (e.g. 2019 → 2019-01-01). | date | format: `%Y-%m-%d`<br> |
| `date_max` | Measurement date, or if not known precisely, the last possible date (e.g. 2019 → 2019-12-31). | date | format: `%Y-%m-%d`<br>required: True |
| `time` | Measurement time. | time | format: `%H:%M:%S`<br> |
| `utc_offset` | Time offset relative to Coordinated Universal Time (UTC). | number [h] |  |
| `equilibrated` | Whether temperatures have equilibrated following drilling. | boolean |  |
<!-- </submission-format> -->

### Validation

You can validate your CSV files (`borehole.csv` and `measurement.csv`) before submitting them using the [frictionless](https://github.com/frictionlessdata/framework) Python package.

1. Clone this repository.

   ```sh
   git clone https://github.com/mjacqu/glenglat.git
   cd glenglat
   ```

2. Either install the `glenglat-submission` Python environment (with `conda`):

   ```sh
   conda env create --file submission/environment.yaml
   conda activate glenglat-submission
   ```

   Or install `frictionless` into an existing environment (with `pip`):

   ```sh
   pip install "frictionless~=5.13"
   ```

3. Validate, fix any reported issues, and rejoice! (`path/to/csvs` is the folder containing your CSV files)

   ```sh
   python submission/validate.py path/to/csvs
   ```

## Developer guide

### Install dependencies

Clone this repository.

```sh
git clone https://github.com/mjacqu/glenglat
cd glenglat
```

Install the `glenglat` Python environment with [`conda`](https://docs.conda.io) (or the faster [`mamba`](https://mamba.readthedocs.io)):

```sh
conda env create --file environment.yaml
conda activate glenglat
```

or update it if it already exists:

```sh
conda env update --file environment.yaml
conda activate glenglat
```

Copy [`.env.example`](.env.example) to `.env` and set the (optional) environment variables.

```sh
cp .env.example .env
```

* `GLIMS_PATH`: Path to a [GeoParquet](https://geoparquet.org) file of glacier outlines from the [GLIMS](https://www.glims.org/) dataset with columns `geometry` (glacier outline) and `glac_id` (glacier id).
* `ZENODO_SANDBOX_ACCESS_TOKEN`: Access token for the [Zenodo Sandbox](https://sandbox.zenodo.org) (for testing). Register an account (if needed), then navigate to [Account > Settings > Applications](https://sandbox.zenodo.org/account/settings/applications/) > Personal access tokens > New token and select scopes `deposit:actions` and `deposit:write`.
* `ZENODO_ACCESS_TOKEN`: Access token for [Zenodo](https://sandbox.zenodo.org). Follow the same steps as above, but on the [real Zenodo](https://zenodo.org/account/settings/applications/).

### Run tests

Run the basic (`frictionless`) tests.

```sh
frictionless validate datapackage.yaml
```

Run the custom (`pytest`) tests in the [`tests`](tests) folder.

```sh
pytest
```

An optional test checks that `borehole.glims_id` is consistent with borehole coordinates. To run, install `geopandas` and `pyarrow` and set the `GLIMS_PATH` environment variable before calling `pytest`.

```sh
conda install -c conda-forge geopandas=0.13 pyarrow
pytest
```

Slow tests can be skipped by using the `--fast` option.

```sh
pytest --fast
```

### Maintain the repository

The [`glenglat.py`](glenglat.py) module contains functions used to maintain the repository. They can be run from the command line as `python glenglat.py {function}`.

To update all generated [`submission`](submission) instructions:

```sh
python glenglat.py write_submission
```

This executes several functions:

* `write_submission_yaml`: Builds [`submission/datapackage.yaml`](submission/datapackage.yaml) from [`datapackage.yaml`](datapackage.yaml).
* `write_submission_md`: Updates tables in this [`README.md`](README.md) from [`submission/datapackage.yaml`](submission/datapackage.yaml).
* `write_submission_xlsx`: Builds [`submission/template.xlsx`](submission/template.xlsx) from [`submission/datapackage.yaml`](submission/datapackage.yaml).

To write a subset of the data (e.g. to send to a contributor for review), use `write_subset`. The selection can be made by curator name (`--curator`) or source `id` (`--source`), optionally including secondary sources mentioned in `notes` columns (`--secondary_sources`), and the output can include source directories (`--source_files`).

```sh
python glenglat.py write_subset subsets/vantricht --curator='Lander Van Tricht' --secondary_sources --source_files
```

### Publish to Zenodo

The [`zenodo.py`](zenodo.py) module contains functions used to prepare and publish the data to [Zenodo](https://zenodo.org). They can be run from the command line as `python zenodo.py {function}`.

To publish (as a draft) to the [Zenodo Sandbox](https://zenodo.org), set the `ZENODO_SANDBOX_ACCESS_TOKEN` environment variable and run:

```sh
python zenodo.py publish_to_zenodo
```

To publish (as a draft) to [Zenodo](https://zenodo.org), set the `ZENODO_ACCESS_TOKEN` environment variable, run the same command with `--sandbox False`, and follow the instructions. It will first check that the repository is on the `main` branch, has no uncommitted changes, that all tests pass, and that a commit has not already been tagged with the current datapackage version (function `is_repo_publishable`).

```sh
python zenodo.py publish_to_zenodo --sandbox False
```

The publish process executes several functions:

* `build_metadata_as_json`: Builds a final `build/datapackage.json` from [`datapackage.yaml`](datapackage.yaml) with filled placeholders for `id` (doi), `created` (timestamp), and `temporalCoverage` (measurement date range).
* `build_zenodo_readme`: Builds `build/README.md` from [`datapackage.yaml`](datapackage.yaml).
* `build_for_zenodo`: Builds a glenglat release as `build/glenglat-v{version}.zip` from new `build/datapackage.json` and `build/README.md` (see above), and unchanged [`LICENSE.md`](LICENSE.md) and [`data/`](data). The zip archive is extracted to `build/glenglat-v{version}` for review.
* `render_zenodo_metadata`: Prepares a metadata dictionary for upload to Zenodo.
