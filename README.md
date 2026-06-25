# tdy-parts-graph

a tiny knowledge graph for a used computer parts inventory. it shows the full loop:
model the domain in owl, constrain it with shacl, load the data, run rdfs reasoning,
validate, and query.

## layout

```
ontology/parts.ttl          owl/rdfs ontology
shapes/listing-shapes.ttl   shacl shapes (the data quality rules)
data/inventory.ttl          sample data: clean records plus deliberately broken ones
src/validate.py             loads everything, reasons, validates, queries
```

## run it

```
pip install -r requirements.txt
python src/validate.py
```

the sample data contains six deliberately broken records, so a clean run reports
`conforms: False`, prints the violations, and exits 1. that is the point: the same
script is the ci gate in `.github/workflows/validate.yml`. swap in clean data and it
exits 0.

## the model

components (cpu, gpu, ram, storage) are subclasses of `Component`, so an rdfs reasoner
infers any cpu is also a component. a `Listing` sells one component, has one condition
from a controlled vocabulary (new, used, refurb, forparts), and is listed by one seller.
a `GradedListing` adds a 1..10 grade and is never sold for parts.
