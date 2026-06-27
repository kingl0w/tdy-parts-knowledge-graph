# tdy-parts-graph

a small knowledge graph for a used computer parts inventory, built twice over the same ontology: once in python for modeling and validation, once on the jvm (apache jena + fuseki) as a served, persistent, reasoning endpoint that stands up in one `docker compose up`.

the point of the project is the thing a normal database can't do: it answers questions about facts nobody typed in. you assert that a motherboard fits a cpu; the graph derives that the cpu fits the motherboard, and that a listing selling that cpu offers something compatible with a motherboard. those facts are computed by an owl reasoner, not stored by hand.

## what this demonstrates

- owl/rdfs domain modeling, including a defined class and an owl 2 property chain
- the full reasoning stack on the jvm: rdfs and owl-rule inference live in fuseki, full owl dl (hermit) materialized offline
- the engineering judgment of *which* inference runs live vs precomputed, and why
- shacl data-quality validation, run through two engines (pyshacl and jena) off one shapes file
- a deployable artifact: served sparql endpoint, persistent triplestore, containerized, one command to run

## two implementations, one ontology

the ontology (`ontology/parts.ttl`) and data (`data/inventory.ttl`) are the single source of truth. both stacks read the same files.

**python** (`src/`): rdflib + owlready2 + pyshacl. modeling, rdfs reasoning, shacl validation, a pytest ci gate. fast to iterate, good for getting the model right.

**jena / fuseki** (`jena/`): the same ontology served as infrastructure. persistent tdb2 store, a real sparql endpoint over http, three inference configs, an offline hermit materializer, and a docker build. this is the "deploy it" half.

## the derived-not-stored demo

the headline. you assert exactly one direction of compatibility:

```turtle
tdy:mobo_x1 tdy:compatibleWith tdy:cpu_x1 .
tdy:mobo_x1 tdy:compatibleWith tdy:ram_x1 .
```

query the served endpoint for what listings offer something motherboard-compatible:

```sparql
SELECT ?listing ?x WHERE { ?listing tdy:offersCompatible ?x }
```

```
listing_1  mobo_x1
listing_2  mobo_x1
```

nobody wrote those triples. deriving them takes two inferences composed: `compatibleWith` is symmetric (so the cpu is compatible with the mobo, in reverse of what was asserted), and `offersCompatible` is a property chain `sells ∘ compatibleWith` (so a listing selling that cpu offers something compatible with the mobo). hermit computes this once; the result is served as plain data with no reasoner running at query time.

the defined class `MotherboardCompatible` works the same way: `cpu_x1` and `ram_x1` are classified into it without ever being asserted as members.

## layout

```
ontology/parts.ttl              owl/rdfs ontology (shared)
data/inventory.ttl              served dataset (shared)
data/valid.ttl                  fixture: conforming records
data/invalid.ttl                fixture: six broken records
shapes/listing-shapes.ttl       shacl shapes (shared by both validators)
src/validate.py                 python: load, reason, validate, query
tests/test_shapes.py            python: pytest ci gate

jena/reasoner/                  maven project: owl api + hermit offline materializer
jena/reasoner/inferred.ttl      hermit output, committed so the graph rebuilds without a reasoner run
jena/fuseki/tdyparts-rdfs.ttl   fuseki config: live rdfs reasoner
jena/fuseki/tdyparts-owl.ttl    fuseki config: live owl-rule reasoner
jena/fuseki/tdyparts-served.ttl fuseki config: plain, serves the materialized graph
jena/fuseki/tdyparts-docker.ttl same, with container paths
jena/Dockerfile                 multi-stage: load tdb2, then serve
docker-compose.yml              one-command standup
```

## run it

### jena (served endpoint, one command)

```
docker compose up -d
# wait a few seconds for fuseki to start, then:
curl -s http://localhost:3030/tdyparts/sparql -H 'Accept: text/csv' \
  --data-urlencode 'query=PREFIX tdy: <https://tdytrading.example/parts#>
SELECT ?listing ?x WHERE { ?listing tdy:offersCompatible ?x }'
docker compose down
```

needs only docker. the image builds the tdb2 store from the three ttls and serves it. no java or jena install required.

### python (validate + reason locally)

```
pip install -r requirements.txt
python src/validate.py
pytest -q
```

`validate.py` runs the demo dataset and reports violations. `pytest -q` is the ci gate against the split fixtures.

### jena, manually (no docker)

requires java 21 and a local apache jena/fuseki 6.1.0. the configs in `jena/fuseki/` swap the inference layer by pointing `fuseki-server --config` at the rdfs, owl, or served file. the reasoner (`jena/reasoner/`) builds with `mvn package` and runs on java 17, since owl api 5.x predates java 21. it is a build-time tool, decoupled from the java 21 serving stack on purpose.

## the model

components (cpu, gpu, ram, storage, motherboard) are subclasses of `Component`, so an rdfs reasoner infers any cpu is also a component. a `Listing` sells one component, has one condition from a controlled vocabulary (new, used, refurb, forparts), and is listed by one seller. a `GradedListing` adds a 1..10 grade and is never sold for parts.

on top of that, three owl constructs that need real reasoning:

- `compatibleWith`: a symmetric object property between components.
- `MotherboardCompatible`: a defined class, `Component and (compatibleWith some Motherboard)`. the reasoner classifies instances into it; nothing is asserted.
- `offersCompatible`: a property chain `sells ∘ compatibleWith`.

## inference: what runs where

three layers, placed deliberately.

- **rdfs, live in fuseki.** subclass and range entailment. cheap, runs on every query. (`tdyparts-rdfs.ttl`)
- **owl-rule, live in fuseki.** adds property characteristics: symmetry, inverse, transitivity. still cheap. (`tdyparts-owl.ttl`)
- **owl dl, materialized offline.** jena's built-in owl reasoner is rule-based and predates owl 2: it does not do property chains, and its live handling of existential restrictions skolemizes invented blank-node witnesses into query results. so the heavy reasoning (hermit, full owl dl) runs once as a build step, writes `inferred.ttl`, and that gets loaded and served as plain triples. the served endpoint runs no reasoner. (`jena/reasoner/`, `tdyparts-served.ttl`)

this split is the design point: do the cheap, safe deductions live; precompute the expensive ones and serve the answers. it is also how this scales, since live dl reasoning inside a query endpoint does not.

## validation (shacl)

`shapes/listing-shapes.ttl` is validated by both pyshacl (python) and jena's `shacl` command (jvm), same file, same verdicts. it passes `data/valid.ttl` and flags all six broken records in `data/invalid.ttl`: negative price, condition outside the allowed set, missing seller, grade out of range, a graded listing sold for parts, and a component with no mpn.

one subtlety worth stating: shacl validates the graph exactly as given and does no reasoning of its own. a shape requiring a listing to sell a `Component` only passes if the class hierarchy is present, so validation includes `ontology/parts.ttl` alongside the data. shacl checks shape, the reasoner derives truth, they are separate layers.

## notes on tooling

- versions verified current as of the build: apache jena + fuseki 6.1.0 (java 21), hermit via owl api 5.1.x (java 17).
- openllet, the usual "owl dl in a jena stack" answer, was rejected: last release 2019, pinned to an old jena, will not load in fuseki 6. hermit run offline through the owl api is the maintained path.
- the dockerfile pulls jena from `archive.apache.org` rather than the live mirror, so the build stays reproducible after a release rolls over and the live mirror drops the old tarball.
