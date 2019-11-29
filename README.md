# masslib

small lib for working with FTCIR MS spectra

This lib supports
<ul>
    <li> Isotope Distribution generator </li>
    <li> Assigning brutto formulae to signal </li>
    <li> Working with spectra as with sets (intersection, union, etc) </li>
</ul>

<h2>Usage Examples</h2>

Usage example for <b>isotope distribution generator</b>:
```python
from distribution_generation.mass_distribution import IsotopeDistribution

# brutto formulae that we want to use
brutto = {"Pd": 1, "Cl": 2}

# instance initialization
d = IsotopeDistribution(brutto)

# masses generations
d.generate_iterations(100000)

# plotting obtained distribution
d.draw()

# Graph can be saved by plt.savefig(filename, "png")
# For that import matplotlib.pyplot as plt is needed
```

Usage for <b>Arithmetic operations over assigned spectra</b>
```python
    
# imports
import os

import settings
from mass import MassSpectrum

#
masses = []
mapper = {"mw": "mass", "relativeAbundance": "I"}
for filename in sorted(os.listdir(settings.DATA_FOLDER)):
    masses.append(MassSpectrum().load(
        f"{settings.DATA_FOLDER}/{filename}",
        mapper=mapper,
        sep=',',
        ignore_columns=["peakNo", "errorPPM", "DBE", "class", "z"]
    ))
    
x, y, z = masses[:3]

union = (x + y + z).reset_to_one()
print(len(union > 2))  # intersection of all three
print(len(union > 1))  # number of bruttos which is presented at least 2 out of 3 spectra

for i in [x, y, z]:
    print(union.calculate_jaccard_needham_score(i))

# deleting common for all 3 spectra
x -= (union > 2)
y -= (union > 2)
z -= (union > 2)
```

Usage for <b>Spectrum Assignment</b>
```python

import time
import pandas as pd
from mass import MassSpectrum

gen_brutto = pd.read_csv("../brutto_generator/C_H_O_N_S.csv", sep=";")

mapper = {"mw": "mass", "relativeAbundance": "I"}

T = time.time()

# in one expression we run:
# created instance of a mass spectrum
# load mass spectrum
# assign
# dropping unassigned bruttos
ms = MassSpectrum().load(
    "../data/a_1.csv",
    mapper,
    sep=',',
    ignore_columns=["peakNo", "errorPPM", "DBE", "class", "C", "H", "O", "N", "S", "z"]
).assign(gen_brutto, elems=list("CHONS")).drop_unassigned()

print(time.time() - T)
```