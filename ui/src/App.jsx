import { useState } from "react";

const STATUS_META = {
  allow: { label: "Suitable", cls: "allow", icon: "✅" },
  warn: { label: "Use with caution", cls: "warn", icon: "⚠️" },
  downgrade: { label: "Caution — not preferred", cls: "downgrade", icon: "⚠️" },
  block: { label: "Not recommended", cls: "block", icon: "❌" },
};

const EXAMPLES = [
  "32, pregnant, severe cramps and fever, history of low BP and high sugar",
  "58 year old man with high blood pressure and type 2 diabetes, on metformin",
  "70 yo with heart failure and chronic kidney disease, on lisinopril",
  "28 year old pregnant woman with a urinary tract infection, allergic to penicillin",
];

export default function App() {
  const [text, setText] = useState(EXAMPLES[0]);
  const [consent, setConsent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);

  async function submit() {
    setError("");
    if (!consent) {
      setError("Please acknowledge the consult-a-doctor consent note before continuing.");
      return;
    }
    setLoading(true);
    setData(null);
    try {
      const res = await fetch("/api/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, consent }),
      });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(`Could not reach the MediGuard API. Is it running on :8000?  (${e.message})`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="wrap">
      <header>
        <h1>🛡️ MediGuard</h1>
        <p className="tag">Safe, explainable medication decision support — advisory only.</p>
      </header>

      <section className="card">
        <label className="lbl">Patient report (free text)</label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          placeholder="e.g. 32, pregnant, fever and cramps, high sugar…"
        />
        <div className="examples">
          {EXAMPLES.map((ex) => (
            <button key={ex} className="chip" onClick={() => setText(ex)}>
              {ex.slice(0, 42)}…
            </button>
          ))}
        </div>

        <label className="consent">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          I understand this is advisory only and I will consult a doctor before acting.
        </label>

        <button className="go" onClick={submit} disabled={loading}>
          {loading ? "Analyzing…" : "Get recommendations"}
        </button>
        {error && <p className="err">{error}</p>}
      </section>

      {data && <Results data={data} />}
    </div>
  );
}

function Results({ data }) {
  const p = data.profile;
  return (
    <section className="results">
      <div className="profile card">
        <h3>Understood patient profile</h3>
        <div className="pgrid">
          <Field k="Age" v={p.age} />
          <Field k="Pregnant" v={p.pregnant === null ? "—" : String(p.pregnant)} />
          <Field k="Conditions" v={(p.conditions || []).map((c) => c.display || c.code).join(", ") || "—"} />
          <Field k="Current meds" v={(p.current_meds || []).map((m) => m.name).join(", ") || "—"} />
          <Field k="Allergies" v={(p.allergies || []).map((a) => a.display || a.code).join(", ") || "—"} />
        </div>
      </div>

      {data.results.map((cond) => (
        <div key={cond.condition_code} className="card">
          <h3>
            {cond.condition_display}{" "}
            <span className="code">({cond.condition_code})</span>
          </h3>
          {cond.abstain && (
            <div className="abstain">🧑‍⚕️ Defer to clinician: {cond.abstain_reason}</div>
          )}
          <div className="recs">
            {cond.recommendations.map((rec, i) => {
              const meta = STATUS_META[rec.status] || STATUS_META.warn;
              return (
                <div key={i} className={`rec ${meta.cls}`}>
                  <div className="rec-head">
                    <span className="drug">{meta.icon} {rec.drug}</span>
                    <span className={`badge ${meta.cls}`}>{meta.label}</span>
                    {rec.abstain && <span className="badge muted">deferred</span>}
                  </div>
                  <div className="conf">confidence {(rec.confidence * 100).toFixed(0)}%</div>
                  {rec.reasons.length > 0 && (
                    <ul className="reasons">
                      {rec.reasons.map((r, j) => (
                        <li key={j} className={`sev-${r.severity}`}>{r.message}</li>
                      ))}
                    </ul>
                  )}
                  <details>
                    <summary>Explanation</summary>
                    <pre className="rationale">{rec.rationale}</pre>
                  </details>
                </div>
              );
            })}
          </div>
        </div>
      ))}

      <p className="disclaimer">{data.disclaimer}</p>
    </section>
  );
}

function Field({ k, v }) {
  return (
    <div className="field">
      <span className="fk">{k}</span>
      <span className="fv">{v === null || v === undefined || v === "" ? "—" : v}</span>
    </div>
  );
}
