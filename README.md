# `glenglat`: Global englacial temperature database

[![Frictionless](https://github.com/mjacqu/glenglat/actions/workflows/frictionless.yaml/badge.svg)](https://repository.frictionlessdata.io/pages/dashboard.html?user=mjacqu&repo=glenglat&flow=frictionless)

Open-access database of englacial temperature measurements compiled from published literature and submissions.

## Data structure

The dataset adheres to the Frictionless Data [Tabular Data Package](https://specs.frictionlessdata.io/tabular-data-package) specification.
The metadata in [`datapackage.yaml`](datapackage.yaml) describes, in detail, the contents of the tabular data files:

- [`data/source.csv`](data/source.csv): Description of each data source (either a direct contribution or the reference to a published study).
- [`data/borehole.csv`](data/borehole.csv): Description of each borehole (location, elevation, etc), linked to `source.csv` via `source_id`.
- [`data/profile.csv`](data/profile.csv): Description of each profile (date and time), linked to `borehole.csv` via `borehole_id`.
- [`data/measurement.csv`](data/measurement.csv): Description of each measurement (depth and temperature), linked to `profile.csv` via `borehole_id` and `profile_id`.

### Supporting information

In folder [`sources`](sources) are subfolders (see column `source.path`) with files that document how and from where the data was extracted. Binary files with a `.png` or `.pdf` extensions are figures, tables, maps, or text from the publication. Binary files with `.tif` extension are georeferenced maps from the publication saved as GeoTIFF, and text files with `.geojson` extension are spatial features extracted from these and saved as GeoJSON. Text files with an `.xml` extension document how numeric values were extracted from maps and figures using PlotDigitizer (https://plotdigitizer.sourceforge.net). Of these, digitized temperature profiles are named `{source_id}_{borehole_id}_{profile_id}.xml` and internally use `temperature` and `depth` as axis names.

Path (relative to the datapackage root directory) to a folder with files that document how and from where the data was extracted, named either `sources/{source_id}_{submitter_code}` or `sources/{source_id}_{author_code}{year}` (where `submitter_code` or `author_code` is the submitter or first author's lowercase, romanized, family name). Files with a `.png` or `.pdf` extension are figures, tables, maps, or text from the publication. Pairs of files with `.pgw` and `.png.aux.xml` extensions georeference a `.png` image, and files with `.geojson` extension are the subsequently-extracted spatial coordinates. Files with an `.xml` extension document how numeric values were extracted from maps and figures using Plot Digitizer (https://plotdigitizer.sourceforge.net). Of these, digitized temperature profiles are named `{source_id}_{borehole_id}_{profile_id}{suffix}`. Those without the optional `suffix` use `temperature` and `depth` as axis names. Those with a `suffix` are unusual cases which contain data for a range of profiles (suffix `-{last_profile_id}`) and/or a non-standard axis (suffix `_{axis}`), for example `163_515_1-8_date`.

## How to contribute

To contribute data, send an email to jacquemart@vaw.baug.ethz.ch. Please structure your data as either comma-separated values (CSV) files (`borehole.csv` and `measurement.csv`) or as an Excel file (with sheets `borehole` and `measurement`). The required and optional columns for each table are described below and in the submission metadata: [`contribute/datapackage.yaml`](contribute/datapackage.yaml). Consider using our handy Excel template: [`contribute/template.xlsx`](contribute/template.xlsx)!

*Note: We also welcome submissions of data that have already been digitized, as they allow us to assess the accuracy of the digitization process.*

<!-- <contributor-format> -->
### `borehole`

| name | description | type | constraints |
| - | - | - | - |
| `id` | Unique identifier. | integer | required: True<br>unique: True |
| `latitude` | Latitude (EPSG 4326). | number | required: True<br>minimum: -90<br>maximum: 90 |
| `longitude` | Longitude (EPSG 4326). | number | required: True<br>minimum: -180<br>maximum: 180 |
| `elevation` | Elevation above sea level. | number | required: True<br>maximum: 9999.0 |
| `glacier_name` | Glacier or ice cap name (as reported). | string | required: True<br>pattern: `[^\s]+( [^\s]+)*` |
| `glims_id` | Global Land Ice Measurements from Space (GLIMS) glacier identifier. | string | pattern: `G[0-9]{6}E[0-9]{5}[NS]` |
| `temperature_accuracy` | Thermistor accuracy or precision (as reported). Typically understood to represent one standard deviation. | number |  |
| `drill_method` | Drilling method:<br>- mechanical<br>- thermal: Hot water or steam | string | enum: ['mechanical', 'thermal'] |
| `to_bottom` | Whether the borehole reached the glacier bed. | boolean |  |
| `label` | Borehole name (e.g. as labeled on a plot). | string |  |
| `notes` | Additional remarks about the study site, the borehole, or the measurements therein. Literature references should be formatted as `{url}` or `author ({year}): {title} ({url})`. | string | pattern: `[^\s]+( [^\s]+)*` |

### `measurement`

| name | description | type | constraints |
| - | - | - | - |
| `borehole_id` | Borehole identifier. | integer | required: True |
| `depth` | Depth below the glacier surface. | number | required: True |
| `temperature` | Temperature. | number | required: True |
| `date_min` | Measurement date, or if not known precisely, the first possible date (e.g. 2019 → 2019-01-01).<br>`%Y-%m-%d` | date | required: True |
| `date_max` | Measurement date, or if not known precisely, the last possible date (e.g. 2019 → 2019-12-31).<br>`%Y-%m-%d` | date | required: True |
| `time` | Measurement time.<br>`%H:%M:%S` | time |  |
| `utc` | Whether `time` is in Coordinated Universal Time (True) or in another (but unknown) timezone (False). | boolean |  |
| `equilibrated` | Whether the profile is in thermal equilibrium following drilling. | boolean |  |
<!-- </contributor-format> -->

### Validation

You can validate your CSV files (`borehole.csv` and `measurement.csv`) before submitting them using the [frictionless](https://github.com/frictionlessdata/framework) Python package.

1. Clone this repository.

   ```sh
   git clone https://github.com/mjacqu/glenglat.git
   cd glenglat
   ```

2. Either install the `glenglat` Python environment (with `conda`):

   ```sh
   conda env create --file scripts/environment.yaml
   conda activate glenglat
   ```

   Or install `frictionless` into an existing environment (with `pip`):

   ```sh
   pip install "frictionless~=5.13"
   ```

3. Validate, fix any reported issues, and rejoice! (`path/to/csvs` is the folder containing your CSV files)

   ```sh
   python scripts/validate_submission.py path/to/csvs
   ```
