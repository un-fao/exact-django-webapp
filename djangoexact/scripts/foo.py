import api.models as models

cs = [c.name for c in models.Country.objects.all()]

print(cs)

from collections import Counter

# Count occurrences
country_count = Counter(cs)

# Find duplicates
duplicates = [country for country, count in country_count.items() if count > 1]

print(duplicates)
