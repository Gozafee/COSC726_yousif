import re

import lab6_kit as K
from lab6_kit import (MemoryScope, EpisodicStore, SemanticStore,
                      ProceduralStore, ScopeError, AblationRow)

INSUFFICIENT = "insufficient evidence"
NEEDS_EPISODIC = {"Q6"}


# ---------------- Task 1 ----------------
def make_search_tool(retriever, parents=None):
    def search_policy(query: str, k: int = 3) -> dict:
        if not isinstance(query, str) or len(query.strip()) < 3:
            return {"ok": False, "error": "query_too_short",
                    "message": "Query must be at least 3 characters."}
        try:
            hits = retriever.retrieve(query.strip(), k=k)
        except Exception as exc:
            return {"ok": False, "error": "retrieval_failed", "message": str(exc)}
        if not hits:
            return {"ok": False, "error": "no_match",
                    "message": "No policy passage matched this query."}
        passages, seen = [], set()
        for c in hits:
            if parents is not None and c.parent_id in parents:
                if c.parent_id in seen:
                    continue
                seen.add(c.parent_id)
                text = parents[c.parent_id]
            else:
                text = c.text
            passages.append({"doc_id": c.doc_id, "chunk_id": c.chunk_id, "text": text})
        return {"ok": True, "passages": passages,
                "evidence_ids": [p["chunk_id"] for p in passages]}
    return search_policy


# ---------------- Task 2 ----------------
def seed_memory():
    ep, sem, proc = EpisodicStore(), SemanticStore(), ProceduralStore()
    alice = MemoryScope(user_id="cust-4417")
    bob = MemoryScope(user_id="cust-9001")

    e1 = ep.write(alice, what="Late delivery on order ORD-1001, 4 days late",
                  action="proposed 10% credit for supervisor approval",
                  outcome="credit approved by supervisor",
                  when="2026-06-10", provenance=["ORD-1001"])
    e2 = ep.write(alice, what="Late delivery on order ORD-1042, 5 days late",
                  action="proposed 10% credit for supervisor approval",
                  outcome="credit approved by supervisor",
                  when="2026-07-05", provenance=["ORD-1042"])
    ep.write(bob, what="Address change request for order ORD-2001",
             action="changed address at depot after identity confirmation",
             outcome="address updated", when="2026-07-02", provenance=["ORD-2001"])

    sem.write(alice, "contact_preference", "email", asserted="2026-03-01")
    sem.write(alice, "contact_preference", "sms", asserted="2026-07-10")
    sem.write(bob, "contact_preference", "phone", asserted="2026-06-15")

    proc.propose("RULE-LATE-REPEAT",
                 when="a customer has two or more late deliveries within 60 days",
                 then="escalate to a human supervisor and attach both order histories",
                 provenance=[e1.episode_id, e2.episode_id])
    proc.review("RULE-LATE-REPEAT", approve=True)
    return ep, sem, proc


# ---------------- Task 3 ----------------
def isolation_test(ep, sem):
    alice = MemoryScope(user_id="cust-4417")
    bob = MemoryScope(user_id="cust-9001")
    a = ep.recall(alice, k=99)
    b = ep.recall(bob, k=99)
    assert a and b, "both users must have episodes"
    assert all(e.scope.user_id == "cust-4417" for e in a)
    assert all(e.scope.user_id == "cust-9001" for e in b)
    assert not ({e.episode_id for e in a} & {e.episode_id for e in b})
    assert all(e.scope.user_id == "cust-4417"
               for e in ep.recall(alice, about="order", k=99))
    fa = sem.get(alice, "contact_preference")
    fb = sem.get(bob, "contact_preference")
    assert fa.scope.user_id == "cust-4417" and fb.scope.user_id == "cust-9001"
    assert fa.value != fb.value
    for bad in (None, MemoryScope()):
        for fn in (lambda s=bad: ep.recall(s),
                   lambda s=bad: sem.get(s, "contact_preference")):
            try:
                fn()
            except ScopeError:
                pass
            else:
                raise AssertionError("scopeless read did not raise ScopeError")


# ---------------- Task 4 ----------------
def _approx_tokens(text):
    return max(1, round(len(text) / 4))


def _has_term(text, term):
    return re.search(r"\b" + re.escape(term.lower()) + r"\b", text.lower()) is not None


def answer(q, retriever, parents, ep, sem, proc, scope,
           use_episodic, use_semantic, use_procedural):
    lines, got_docs, seen = [], set(), set()

    if retriever is not None:
        for c in retriever.retrieve(q.question, k=3):
            got_docs.add(c.doc_id)
            if parents is not None and c.parent_id in parents:
                if c.parent_id in seen:
                    continue
                seen.add(c.parent_id)
                text, tag = parents[c.parent_id], c.parent_id
            else:
                text, tag = c.text, c.chunk_id
            lines.append(f"[DOC {tag}] {text}")

    if use_episodic:
        for e in ep.recall(scope, k=3):
            lines.append(f"[EPISODE {e.episode_id} {e.when}] {e.what}; {e.action}; {e.outcome}")

    if use_semantic:
        f = sem.get(scope, "contact_preference")
        if f:
            lines.append(f"[FACT {f.key}={f.value} since {f.asserted}]")

    if use_procedural:
        for p in proc.active():
            lines.append(f"[RULE {p.rule_id}] when {p.when}, then {p.then}")

    ctx = "\n".join(lines)
    tokens = _approx_tokens(ctx)

    authoritative = bool(q.gold_docs & got_docs)
    has_term = any(_has_term(ctx, t) for t in q.gold_answer_contains)
    has_history = any(l.startswith("[EPISODE") for l in lines)
    needs_history = q.qid in NEEDS_EPISODIC

    ok = authoritative and has_term and (has_history or not needs_history)
    return (ctx if ok else INSUFFICIENT), tokens


def run_ablation(embedder):
    scope = MemoryScope(user_id="cust-4417")
    ep, sem, proc = seed_memory()
    docs = K.POLICY_DOCS

    fixed = K.chunk_fixed(docs)
    recursive = K.chunk_recursive(docs)
    children, parents = K.chunk_parent_child(docs)

    configs = [
        ("no memory at all", None, None),
        ("fixed + keyword", K.KeywordRetriever(fixed), None),
        ("recursive + keyword", K.KeywordRetriever(recursive), None),
        ("recursive + embeddings",
         K.ChromaRetriever(recursive, embedder, collection="cosc726-abl-rec"), None),
        ("parent-child + embeddings",
         K.ChromaRetriever(children, embedder, parents=parents,
                           collection="cosc726-abl-pc"), parents),
    ]

    def measure(name, retriever, par, e=False, s=False, p=False):
        answered, tokens = 0, 0
        for q in K.QUESTIONS:
            out, t = answer(q, retriever, par, ep, sem, proc, scope, e, s, p)
            answered += out != INSUFFICIENT
            tokens += t
        n = len(K.QUESTIONS)
        if retriever is None:
            rec = prec = 0.0
        else:
            sc = K.score_retrieval(retriever, K.QUESTIONS)
            rec, prec = sc["recall"], sc["precision"]
        return AblationRow(name, rec, prec, answered / n, round(tokens / n))

    rows = [measure(*c) for c in configs]
    best_i = max(range(1, len(rows)), key=lambda i: (rows[i].answered, -rows[i].tokens))
    base, base_r, base_p = configs[best_i]
    rows += [
        measure(f"{base} + episodic", base_r, base_p, e=True),
        measure(f"{base} + epi + sem", base_r, base_p, e=True, s=True),
        measure("everything", base_r, base_p, e=True, s=True, p=True),
    ]
    return rows
