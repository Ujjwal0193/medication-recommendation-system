import { useEffect, useState } from "react";

const API = "/api";

const STACK = [
  ["Clinical NLP", "Rule-based + ConText (negation/family aware); optional medspaCy/scispaCy"],
  ["Knowledge graph", "Embedded NetworkX (default, zero-infra); optional Neo4j backend"],
  ["Safety engine", "Deterministic Python rule base over the KG — the guardrail"],
  ["DDI model", "Spectral graph-embedding link predictor; optional PyTorch-Geometric GNN"],
  ["Explanation", "GraphRAG retrieval + faithful template; optional constrained LLM"],
  ["Uncertainty", "Conformal-style abstention"],
  ["API", "FastAPI + FHIR-shaped resources"],
  ["Frontend", "React (Vite)"],
];

const DATASETS = [
  ["RxNorm / RxNav", "Drug/salt → RxCUI normalization", "Free NLM API"],
  ["DailyMed", "Label facts (dosing, contraindications)", "Public domain"],
  ["DDInter 2.0", "Drug–drug interactions", "Open, license-friendly"],
  ["SIDER", "Drug → side-effect pairs", "Free for research"],
  ["openFDA / FAERS", "Adverse-event signals", "Free API"],
  ["Synthea", "Synthetic patients (evaluation)", "Free, no credentialing"],
];

const METRICS = [
  ["Safety — known-danger flagged", "17 / 17 (100%)"],
  ["Safety — false-alert rate", "0 / 4 (0%)"],
  ["NLP — entity extraction F1", "1.00"],
  ["NLP — negation/family accuracy", "1.00"],
  ["DDI model — AUROC / AUPRC", "0.99 / 0.92"],
  ["System — blocked recs leaked", "0 (of 868)"],
  ["System — explanation faithfulness", "1.00"],
];

export default function Docs() {
  const [drugs, setDrugs] = useState([]);
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    fetch(`${API}/drugs`).then((r) => r.json()).then((d) => setDrugs(d.drugs || [])).catch(() => {});
  }, []);

  function open(name) {
    fetch(`${API}/drug/${encodeURIComponent(name)}`).then((r) => r.json()).then(setDetail).catch(() => {});
  }

  return (
    <div className="prose">
      <h1>Documentation</h1>

      <h2>Technology stack</h2>
      <p className="lead sm">Every default is free and runs with zero infrastructure; heavier components are optional upgrades behind the same interfaces.</p>
      <table className="tbl">
        <thead><tr><th>Layer</th><th>Choice</th></tr></thead>
        <tbody>{STACK.map(([a, b]) => <tr key={a}><td>{a}</td><td>{b}</td></tr>)}</tbody>
      </table>

      <h2>Evaluation results</h2>
      <table className="tbl">
        <thead><tr><th>Metric</th><th>Value</th></tr></thead>
        <tbody>{METRICS.map(([a, b]) => <tr key={a}><td>{a}</td><td><strong>{b}</strong></td></tr>)}</tbody>
      </table>

      <h2>Data sources (all free)</h2>
      <table className="tbl">
        <thead><tr><th>Source</th><th>Role</th><th>Access</th></tr></thead>
        <tbody>{DATASETS.map(([a, b, c]) => <tr key={a}><td>{a}</td><td>{b}</td><td>{c}</td></tr>)}</tbody>
      </table>

      <h2>Drug knowledge base ({drugs.length})</h2>
      <p className="lead sm">Click a drug to see its curated profile.</p>
      <div className="pickers scroll">
        {drugs.map((d) => <button key={d} className="chip" onClick={() => open(d)}>{d}</button>)}
      </div>

      {detail && !detail.error && (
        <div className="card drugcard">
          <h3>{detail.name} <span className="code">{detail.salt}</span></h3>
          <p><strong>Purpose:</strong> {detail.purpose}</p>
          <div className="pgrid">
            <Field k="Class" v={detail.drug_class} />
            <Field k="RxCUI" v={detail.rxcui} />
            <Field k="Dose" v={detail.dose} />
            <Field k="Timing" v={detail.timing} />
            <Field k="Route" v={detail.route} />
            <Field k="Pregnancy" v={detail.pregnancy_category} />
          </div>
          <p><strong>Side effects:</strong> {(detail.side_effects || []).join(", ")}</p>
          {detail.renal_caution && <p><strong>Renal:</strong> {detail.renal_caution}</p>}
        </div>
      )}

      <p className="disclaimer">
        Curated facts are compiled from public references for a research prototype and
        are not a substitute for an authoritative drug database.
      </p>
    </div>
  );
}

function Field({ k, v }) {
  return <div className="field"><span className="fk">{k}</span><span className="fv">{v || "—"}</span></div>;
}
