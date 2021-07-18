import pandas as pd

#  from pangeo_forge_recipes.patterns import pattern_from_file_sequence
from pangeo_forge_recipes.patterns import ConcatDim, FilePattern
from pangeo_forge_recipes.recipes import XarrayZarrRecipe

#  input_url_pattern = (
#  "https://www.ncei.noaa.gov/data/sea-surface-temperature-optimum-interpolation"
#  "/v2.1/access/avhrr/{yyyymm}/oisst-avhrr-v02r01.{yyyymmdd}.nc"
#  )
#  dates = pd.date_range("2019-09-01", "2021-01-05", freq="D")
#  input_urls = [
#  input_url_pattern.format(yyyymm=day.strftime("%Y%m"), yyyymmdd=day.strftime("%Y%m%d"))
#  for day in dates
#  ]


def format_function(time):
    base = pd.Timestamp("2019-09-01")
    day = base + pd.Timedelta(days=time)
    input_url_pattern = (
        "https://www.ncei.noaa.gov/data/sea-surface-temperature-optimum-interpolation"
        "/v2.1/access/avhrr/{day:%Y%m}/oisst-avhrr-v02r01.{day:%Y%m%d}.nc"
    )
    return input_url_pattern.format(day=day)


dates = pd.date_range("2019-09-01", "2021-01-05", freq="D")
#  pattern = pattern_from_file_sequence(input_urls, "time", nitems_per_file=1)
pattern = FilePattern(format_function, ConcatDim("time", range(len(dates)), 1))
recipe = XarrayZarrRecipe(pattern, inputs_per_chunk=20, cache_inputs=True)
