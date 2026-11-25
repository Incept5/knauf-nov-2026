"""Builds index.html = _template.html + the CSV from day-1/ex1-dashboard embedded (so index.html works opened from disk)."""
import pathlib
here = pathlib.Path(__file__).parent
csv = (here.parent.parent.parent / "day-1/ex1-dashboard/munich_weather_2025.csv").read_text()
(here / "index.html").write_text((here / "_template.html").read_text().replace("__CSV__", csv.strip()).replace("/*DATA_MARKER*/\n", ""))
print("index.html written")
