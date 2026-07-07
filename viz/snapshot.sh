#!/usr/bin/env bash
# Snapshot the graph the viz pages draw into viz/data.json so GitHub Pages
# (no Fuseki) can serve it. Run after rebuilding the container.
set -euo pipefail
cd "$(dirname "$0")"
curl -sf http://localhost:3030/tdyparts/sparql \
  -H 'Accept: application/sparql-results+json' \
  --data-urlencode 'query=
PREFIX tdy: <https://tdytrading.example/parts#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?s ?sType ?p ?o ?oType WHERE {
  { ?s tdy:compatibleWith ?o . BIND(tdy:compatibleWith AS ?p) }
  UNION
  { ?s tdy:fitsWith ?o . BIND(tdy:fitsWith AS ?p) }
  OPTIONAL { ?s rdf:type ?sType }
  OPTIONAL { ?o rdf:type ?oType }
}' > data.json
echo "wrote viz/data.json ($(wc -c < data.json) bytes)"
