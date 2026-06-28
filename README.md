# tdy-parts-graph

A small knowledge graph for a used computer parts inventory, built twice over the same ontology: once in Python for modeling and validation, once on the JVM (Apache Jena + Fuseki) as a served, persistent, reasoning endpoint that stands up in one `docker compose up`.

The point of the project is the thing a normal database can't do: it answers questions about facts nobody typed in. You assert that a motherboard fits a CPU; the graph derives that the CPU fits the motherboard, and that a listing selling that CPU offers something compatible with a motherboard. Those facts are computed by an OWL reasoner, not stored by hand. On top of that, the graph derives *physical build compatibility* (which parts fit together, whether a build has enough power) from part attributes, using SPARQL rules rather than OWL, because rules are the better tool for value-matching. Two inference paradigms, one served graph.

## What this demonstrates

- OWL/RDFS domain modeling, including a defined class and an OWL 2 property chain
- The full reasoning stack on the JVM: RDFS and OWL-rule inference live in Fuseki, full OWL DL (HermiT) materialized offline
- SPARQL CONSTRUCT rules deriving compatibility from attributes, across three escalating patterns (equality, set-containment, numeric threshold) plus whole-build power aggregation
- The judgment to use two different inference paradigms in one graph, OWL DL where it fits and SPARQL rules where they fit, kept distinguishable by predicate
- SHACL data-quality validation, run through two engines (pySHACL and Jena) off one shapes file
- A deployable artifact: served SPARQL endpoint, persistent triplestore, containerized, one command to run

## Two implementations, one ontology

The ontology (`ontology/parts.ttl`) and data are the single source of truth. Both stacks read the same files.

**Python** (`src/`): rdflib + owlready2 + pySHACL. Modeling, RDFS reasoning, SHACL validation, a pytest CI gate. Fast to iterate, good for getting the model right.

**Jena / Fuseki** (`jena/`): the same ontology served as infrastructure. Persistent TDB2 store, a real SPARQL endpoint over HTTP, inference configs, an offline HermiT materializer, the SPARQL build-compatibility rules, and a Docker build. This is the "deploy it" half. (The build-compatibility rules are a Jena-side capability; they have no Python counterpart.)

## The derived-not-stored demo

The headline. You assert exactly one direction of compatibility:

```turtle
tdy:mobo_x1 tdy:compatibleWith tdy:cpu_x1 .
tdy:mobo_x1 tdy:compatibleWith tdy:ram_x1 .
```

Query the served endpoint for what listings offer something motherboard-compatible:

```sparql
SELECT ?listing ?x WHERE { ?listing tdy:offersCompatible ?x }
```

```
listing_1  mobo_x1
listing_2  mobo_x1
```

Nobody wrote those triples. Deriving them takes two inferences composed: `compatibleWith` is symmetric (so the CPU is compatible with the mobo, in reverse of what was asserted), and `offersCompatible` is a property chain `sells ∘ compatibleWith` (so a listing selling that CPU offers something compatible with the mobo). HermiT computes this once; the result is served as plain data with no reasoner running at query time.

The defined class `MotherboardCompatible` works the same way: `cpu_x1` and `ram_x1` are classified into it without ever being asserted as members.

## Build compatibility (SPARQL rules)

The OWL work above answers questions about listings and provenance. A second, separate body of work answers a different question: which parts physically and electrically go together, and whether a complete build is valid. This is derived with SPARQL CONSTRUCT rules over part attributes, not OWL, because matching on shared or sufficient attribute values is what rules are built for and what OWL is clumsy at.

The data lives in `data/catalog.ttl`: parts carrying attributes (socket, RAM generation, form factor, interface, length, power draw, recommended PSU) plus a couple of example `Build` nodes that group chosen parts.

The rules live in `rules/`, seven CONSTRUCT queries across three escalating patterns:

- **Equality** (`01-socket`, `02-ramgen`, `03-interface`): two parts match when they share an attribute value. CPU and board share a socket, RAM and board share a generation, storage and board share an interface.
- **Set-containment** (`04-formfactor`, `05-gpu-length`): not equality but "fits inside." A board's form factor must be in the set a case accepts; a GPU's length must be within a case's clearance (a numeric `<=`).
- **Numeric threshold** (`06-gpu-psu`): a PSU is sufficient for a GPU when its wattage meets the GPU's manufacturer-recommended figure.
- **Whole-build aggregation** (`07-build-power`): the hardest one, and a different shape. It sums the power draw across every part of a `Build` and compares to the build's PSU, emitting `powerOk` only if the supply clears the total. This needs the notion of a build as a node, not a pairwise edge.

Each rule emits `tdy:fitsWith` (or `tdy:powerOk`), deliberately a different predicate from the OWL-reasoned `tdy:compatibleWith`. Keeping them separate means one graph can hold both kinds of compatibility while a query can still tell which mechanism produced which fact.

The rules are materialized the same way as the OWL inferences: `jena/run-rules.sh` runs all seven against the catalog and writes `data/catalog-inferred.ttl`, which is committed and loaded into the served store. Derive offline, serve static, no rule engine running at query time.

### Two paradigms, one query

Because both mechanisms write into the same served graph with distinct predicates, a single query can ask for both and tell them apart:

```sparql
SELECT ?s ?type ?o WHERE {
  { ?s tdy:compatibleWith ?o BIND("owl-reasoned" AS ?type) }
  UNION
  { ?s tdy:fitsWith ?o BIND("rule-derived" AS ?type) }
}
```

The `owl-reasoned` rows come from HermiT (symmetry, property chains, defined classes); the `rule-derived` rows come from the SPARQL rules (attribute matching, containment, thresholds). Same graph, two inference paradigms, distinguishable by design.

## Layout

```
ontology/parts.ttl              OWL/RDFS ontology (shared)
data/inventory.ttl              listing demo dataset (served)
data/valid.ttl                  fixture: conforming records
data/invalid.ttl                fixture: six broken records
data/catalog.ttl                build catalog: parts with attributes + example builds
data/catalog-inferred.ttl       rule-derived fitsWith / powerOk facts (materialized)
shapes/listing-shapes.ttl       SHACL shapes (shared by both validators)
src/validate.py                 Python: load, reason, validate, query
tests/test_shapes.py            Python: pytest CI gate

rules/*.rq                      SPARQL CONSTRUCT rules deriving build compatibility
jena/run-rules.sh               runs all rules, writes catalog-inferred.ttl
jena/reasoner/                  Maven project: OWL API + HermiT offline materializer
jena/reasoner/inferred.ttl      HermiT output, committed so the graph rebuilds without a reasoner run
jena/fuseki/tdyparts-rdfs.ttl   Fuseki config: live RDFS reasoner
jena/fuseki/tdyparts-owl.ttl    Fuseki config: live OWL-rule reasoner
jena/fuseki/tdyparts-served.ttl Fuseki config: plain, serves the materialized graph
jena/fuseki/tdyparts-docker.ttl same, with container paths
jena/Dockerfile                 multi-stage: load TDB2, then serve
docker-compose.yml              one-command standup
```

## Run it

### Jena (served endpoint, one command)

```
docker compose up -d
# wait a few seconds for Fuseki to start, then:

# OWL-reasoned: which listings offer a motherboard-compatible part
curl -s http://localhost:3030/tdyparts/sparql -H 'Accept: text/csv' \
  --data-urlencode 'query=PREFIX tdy: <https://tdytrading.example/parts#>
SELECT ?listing ?x WHERE { ?listing tdy:offersCompatible ?x }'

# rule-derived: which PSUs are sufficient for which GPUs
curl -s http://localhost:3030/tdyparts/sparql -H 'Accept: text/csv' \
  --data-urlencode 'query=PREFIX tdy: <https://tdytrading.example/parts#>
SELECT ?gpu ?psu WHERE { ?gpu a tdy:GPU ; tdy:fitsWith ?psu . ?psu a tdy:PSU }'

docker compose down
```

Needs only Docker. The image builds the TDB2 store from the five TTLs (ontology, listing data + HermiT inferences, catalog + rule-derived facts) and serves it. No Java or Jena install required.

### Python (validate + reason locally)

```
pip install -r requirements.txt
python src/validate.py
pytest -q
```

`validate.py` runs the demo dataset and reports violations. `pytest -q` is the CI gate against the split fixtures.

### Jena, manually (no Docker)

Requires Java 21 and a local Apache Jena/Fuseki 6.1.0. The configs in `jena/fuseki/` swap the inference layer by pointing `fuseki-server --config` at the RDFS, OWL, or served file. The reasoner (`jena/reasoner/`) builds with `mvn package` and runs on Java 17, since OWL API 5.x predates Java 21. It is a build-time tool, decoupled from the Java 21 serving stack on purpose. The SPARQL rules run with `jena/run-rules.sh` (needs the `sparql` command on PATH).

## The model

**Listing side.** Components (CPU, GPU, RAM, storage, motherboard) are subclasses of `Component`, so an RDFS reasoner infers any CPU is also a component. A `Listing` sells one component, has one condition from a controlled vocabulary (new, used, refurb, forparts), and is listed by one seller. A `GradedListing` adds a 1..10 grade and is never sold for parts.

Three OWL constructs that need real reasoning:

- `compatibleWith`: a symmetric object property between components.
- `MotherboardCompatible`: a defined class, `Component and (compatibleWith some Motherboard)`. The reasoner classifies instances into it; nothing is asserted.
- `offersCompatible`: a property chain `sells ∘ compatibleWith`.

**Build side.** A `Part` superclass covers every physical part (Component plus `PSU` and `Case`). Parts carry plain-literal attributes (`socket`, `ramGen`, `formFactor`, `acceptsFormFactor`, `interface`, `lengthMm`, `maxGpuMm`, `wattage`, `draw`, `recommendedPsu`) that the SPARQL rules match on. A `Build` is a node with `hasPart` edges to its chosen parts, which is what makes whole-build reasoning (the power aggregation) possible. The rules emit `fitsWith` between parts and `powerOk` on builds.

## Inference: what runs where

Two derivation mechanisms, both following the same derive-offline-serve-static pattern.

**OWL, three layers:**

- **RDFS, live in Fuseki.** Subclass and range entailment. Cheap, runs on every query. (`tdyparts-rdfs.ttl`)
- **OWL-rule, live in Fuseki.** Adds property characteristics: symmetry, inverse, transitivity. Still cheap. (`tdyparts-owl.ttl`)
- **OWL DL, materialized offline.** Jena's built-in OWL reasoner is rule-based and predates OWL 2: it does not do property chains, and its live handling of existential restrictions skolemizes invented blank-node witnesses into query results. So the heavy reasoning (HermiT, full OWL DL) runs once as a build step, writes `inferred.ttl`, and that gets loaded and served as plain triples. (`jena/reasoner/`)

**SPARQL rules, materialized offline.** The build-compatibility rules in `rules/` run via `jena/run-rules.sh`, which writes `catalog-inferred.ttl`. Same idea as the HermiT step but rule-based: compute the derived edges once, serve them as plain triples.

The served endpoint (`tdyparts-served.ttl`) runs no reasoner at all. Both the OWL and the SPARQL derivations are precomputed and loaded as static data. The design point: do the cheap, safe deductions live; precompute the expensive ones and serve the answers. It is also how this scales, since live reasoning inside a query endpoint does not.

## Validation (SHACL)

`shapes/listing-shapes.ttl` is validated by both pySHACL (Python) and Jena's `shacl` command (JVM), same file, same verdicts. It passes `data/valid.ttl` and flags all six broken records in `data/invalid.ttl`: negative price, condition outside the allowed set, missing seller, grade out of range, a graded listing sold for parts, and a component with no mpn.

One subtlety worth stating: SHACL validates the graph exactly as given and does no reasoning of its own. A shape requiring a listing to sell a `Component` only passes if the class hierarchy is present, so validation includes `ontology/parts.ttl` alongside the data. SHACL checks shape, the reasoner derives truth, they are separate layers.

## Notes on tooling

- Versions verified current as of the build: Apache Jena + Fuseki 6.1.0 (Java 21), HermiT via OWL API 5.1.x (Java 17).
- Openllet, the usual "OWL DL in a Jena stack" answer, was rejected: last release 2019, pinned to an old Jena, will not load in Fuseki 6. HermiT run offline through the OWL API is the maintained path.
- The Dockerfile pulls Jena from `archive.apache.org` rather than the live mirror, so the build stays reproducible after a release rolls over and the live mirror drops the old tarball.
