#!/usr/bin/env python3
"""load the parts graph, reason over it, validate with shacl, run a couple of queries.
exits non-zero when the data does not conform so it works as a ci gate."""

import sys
from pathlib import Path

from rdflib import Graph
from pyshacl import validate

ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY = ROOT / "ontology" / "parts.ttl"
SHAPES = ROOT / "shapes" / "listing-shapes.ttl"
DATA = ROOT / "data" / "inventory.ttl"

TDY = "https://tdytrading.example/parts#"


def load(path):
    g = Graph()
    g.parse(path, format="turtle")
    print(f"loaded {path.relative_to(ROOT)}: {len(g)} triples")
    return g


def run_queries(data, ontology):
    # combine so rdfs subclass facts are visible to the queries
    g = data + ontology

    print("\nused components priced under $50:")
    q1 = """
        PREFIX tdy: <https://tdytrading.example/parts#>
        SELECT ?listing ?price WHERE {
            ?listing tdy:hasCondition tdy:Used ;
                     tdy:sells ?c ;
                     tdy:priceUSD ?price .
            FILTER (?price < 50)
        }
    """
    for row in g.query(q1):
        print(f"  {row.listing.split('#')[-1]}  ${row.price}")

    print("\nlistings per condition:")
    # group by the condition iri, format the local name ourselves.
    # joining on rdfs:label here trips an rdflib aggregate quirk when a value has no label.
    q2 = """
        PREFIX tdy: <https://tdytrading.example/parts#>
        SELECT ?cond (COUNT(?listing) AS ?n) WHERE {
            ?listing tdy:hasCondition ?cond .
        } GROUP BY ?cond
    """
    for row in g.query(q2):
        print(f"  {row.cond.split('#')[-1]}: {row.n}")


def main():
    ontology = load(ONTOLOGY)
    shapes = load(SHAPES)
    data = load(DATA)

    conforms, _, report = validate(
        data,
        shacl_graph=shapes,
        ont_graph=ontology,
        inference="rdfs",
        advanced=True,
    )

    print(f"\nconforms: {conforms}")
    if not conforms:
        print(report)

    run_queries(data, ontology)

    sys.exit(0 if conforms else 1)


if __name__ == "__main__":
    main()
