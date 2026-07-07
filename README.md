# tdy-parts-graph

A knowledge graph for a used computer parts inventory. It answers questions about facts nobody typed in: assert that a motherboard fits a CPU, and the graph derives that the CPU fits the motherboard, that a listing selling that CPU offers something motherboard-compatible, and which parts form a working build with enough power. Those facts are computed, not stored.

**Live demo:** [project page](https://kingl0w.github.io/tdy-parts-knowledge-graph/) · [radial build explorer](https://kingl0w.github.io/tdy-parts-knowledge-graph/viz/explorer.html) · [force graph](https://kingl0w.github.io/tdy-parts-knowledge-graph/viz/index.html)

It is built over one ontology with deliberately different tools for different jobs: OWL/HermiT reasoning for the listing world, SPARQL rules for build compatibility, a Python pipeline for data intake, and a local LLM for natural-language queries. The whole serving stack stands up in one `docker compose up`.

## What it demonstrates

- OWL/RDFS modeling with a defined class and an OWL 2 property chain, materialized offline with HermiT
- SPARQL CONSTRUCT rules deriving compatibility from part attributes, across three patterns (equality, set-containment, numeric threshold) plus whole-build power aggregation
- Two inference paradigms in one served graph, kept distinguishable by predicate
- A tested CSV intake pipeline (validate then map) that replaces hand-written RDF
- SHACL validation run through two engines off one shapes file
- A provider-agnostic local-LLM layer that turns English into SPARQL against the live endpoint
- A deployable artifact: persistent triplestore, served SPARQL endpoint, containerized, one command

A through-line: each tool was chosen for fit, not name. SPARQL rules over OWL for value-matching, plain Python over RML for intake at this scale, a local model over a cloud API for a self-contained tool.

## The two reasoning paradigms

**OWL (the listing world).** You assert one direction of compatibility:

```turtle
tdy:mobo_x1 tdy:compatibleWith tdy:cpu_x1 .
```

and querying `tdy:offersCompatible` returns listings nobody linked by hand. It takes two composed inferences: `compatibleWith` is symmetric, and `offersCompatible` is a property chain `sells ∘ compatibleWith`. HermiT computes this offline; the result is served as plain triples. The defined class `MotherboardCompatible` (`Component and (compatibleWith some Motherboard)`) is classified the same way.

**SPARQL rules (the build world).** Which parts physically and electrically fit, derived from attributes rather than OWL, because matching on shared or sufficient values is what rules do well and OWL does clumsily. Parts in `data/catalog.ttl` carry attributes (socket, ramGen, formFactor, interface, lengths, wattage, draw, recommendedPsu); a `Build` groups chosen parts via `hasPart`. The seven rules in `rules/`:

- **Equality** (`01-socket`, `02-ramgen`, `03-interface`): parts match on a shared attribute.
- **Set-containment** (`04-formfactor`, `05-gpu-length`): a board's form factor is in the set a case accepts; a GPU's length is within a case's clearance.
- **Numeric threshold** (`06-gpu-psu`): a PSU meets a GPU's recommended wattage.
- **Whole-build aggregation** (`07-build-power`): sums draw across a build's parts and compares to its PSU, emitting `powerOk`. Needs the build-as-a-node model, not a pairwise edge.

Rules emit `tdy:fitsWith` (made symmetric by a post-step in `run-rules.sh`) and `tdy:powerOk`, deliberately distinct predicates from the OWL `tdy:compatibleWith`. So one graph holds both kinds of compatibility and a query can still tell them apart:

```sparql
SELECT ?s ?type ?o WHERE {
  { ?s tdy:compatibleWith ?o BIND("owl-reasoned" AS ?type) }
  UNION
  { ?s tdy:fitsWith ?o BIND("rule-derived" AS ?type) }
}
```

Both mechanisms precompute their facts and serve them static; the endpoint runs no reasoner at query time. Cheap deductions could run live, but precomputing the expensive ones is how this scales.

## Data intake

Parts arrive as CSVs (one per type, `data/csv/`), not hand-written Turtle.

- `src/validate_csv.py` checks every row first: required columns, integer fields. It names file, row, and column on failure and exits non-zero.
- `src/intake.py` maps each validated row to typed triples with rdflib, so output is always well-formed (strings plain, integers typed, multi-valued cells split, build parts as IRIs). The generated `data/catalog.ttl` was verified triple-for-triple identical to the hand-written original.

`rebuild-catalog.sh` wires the chain: validate, generate, run rules. Edit a CSV, run it, and the derived facts update; add one GPU row and its `fitsWith` edges appear without writing a compatibility triple. Plain Python is deliberate over a mapping framework like RML: at this scale, with homogeneous per-type sources, a small tested script is simpler and just as rigorous.

## Visualization

`viz/index.html` is a self-contained D3 force-directed view. With the container running, open it (or `python3 -m http.server 8080 --directory viz`) and it queries the live endpoint, drawing parts as nodes colored by type and edges colored by mechanism: green for OWL-reasoned `compatibleWith`, yellow for rule-derived `fitsWith`. The two paradigms show up as two visually distinct subgraphs. Scroll to zoom, drag to pan or move nodes.

## Natural-language queries (local LLM)

`rag/` adds an English-to-SPARQL layer. A question becomes a schema-aware prompt, the model writes SPARQL, a guardrail confirms it is a read-only SELECT, the endpoint runs it, and the results are phrased back in plain language. It shows all three: the generated query, the raw results, the answer. The graph stays the source of truth; the model only translates, so it cannot invent compatibility.

The LLM is isolated behind a one-function contract (`complete(prompt) -> str`) in `rag/backends/`, selected in `.env`. Swapping providers means adding one ~10-line file. The reference setup runs fully offline against a local Ollama model (`qwen2.5-coder`), no API key, no cloud. A Gemini backend is included as a second example.

```
python3 -m rag.ask "what fits the b560 motherboard?"
```

Requires three things up: the container (endpoint), Ollama (model), and the venv (code).

## Layout

```
ontology/parts.ttl              OWL/RDFS ontology
data/inventory.ttl              listing demo dataset
data/valid.ttl / invalid.ttl    SHACL fixtures
data/csv/                        intake source: one CSV per part type
data/catalog.ttl                generated parts graph (from CSVs)
data/catalog-inferred.ttl       rule-derived fitsWith / powerOk facts
shapes/listing-shapes.ttl       SHACL shapes (both validators)
src/validate.py                 load, reason, validate, query (SHACL)
src/validate_csv.py             CSV row validation
src/intake.py                   CSV to typed triples
rebuild-catalog.sh              validate, generate, run rules
rules/*.rq                      SPARQL compatibility rules
rules/symmetry/                 fitsWith symmetry pass
jena/run-rules.sh               runs rules, writes catalog-inferred.ttl
jena/reasoner/                  Maven + OWL API + HermiT offline materializer
jena/fuseki/*.ttl               Fuseki configs (rdfs / owl / served / docker)
jena/Dockerfile                 multi-stage: load TDB2, then serve
viz/index.html                  D3 graph visualization
rag/                            English-to-SPARQL layer (agnostic LLM backend)
docker-compose.yml              one-command standup
```

## Run it

**Served endpoint (Docker only):**

```
docker compose up -d   # wait a few seconds for Fuseki

curl -s http://localhost:3030/tdyparts/sparql -H 'Accept: text/csv' \
  --data-urlencode 'query=PREFIX tdy: <https://tdytrading.example/parts#>
SELECT ?part WHERE { tdy:board_b560 tdy:fitsWith ?part }'

docker compose down
```

The image builds the TDB2 store from five TTLs (ontology, listing data + HermiT inferences, catalog + rule-derived facts) and serves it. No Java or Jena install needed.

**Python (validate, intake):** `pip install -r requirements.txt`, then `python src/validate.py` and `pytest -q`, or `./rebuild-catalog.sh` to regenerate the catalog from CSVs.

**Jena manually (no Docker):** needs Java 21 and Apache Jena/Fuseki 6.1.0. Swap inference layers by pointing `fuseki-server --config` at a file in `jena/fuseki/`. The HermiT reasoner (`jena/reasoner/`) builds with `mvn package` on Java 17 (OWL API 5.x predates Java 21), a build-time tool decoupled from the Java 21 serving stack.

## The model

**Listing side.** CPU, GPU, RAM, Storage, Motherboard are subclasses of `Component`. A `Listing` sells one component, has one condition (new/used/refurb/forparts), and one seller. A `GradedListing` adds a 1..10 grade and is never sold for parts. The reasoning constructs are `compatibleWith` (symmetric), `MotherboardCompatible` (defined class), and `offersCompatible` (property chain).

**Build side.** A `Part` superclass covers every physical part (Component plus `PSU`, `Case`). Parts carry plain-literal attributes the rules match on; a `Build` groups parts via `hasPart`, enabling whole-build power reasoning.

## Validation (SHACL)

`shapes/listing-shapes.ttl` runs through both pySHACL and Jena's `shacl` command, same file, same verdicts. It passes `data/valid.ttl` and flags all six broken records in `data/invalid.ttl`. SHACL does no reasoning of its own, so validation includes the ontology alongside the data for the class hierarchy. SHACL checks shape; the reasoner derives truth; separate layers.

## Notes

- Versions: Apache Jena + Fuseki 6.1.0 (Java 21), HermiT via OWL API 5.1.x (Java 17), Ollama with qwen2.5-coder.
- Openllet was rejected (last release 2019, won't load in Fuseki 6); offline HermiT through the OWL API is the maintained path.
- The Dockerfile pulls Jena from `archive.apache.org` for reproducibility after a release rolls over.
- `.env` (LLM backend, keys) is gitignored.
