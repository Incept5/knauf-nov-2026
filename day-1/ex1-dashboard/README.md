# Exercise 1: build an interactive dashboard (25 min)

**Data:** `munich_weather_2025.csv`, 365 days of Munich weather (Open-Meteo archive, 2025). Columns: date, temp_max_c,
temp_min_c, rain_mm, wind_max_kmh, sunshine_hours. It is real data and works offline.

**Brief (same for everyone):** "A site manager wants to see at a glance which days in 2025 were unsuitable for outdoor
work, and how bad the winter was." Build a web page with a chart and a summary. You choose the tool and the model.

**Stages (go as far as you can):**
1. Load the CSV and show a chart of temperature over the year.
2. Add filters: month range, and a toggle for "workable days" (rain < 2 mm, wind < 40 km/h, temp_min > 0).
3. Add a summary: how many workable days per month, and the five worst weeks.
4. Make it look good and work on a phone.

**Stretch ideas:** fetch live data from the Open-Meteo forecast API (no key; check it is reachable from the Knauf network first); export a PDF; add a "should we pour concrete
on Friday?" box that asks the model; speak the summary aloud; German UI.

**Notes for the comparison:** write down how many prompts it took, what the AI got wrong, and how you checked it.
