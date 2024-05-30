# `glenglat`: Global englacial temperature database

[![Frictionless](https://github.com/mjacqu/glenglat/actions/workflows/frictionless.yaml/badge.svg)](https://repository.frictionlessdata.io/pages/dashboard.html?user=mjacqu&repo=glenglat&flow=frictionless)

Open-access database of englacial temperature measurements compiled from published literature and submissions.

## Data structure

The dataset adheres to the Frictionless Data [Tabular Data Package](https://specs.frictionlessdata.io/tabular-data-package) specification.
The metadata in [`datapackage.yaml`](datapackage.yaml) describes, in detail, the contents of the tabular data files:

- [`data/source.csv`](data/source.csv): Description of each data source (either a direct contribution or the reference to a published study).
- [`data/borehole.csv`](data/borehole.csv): Description of each borehole (location, elevation, etc), linked to `source.csv` via `source_id` and less formally via source identifiers in `notes`.
- [`data/profile.csv`](data/profile.csv): Description of each profile (date and time), linked to `borehole.csv` via `borehole_id` and to `source.csv` via `source_id`.
- [`data/measurement.csv`](data/measurement.csv): Description of each measurement (depth and temperature), linked to `profile.csv` via `borehole_id` and `profile_id`.

For boreholes with many profiles (e.g. from automated loggers), pairs of `profile.csv` and `measurement.csv` are stored separately in subfolders of [`data`](data) named `{source.id}-{glacier}`, where `glacier` is a simplified and kebab-cased version of the glacier name (e.g. [`flowers2022-little-kluane`](data/flowers2022-little-kluane)).

### Supporting information

Folder [`sources`](sources) contains subfolders (with names matching column `source.id`) with files that document how and from where the data was extracted. Files with a `.png`, `.jpg`, or `.pdf` extension are figures, tables, maps, or text from the publication. Pairs of files with `.pgw` and `.{png|jpg}.aux.xml` extensions georeference a `.{png|jpg}` image, and files with `.geojson` extension are the subsequently-extracted spatial coordinates. Files with an `.xml` extension document how numeric values were extracted from maps and figures using Plot Digitizer (https://plotdigitizer.sourceforge.net). Of these, digitized temperature profiles are named `{borehole.id}_{profile.id}{suffix}` where `borehole.id` and `profile.id` are either a single value or a hyphenated range (e.g. `1-8`). Those without the optional `suffix` use `temperature` and `depth` as axis names. Those with a `suffix` are unusual cases which, for example, may be part of a series (e.g. `_lower`) or use a non-standard axis (e.g. `_date`).

## How to contribute

To contribute data, send an email to jacquemart@vaw.baug.ethz.ch. Please structure your data as either comma-separated values (CSV) files (`borehole.csv` and `measurement.csv`) or as an Excel file (with sheets `borehole` and `measurement`). The required and optional columns for each table are described below and in the submission metadata: [`contribute/datapackage.yaml`](contribute/datapackage.yaml). Consider using our handy Excel template: [`contribute/template.xlsx`](contribute/template.xlsx)!

*Note: We also welcome submissions of data that have already been digitized, as they allow us to assess the accuracy of the digitization process.*

<!-- <contributor-format> -->
### `borehole`

| name | description | type | constraints |
| - | - | - | - |
| `id` | Unique identifier. | integer | required: True<br>unique: True<br>minimum: 1 |
| `glacier_name` | Glacier or ice cap name (as reported). | string | required: True<br>pattern: `[^\s]+( [^\s]+)*` |
| `glims_id` | Global Land Ice Measurements from Space (GLIMS) glacier identifier. | string | pattern: `G[0-9]{6}E[0-9]{5}[NS]` |
| `latitude` | Latitude (EPSG 4326). | number | required: True<br>minimum: -90<br>maximum: 90 |
| `longitude` | Longitude (EPSG 4326). | number | required: True<br>minimum: -180<br>maximum: 180 |
| `elevation` | Elevation above sea level. | number | required: True<br>maximum: 9999.0 |
| `label` | Borehole name (e.g. as labeled on a plot). | string |  |
| `date_min` | Begin date of drilling, or if not known precisely, the first possible date (e.g. 2019 → 2019-01-01).<br>`%Y-%m-%d` | date |  |
| `date_max` | End date of drilling, or if not known precisely, the last possible date (e.g. 2019 → 2019-12-31).<br>`%Y-%m-%d` | date |  |
| `drill_method` | Drilling method:<br>- mechanical: Push, percussion, rotary, ...<br>- thermal: Hot point, electrothermal, steam, ...<br>- combined: Mechanical and thermal | string | enum: ['mechanical', 'thermal', 'combined'] |
| `ice_depth` | Starting depth of ice. Infinity (`INF`) indicates that ice was not reached. | number |  |
| `depth` | Total borehole depth (not including drilling in the underlying bed). | number |  |
| `to_bed` | Whether the borehole reached the glacier bed. | boolean |  |
| `temperature_accuracy` | Thermistor accuracy or precision (as reported). Typically understood to represent one standard deviation. | number |  |
| `notes` | Additional remarks about the study site, the borehole, or the measurements therein. Literature references should be formatted as `{url}` or `{author} {year} ({url})`. | string | pattern: `[^\s]+( [^\s]+)*` |

### `measurement`

| name | description | type | constraints |
| - | - | - | - |
| `borehole_id` | Borehole identifier. | integer | required: True |
| `depth` | Depth below the glacier surface. | number | required: True |
| `temperature` | Temperature. | number | required: True |
| `date_min` | Measurement date, or if not known precisely, the first possible date (e.g. 2019 → 2019-01-01).<br>`%Y-%m-%d` | date |  |
| `date_max` | Measurement date, or if not known precisely, the last possible date (e.g. 2019 → 2019-12-31).<br>`%Y-%m-%d` | date | required: True |
| `time` | Measurement time.<br>`%H:%M:%S` | time |  |
| `utc_offset` | Time offset relative to Coordinated Universal Time (UTC). | number |  |
| `equilibrated` | Whether the profile is in thermal equilibrium following drilling. | boolean |  |
<!-- </contributor-format> -->

### Validation

You can validate your CSV files (`borehole.csv` and `measurement.csv`) before submitting them using the [frictionless](https://github.com/frictionlessdata/framework) Python package.

1. Clone this repository.

   ```sh
   git clone https://github.com/mjacqu/glenglat.git
   cd glenglat
   ```

2. Either install the `glenglat-contribute` Python environment (with `conda`):

   ```sh
   conda env create --file contribute/environment.yaml
   conda activate glenglat
   ```

   Or install `frictionless` into an existing environment (with `pip`):

   ```sh
   pip install "frictionless~=5.13"
   ```

3. Validate, fix any reported issues, and rejoice! (`path/to/csvs` is the folder containing your CSV files)

   ```sh
   python contribute/validate_submission.py path/to/csvs
   ```

## Testing

Follow the instructions below to run a full test of the data package.

1. Clone this repository.

   ```sh
   git clone https://github.com/mjacqu/glenglat.git
   cd glenglat
   ```

2. Install the `glenglat` Python environment (with `conda`):

   ```sh
   conda env create --file tests/environment.yaml
   conda activate glenglat
   ```

3. Run the basic (`frictionless`) tests.

   ```sh
   frictionless validate datapackage.yaml
   ```

4. Run the custom (`pytest`) tests.

   ```sh
   pytest tests
   ```

5. An optional test checks that `borehole.glims_id` is consistent with borehole coordinates. This requires a [GeoParquet](https://geoparquet.org) file of glacier outlines from the [GLIMS](https://www.glims.org/) dataset with columns `geometry` (glacier outline) and `glac_id` (glacier id). To run, first install `geopandas` and `pyarrow`, then set the `GLIMS_PATH` environment variable before calling `pytest`.

   ```sh
   conda install -c conda-forge geopandas=0.13 pyarrow
   GLIMS_PATH=/path/to/parquet pytest tests
   ```
