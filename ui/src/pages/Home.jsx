import { Link } from "react-router-dom";

const FEATURES = [
  { icon: "🧠", title: "Reads the patient", body: "Clinical NLP turns free-text reports into coded profiles — handling negation (\"no chest pain\") and family history (\"father has heart disease\") correctly." },
  { icon: "🛡️", title: "Rules are the authority", body: "A deterministic rule engine over a knowledge graph checks interactions, contraindications, dosing and duplicates. It can block or downgrade any suggestion." },
  { icon: "🔬", title: "ML suggests, never decides", body: "A graph-based model flags possible undocumented interactions — as warnings only. A confidence gate guarantees it can never override a safety block." },
  { icon: "💬", title: "Explains every choice", body: "A GraphRAG layer writes plain-language rationale using only verified knowledge-graph facts, so the reasoning is faithful and auditable." },
  { icon: "🧑‍⚕️", title: "Defers when unsure", body: "Conformal-style abstention says \"defer to a clinician\" when the safest option still carries real risk. Every output ends with a consult-a-doctor note." },
  { icon: "🔌", title: "Interoperable by design", body: "A FastAPI service exposes FHIR-shaped resources (MedicationRequest, Condition, Observation), positioning it for EHR integration." },
];

const METRICS = [
  { v: "100%", k: "known-danger combinations flagged", sub: "0 false alerts" },
  { v: "1.00", k: "NLP entity-extraction F1", sub: "on the gold set" },
  { v: "0.99", k: "DDI model AUROC", sub: "held-out links" },
  { v: "0", k: "unsafe recs ever actionable", sub: "over 868 recommendations" },
];

export default function Home() {
  return (
    <>
      <section className="hero">
        <div className="pill">Neuro-symbolic clinical decision support</div>
        <h1>The machine understands and suggests.<br />The rules — and a doctor — decide.</h1>
        <p className="lead">
          MediGuard reads a patient's report, recommends medication through a knowledge
          graph, and passes every suggestion through a deterministic safety engine that
          checks drug–drug interactions, contraindications, pregnancy, dosing and
          duplicate therapy before anything is shown.
        </p>
        <div className="cta">
          <Link className="btn primary" to="/demo">Try the live demo →</Link>
          <Link className="btn ghost" to="/about">How it works</Link>
        </div>
      </section>

      <section className="metrics">
        {METRICS.map((m) => (
          <div key={m.k} className="metric">
            <div className="mv">{m.v}</div>
            <div className="mk">{m.k}</div>
            <div className="msub">{m.sub}</div>
          </div>
        ))}
      </section>

      <section className="features">
        <h2>What makes it safe <em>and</em> smart</h2>
        <div className="fgrid">
          {FEATURES.map((f) => (
            <div key={f.title} className="fcard">
              <div className="ficon">{f.icon}</div>
              <h3>{f.title}</h3>
              <p>{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="arch">
        <h2>The pipeline</h2>
        <div className="flow">
          {["Patient text + fields", "Clinical NLP", "Candidate drugs", "SAFETY AUTHORITY (veto)", "ML warnings-only", "Abstain if unsure", "Explained recommendation"].map((step, i, a) => (
            <div key={step} className={`node ${step.includes("SAFETY") ? "guard" : ""}`}>
              {step}
              {i < a.length - 1 && <span className="arrow">↓</span>}
            </div>
          ))}
        </div>
        <p className="archnote">
          The Safety Authority is the only component that decides safety. No ML or LLM
          output can turn a <span className="block-word">BLOCK</span> into an actionable
          recommendation — an invariant enforced in three independent places in code.
        </p>
      </section>
    </>
  );
}
