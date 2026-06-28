import sys
import re
import json
import urllib.parse
import urllib.request
from rag.llm import complete
from rag.schema import build_prompt

ENDPOINT = "http://localhost:3030/tdyparts/sparql"
FORBIDDEN = ("INSERT", "DELETE", "DROP", "CLEAR", "LOAD", "CREATE")


def extract_sparql(text):
    text = re.sub(r"^```(?:sparql)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return text


def is_safe(query):
    up = query.upper()
    if not re.search(r"\bSELECT\b", up):
        return False
    return not any(re.search(rf"\b{w}\b", up) for w in FORBIDDEN)


def run_query(query):
    data = urllib.parse.urlencode({"query": query}).encode()
    req = urllib.request.Request(
        ENDPOINT, data=data,
        headers={"Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def format_results(results):
    vars_ = results["head"]["vars"]
    rows = results["results"]["bindings"]
    if not rows:
        return "(no results)"
    out = []
    for row in rows:
        out.append("  " + ", ".join(f"{v}={row[v]['value'].split('#')[-1]}"
                                    for v in vars_ if v in row))
    return "\n".join(out)


def fetch_ids():
    q = ("PREFIX tdy: <https://tdytrading.example/parts#> "
         "SELECT ?s WHERE { ?s a ?t FILTER(STRSTARTS(STR(?t), STR(tdy:))) } ORDER BY ?s")
    try:
        res = run_query(q)
        ids = [b["s"]["value"].split("#")[-1] for b in res["results"]["bindings"]]
        return ", ".join(f"tdy:{i}" for i in ids)
    except Exception:
        return ""


def ask(question):
    sparql = extract_sparql(complete(build_prompt(question, fetch_ids())))
    print("\n--- generated SPARQL ---")
    print(sparql)

    if not is_safe(sparql):
        print("\nREFUSED: generated query is not a read-only SELECT.")
        return

    try:
        results = run_query(sparql)
    except Exception as e:
        print(f"\nquery failed: {e}")
        return

    print("\n--- results ---")
    print(format_results(results))

    answer_prompt = (
        f"Question: {question}\n"
        f"SPARQL results (JSON): {json.dumps(results['results']['bindings'])}\n"
        f"Answer the question in one or two plain sentences using only these results. "
        f"Use short part names, not full URIs.")
    print("\n--- answer ---")
    print(complete(answer_prompt).strip())


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or input("question: ")
    ask(q)
