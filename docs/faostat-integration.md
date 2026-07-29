# How the FAOSTAT Integration Works

## What is FAOSTAT?

FAOSTAT is the United Nations Food and Agriculture Organization's global statistical database. Among other data, it publishes annual **crop yield figures** — how much of a crop (in tonnes) is typically harvested per hectare of land, broken down by country and year.

## Why does the application use it?

When a user adds an **Annual Cropland** activity to a project, the system needs to know how productive the land is (its crop yield) to calculate greenhouse gas emissions accurately. Instead of requiring the user to manually find and enter this figure every time, the application fetches it automatically from FAOSTAT.

---

## Step-by-step: what happens when a calculation runs

1. **Determine the reference year.**
   The system looks at the activity's configured year (`faostat_year_t2`). If the user has not set one, it defaults to the project's start year.

2. **Ask FAOSTAT for the yield.**
   Using the **country name** (e.g., "Italy") and the **crop name** (e.g., "Wheat"), the system contacts the FAOSTAT database and requests the official yield figure for that year.

3. **Try earlier years if needed.**
   If FAOSTAT has no data for that exact year, the system automatically steps back — one year at a time — for up to **20 years**, until it finds data.

4. **Pick the best number.**
   If FAOSTAT returns multiple figures for the same year (which can happen), the system prefers the entry marked as **officially verified** (flag "A"). If no verified figure exists, it reports an error rather than using uncertain data.

5. **Fall back to local data if FAOSTAT is unavailable.**
   If the FAOSTAT service cannot be reached (no internet, authentication problem, or no data found within 20 years), the system falls back to a built-in local reference table of regional average yields (`CropYieldStat`).

6. **Manual override as a last resort.**
   If the user has entered a yield value manually on the activity form (`crop_yield_t2`), that value is used when neither FAOSTAT nor the local table can provide data.

---

## Summary diagram

```
Run calculation
      │
      ▼
FAOSTAT available? ──No──▶ Local reference table available? ──No──▶ User entered a value? ──No──▶ ERROR
      │                                 │                                      │
     Yes                               Yes                                    Yes
      │                                 │                                      │
  Use FAOSTAT data              Use regional average                  Use manual value
```

---

## Key design decisions

| What | Why |
|---|---|
| Tries up to 20 years back | Agricultural datasets often have a 1–3 year publication lag; going back further ensures data is found |
| Converts kg/ha → t/ha | FAOSTAT publishes in kg/ha; the emissions model internally works in t/ha |
| Thread-safe locking | Multiple calculations can run at the same time; the lock prevents one calculation from interfering with another's connection to FAOSTAT |
| Credentials from environment variables | Username and password are never stored in the code or database; they are injected securely at deploy time |

---

## What can go wrong, and what the user sees

| Situation | What happens |
|---|---|
| Country or crop name doesn't match FAOSTAT's spelling | An error is shown asking the user to check the name |
| No data found in any of the 20 years | Falls back to the regional average, or asks the user to enter a value manually |
| FAOSTAT is unreachable (network/auth) | Falls back to the regional average silently; a warning is logged |
| No data anywhere and no manual value | The calculation fails with a clear message asking the user to provide a manual yield |
