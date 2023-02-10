# `glenglat`: Global englacial temperature database

Open-access database of englacial temperature measurements compiled from published literature and submitted entries.

## Data structure

The dataset adheres to the Frictionless Data [Tabular Data Package](https://specs.frictionlessdata.io/tabular-data-package) specification.
The metadata in [`datapackage.yaml`](datapackage.yaml) describes, in detail, the contents of the tabular data files:

- [`data/source.csv`](data/source.csv): Description of each data source (either a direct contribution or the reference to a published study).
- [`data/borehole.csv`](data/borehole.csv): Description of each borehole (location, elevation, etc), linked to `source.csv` via `source_id`.
- [`data/profile.csv`](data/profile.csv): Description of each profile (date and time), linked to `borehole.csv` via `borehole_id`.
- [`data/measurement.csv`](data/measurement.csv): Description of each measurement (depth and temperature), linked to `borehole.csv` and `profile.csv` via `borehole_id` and `profile_id`, respectively.

## How to contribute

To contribute data, send an email to jacquemart@vaw.baug.ethz.ch. Please structure your data as either comma-separated values (CSV) files (`borehole.csv` and `measurement.csv`) or as an Excel file (with sheets `borehole` and `measurement`). The required and optional columns for each table are described below. Consider using our handy Excel template: [`contribute/template.xlsx`](contribute/template.xlsx)!

*Note: We also welcome submissions of data that have already been digitized, as they allow us to assess the accuracy of the digitization process.*

<!-- <contributor-format> -->
### `borehole`

| name | description | type | constraints |
| - | - | - | - |
| `id` | Unique identifier. | integer | required: True<br>unique: True<br> |
| `latitude` | Latitude (EPSG 4326). | number | required: True<br>minimum: -90<br>maximum: 90<br> |
| `longitude` | Longitude (EPSG 4326). | number | required: True<br>minimum: -180<br>maximum: 180<br> |
| `elevation` | Elevation above sea level. | number | required: True<br>maximum: 9999.0<br> |
| `glacier_name` | Glacier or ice cap name (as reported). | string | required: True<br>pattern: `[^\s]+( [^\s]+)*`<br> |
| `rgi_id` | Randolph Glacier Inventory (RGI) 6.0 identifier. | string | required: True<br>pattern: `RGI60-\d{2}\.\d{5}`<br> |
| `temperature_accuracy` | Thermistor accuracy or precision (as reported). Typically understood to represent one standard deviation. | number |  |
| `to_bottom` | Whether the borehole reached the glacier bed. | boolean |  |
| `label` | Borehole name (e.g. as labeled on a plot). | string |  |
| `notes` | Additional remarks about the study site, the borehole, or the measurements therein. Literature references should be formatted as `{url}` or `author ({year}): {title} ({url})`. | string | pattern: `[^\s]+( [^\s]+)*`<br> |
| `first_author` | Name of first study author. | string | required: True<br>pattern: `[^\s]+( [^\s]+)*`<br> |
| `year` | Year of study publication. | year | required: True<br> |
| `title` | Study title. | string | pattern: `[^\s]+( [^\s]+)*`<br> |
| `url` | Study URL (DOI if available). | string | pattern: `https?:\/\/.+`<br> |

### `measurement`

| name | description | type | constraints |
| - | - | - | - |
| `borehole_id` | Borehole identifier. | integer | required: True<br> |
| `depth` | Depth below the glacier surface. | number | required: True<br> |
| `temperature` | Temperature. | number |  |
| `date_min` | Measurement date, or if not known precisely, the first possible date (e.g. 2019 → 2019-01-01).<br>`%Y-%m-%d` | date | required: True<br> |
| `date_max` | Measurement date, or if not known precisely, the last possible date (e.g. 2019 → 2019-12-31).<br>`%Y-%m-%d` | date | required: True<br> |
| `time` | Measurement time.<br>`%H:%M:%S` | time |  |
| `utc` | Whether `time` is in Coordinated Universal Time (True), in another (but unknown) timezone (False), or in an unknown timezone (NULL). | boolean |  |
<!-- <contributor-format> -->
