# glenglat
Global Englacial Temperature database

## Project description
Open-access database of englacial temperature measurements compiled from published literature and submitted entries.

## Data structure
- [`data/sources.csv`](data/sources.csv): Table of all studies that have been considered to date. The column `included` indicates whether temperature measurements from the study have been included in the database.

- [`data/boreholes.csv`](data/boreholes.csv):
Metadata about each individual temperature profile.

- [`data/temperatures.csv`](data/temperatures.csv):
Depth vs. temperature data linked to the the data in `boreholes.csv` and `sources.csv` via `borehole_id` and `source_id`, respectively.

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
