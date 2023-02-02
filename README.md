# glenglat
Global Englacial Temperature database

## Project description
Open-access database of englacial temperature measurements compiled from published literature and submitted entries.

## Data structure
- [`data/source.csv`](data/source.csv): Table of all studies and data contributors that have been considered to date. The column `included` indicates whether temperature measurements from the study have been included in the database or not.

- [`data/borehole.csv`](data/borehole.csv):
Metadata about each individual borehole, linked to data in `source.csv`via `source_id`.

- [`data/timestamp.csv`](data/timestamp.csv):
Date, date range or date and time of each measurement, linked to the data in `borehole.csv` via `borehole_id`.

- [`data/temperature.csv`](data/temperature.csv):
Depth vs. temperature data linked to the data in `borehole.csv` and `timestamp.csv` via `borehole_id` and `timestamp_id`, respectively.

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
