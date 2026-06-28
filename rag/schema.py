SCHEMA = """You translate questions about a computer-parts knowledge graph into SPARQL.

Namespace:
  PREFIX tdy: <https://tdytrading.example/parts#>

Part classes (each part is one of these):
  tdy:CPU  tdy:GPU  tdy:RAM  tdy:Storage  tdy:Motherboard  tdy:PSU  tdy:Case
A tdy:Build groups chosen parts via tdy:hasPart.

Raw attributes on parts (literals):
  tdy:socket tdy:ramGen tdy:formFactor tdy:interface (strings)
  tdy:acceptsFormFactor (string, a Case may have several)
  tdy:lengthMm tdy:maxGpuMm tdy:wattage tdy:draw tdy:recommendedPsu (integers)

Derived relationships (ALREADY COMPUTED, just query them, do not reconstruct):
  tdy:fitsWith     part-to-part build compatibility, derived from attributes.
                   e.g. a CPU fitsWith a Motherboard with the same socket;
                   a GPU fitsWith a PSU whose wattage meets its recommendation;
                   a board/GPU fitsWith a Case it physically fits.
  tdy:compatibleWith  symmetric, OWL-reasoned compatibility (the listing demo world).
  tdy:powerOk      a Build has this set true when its PSU covers total draw.

Available part ids (use these EXACT names, do not invent ids):
{ids}

IMPORTANT: compatibility is precomputed. To find what fits a part, query
tdy:fitsWith directly. Do NOT join on shared sockets/wattages to recompute it.

Rules for your output:
- Return ONLY a SPARQL query. No explanation, no markdown fences, no commentary.
- Only SELECT queries. Never INSERT/DELETE/DROP/CLEAR/LOAD/CREATE.
- Always start with the PREFIX line.
- Part ids are local names, e.g. tdy:board_b560, tdy:gpu_big.

Question: {question}

SPARQL:"""


def build_prompt(question, ids=""):
    return SCHEMA.format(question=question, ids=ids)
