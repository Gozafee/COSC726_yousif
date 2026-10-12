# Decision Memo — Lab 5: Give Layla Memory

## Ablation table (6 questions, k = 3, tokens = average per question)

| configuration | recall | precision | answered | tokens |
|---|---|---|---|---|
| no memory at all | 0% | 0% | 0% | 1 |
| fixed + keyword | 67% | 33% | 50% | 94 |
| recursive + keyword | 83% | 47% | 67% | 112 |
| recursive + embeddings | 100% | 64% | 83% | 97 |
| parent-child + embeddings | 100% | 64% | 83% | 148 |
| recursive + embeddings + episodic | 100% | 64% | 100% | 172 |
| recursive + embeddings + epi + sem | 100% | 64% | 100% | 184 |
| everything | 100% | 64% | 100% | 223 |

## 1. Which layer helped most, and on which questions?

Retrieval helped most, not a memory layer. Going from no memory (0% answered) to
recursive chunking with embeddings (83% answered) is the largest jump in the table.
Within retrieval, two choices mattered:

- **Chunking:** sentence-level (recursive) beat fixed-size with the same keyword
  retriever (recall 67% → 83%, answered 50% → 67%). Fixed chunks can split the
  threshold from the approval rule in POL-LATE, which hurts Q2.
- **Embeddings over keywords:** recall 83% → 100% and answered 67% → 83%, at
  *fewer* tokens (112 → 97). The gain is on the paraphrase question, Q5
  ("charged twice" vs "duplicate charges", no shared word).

Among the memory layers, **episodic** was the only one that helped: answered
83% → 100% (+17 points, one question, Q6), for +75 tokens per question.

## 2. Which layer made things worse, and how do I know?

Semantic and procedural memory made things worse. Answered stayed at 100% while
tokens rose from 172 → 184 (+semantic) → 223 (+procedural): +51 tokens per
question for zero gain. None of the six questions asks about contact preference
or the late-delivery escalation rule, yet both layers inject lines into every
context. That is a measurable regression, a cost with no benefit on this question
set.

Parent-child chunking is the same kind of finding: recall, precision and answered
are identical to recursive + embeddings, but tokens go 97 → 148 (+53%) because it
returns whole parent documents. On five short documents, "large for
understanding" buys nothing.

I know this from the answered and tokens columns read together, not from either
alone.

## 3. Where did embeddings beat keywords, and what would I do in production?

Embeddings beat keywords on recall (83% → 100%) and answered (67% → 83%). The
case the lab is designed around is Q5, where there is no lexical overlap. The
keyword retriever still returned plausible documents for it, a confident wrong
answer, which is harder to debug than an empty result.

In production I would use **hybrid retrieval** (keyword + embeddings merged),
because keywords are cheap, exact on identifiers and policy terms, and
competitive on a small corpus, while embeddings cover paraphrase. I would store
the embedding model name and dimension with the index and re-index on any
change, since 768-dim and 1536-dim vectors cannot be mixed.

## 4. What did episodic memory make possible that retrieval could not?

Q6 ("second complaint this month about the same order"). No policy document can
say whether *this customer* has complained before; that is a fact about history,
not about policy. The episodic store holds two late-delivery episodes for
cust-4417 inside 60 days, and `count_since` returns 2, which is exactly the
condition POL-ESCALATE ("more than once in sixty days") needs. Retrieval finds
the rule; episodic memory supplies the case it applies to.

## 5. Where does memory access sit in my authorisation model?

Memory access is an authorisation decision, enforced in the **store**: every read
and write requires a `MemoryScope` with a `user_id`, and a scopeless access raises
`ScopeError` instead of returning an empty list (an empty list would hide a
bug that is a data-protection incident). The isolation test shows Alice's and
Bob's recalls are disjoint and that scopeless reads raise.

Limit of what I proved: the store trusts the scope it is given. A write with the
wrong `user_id` would be accepted. So the `user_id` must come from the
authenticated session, never from the request body or the model's tool
arguments, and the check should also exist in the tool layer (defence in depth).

## 6. What did the measurement not tell me?

- **Five short documents is not a corpus** and six questions written by one
  person is a smoke test. 100% recall here says little about a real corpus.
- **My "answered" metric is generous.** It counts an answer when the right
  document was retrieved and a required word appears in the context. No model
  read the context, so it does not test whether the answer would be correct.
- **Q6's episodic gain is partly by construction.** I required an episodic line
  in the context for Q6 (no document can answer it), so the +17 points at the
  episodic row is close to guaranteed. It shows episodic memory is *necessary*
  for Q6, not how much it helps in practice.
- **Episodic recall injects the customer's latest episodes on every question**,
  relevant or not; a smarter filter might lower the +75 token cost.
- **The reader is deterministic**, so there is no variance to measure, and
  `nomic-embed-text` is one embedding model: swapping it changes every number
  and invalidates the index.
- **Token counts are approximate** (characters ÷ 4), good for comparing rows,
  not for billing.
- Nothing here tests stale or poisoned memory over time (Stretch 1): a false
  fact written through the normal path is indistinguishable from a real one.
