# Part 9 — Decision Memo

### 1. What exactly did you change between each pair of runs?
- **A -> B:** Added structured JSON output contracts and Pydantic schema into the system prompt.
- **B -> E:** Enforced Constrained Decoding at token generation time to guarantee valid JSON matching the schema.

### 2. Which dimension moved, and by how much?
- **Parseability:** Jumped from **8%** (A naive) to **100%** (B & E).
- **Schema Compliance:** Increased from **0%** (A) to **75%** (B) and **100%** under constrained decoding (E).
- **Latency:** Decreased from **25.4s** (A) to **19.4s** (B).

### 3. Which technique would you ship, and at what latency per call?
- **Ship:** **Technique E (Constrained Decoding)** with System Prompt constraints.
- **Latency:** ~19.4 seconds per call.

### 4. Which failure remains, and which gate catches it?
- **Remaining Failure:** Semantic mismatches (`refers`) when context/evidence is insufficient or ambiguous.
- **Catching Gate:** Evaluation validation functions and downstream application logic checks.

### 5. What would make you revert this choice?
- High generation latency under heavy load, excessive memory overhead from grammar-guided sampling, or if an upgraded frontier model achieves near-perfect schema execution natively.

### 6. What did the measurement not tell you?
- **Model Scale:** Tested on a small ~1.5B model, which behaves differently from large frontier models.
- **Sample Size:** Evaluation was run on a single individual's subset (smoke test), not a full production-grade test suite.
- **Variance:** Ran only once using greedy decoding, so there is no variance estimate.
