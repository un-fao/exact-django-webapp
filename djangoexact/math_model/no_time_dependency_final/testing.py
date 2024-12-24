tier2 = 0
default = None


ciao = tier2 or default
ciao2 = tier2 if tier2 else default
ciao3 = tier2 if tier2 is not None else default

print(ciao)
print(ciao2)
print(ciao3)