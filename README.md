[![Build Status](https://cloud.drone.io/api/badges/cknoll/semantictools/status.svg)](https://cloud.drone.io/cknoll/semantictools)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# General Information

This repo collects some code to explore ontologies from Python or Jupyter Notebook.

Installation:

1. clone the repo
2. run `pip install -e .`

# Showcases

## Retrieving the superclasses of a wikidata entity

See also [doc/demo_notebooks/wikidata_superclasses.ipynb](doc/demo_notebooks/wikidata_superclasses.ipynb)


### 3 levels

![vectorspace_superclasses_l3.svg](doc/demo_notebooks/vectorspace_superclasses_l3.svg)

### 13 levels

![vectorspace_superclasses_l13.svg](doc/demo_notebooks/vectorspace_superclasses_l13.svg)


## Visualizing the taxonomy of `bfo.owl`

See also [doc/demo_notebooks/bfo_visualization.ipynb](doc/demo_notebooks/bfo_visualization.ipynb):

![bfo.svg](doc/demo_notebooks/bfo.svg)


# Contributing

This repo uses `black -l 120 ./` as base line for coding style .
