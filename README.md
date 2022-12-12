# glenglat
Global Englacial Temperature database

## Project description
Open-access database of englacial temperature measurements compiled from published literature and submitted entries.

## Data structure
- [`studies.csv`](studies.csv): Table of all studies that have been included to date. The column "catalogued" indicates whether data from the study has been incorporated into the database.

- [`measurement_info.csv`](measurement_info.csv):
Metadata about each individual temperature profile.

- [`data.csv`](data.csv):
Depth vs. temperature data linked to the the data in `measurement_info.csv` and `studies.csv` via `study_id` and `measurement_id`

## How to contribute
If you would like to contribute data, please send an email to jacquemart@vaw.baug.ethz.ch

Shared datasets should ideally include:

Depth vs. temperature data
Measurement date
Measurement location (ideally Lat/Long and elevation)
Whether the borehole reached the bottom
Any additional descriptions of the site, notes etc.
Author / team

We also welcome submissions of datasets that have already been digitized, because it allows us to assess the accuracy of the digitization process.
