import faostat
import csv
import dotenv
import os

dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), "..", "djangoexact", ".env"))

FAOSTAT_TOKEN = os.getenv("FAOSTAT_TOKEN")

faostat.set_requests_args(token=FAOSTAT_TOKEN)

yield_items = list(faostat.get_par("QCL", "item"))

# to csv
with open("faostat_crops.csv", "w") as f:
    writer = csv.writer(f)
    writer.writerow(["item"])
    for item in yield_items:
        writer.writerow([item])