# Netflix App

## Download your Netflix data

Go here and request your netflix data for download:
https://www.netflix.com/account/getmyinfo

## Get a TMDB API key

Signup here:
https://www.themoviedb.org/signup

Create an API key here:
https://www.themoviedb.org/settings/api

## Setup

Put the following files in the `inputs` folder:

- NetflixViewingHistory.csv (downloaded from netflix)
- TMDB_API_KEY.txt (put the key in this text file)
- missing_imdb_id.json (optional: put json in here to fix titles missing from TMDB)

## Create your Netflix Page

```
./run.sh
```

Force it to run again:

```
./run.sh --force
```

## Debugging

Check the temp folder for intermediate files that are generated.
You can view these dataframes in Pandas to see whats going on.
The main.py runs each step one after the other so you can look at the code where your
issue is happening.

## Missing IMDB file

The missing IMDB file is there so you can manually tell the system of an IMDB ID for a
particular title.

The format is:

```json
{
  "Life: Primates": "tt1533395"
}
```

Each item can be partial or exact match but don't be too short as it will match other
titles with a string in string comparison.
