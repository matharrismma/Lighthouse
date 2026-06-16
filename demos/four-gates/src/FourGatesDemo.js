import React, { useState } from "react";

const GATES = [
  {
    id: "RED",
    name: "RED GATE",
    subtitle: "Absolute Prohibitions",
    description: "Does this violate any absolute moral boundary?",
    prompt: `You are the RED GATE — the first validation gate in the Four Gates decision protocol. Your sole function is to check whether a proposed action violates any ABSOLUTE moral prohibition.

Absolute prohibitions include: taking innocent life, bearing false witness, theft, exploitation of the vulnerable, blasphemy, idolatry, sexual immorality, and any action that treats a person as merely a means to an end.

You are NOT weighing costs and benefits. You are checking for bright-line violations. If the action crosses ANY absolute prohibition, it FAILS. If it does not cross any, it PASSES.

Respond in this exact JSON format and nothing else:
{"pass": true/false, "reasoning": "2-3 sentences explaining the determination"}`,
    color: "#C62828",
    glow: "rgba(198, 40, 40, 0.3)",
  },
  {
    id: "FLOOR",
    name: "FLOOR GATE",
    subtitle: "Protective Minimums",
    description: "Does this meet the minimum standard of care and protection?",
    prompt: `You are the FLOOR GATE — the second validation gate in the Four Gates decision protocol. You only run if the RED GATE has already passed. Your function is to check whether a proposed action meets MINIMUM PROTECTIVE STANDARDS.

Floor standards include: duty of care toward those affected, basic fairness and due process, protection of the weak and dependent, truthful representation, honoring of existing obligations and covenants, and stewardship of resources entrusted.

You are checking for floors — minimums below which no action should proceed. This is not about optimization. If the action meets all minimum protective standards, it PASSES. If it falls below any floor, it FAILS.

Respond in this exact JSON format and nothing else:
{"pass": true/false, "reasoning": "2-3 sentences explaining the determination"}`,
    color: "#E65100",
    glow: "rgba(230, 81, 0, 0.3)",
  },
  {
    id: "BROTHERS",
    name: "BROTHERS GATE",
    subtitle: "Community Witness",
    description: "Would this withstand the scrutiny of faithful witnesses?",
    prompt: `You are the BROTHERS GATE — the third validation gate in the Four Gates decision protocol. You only run if RED and FLOOR gates have passed. Your function is to evaluate whether a proposed action would withstand COMMUNITY WITNESS AND ACCOUNTABILITY.

The Brothers test asks: Could this action be fully disclosed to a circle of trusted, faithful people and receive their affirmation? Would those who know you best, and who share your values, say "yes, proceed"? Is there anything hidden, rationalized, or self-serving that the light of communal scrutiny would expose?

This gate exists because individuals deceive themselves. The community of witnesses is a safeguard against self-confirmation. If the action would withstand full communal scrutiny, it PASSES. If there is anything that would give faithful witnesses pause, it FAILS.

Respond in this exact JSON format and nothing else:
{"pass": true/false, "reasoning": "2-3 sentences explaining the determination"}`,
    color: "#F9A825",
    glow: "rgba(249, 168, 37, 0.3)",
  },
  {
    id: "GOD",
    name: "GOD GATE",
    subtitle: "Execution Parameters",
    description: "Is this aligned with purpose, calling, and proper authority?",
    prompt: `You are the GOD GATE — the fourth and final validation gate in the Four Gates decision protocol. You only run if RED, FLOOR, and BROTHERS gates have all passed. Your function is to evaluate whether a proposed action is aligned with PURPOSE, CALLING, AND DIVINE AUTHORITY.

The God Gate asks: Is this action within the scope of authority granted to the actor? Is the timing right — is this the proper season? Does it serve the purpose for which the actor has been placed in their role? Is it undertaken in humility, recognizing that execution authority comes from above, not from self?

This is not about whether the action is merely permissible (earlier gates handle that). This is about whether it is RIGHT — the right action, by the right person, at the right time, under proper authority.

If the action appears aligned with purpose and proper authority, it PASSES. If there are concerns about overreach, wrong timing, or misaligned purpose, it FAILS.

Respond in this exact JSON format and nothing else:
{"pass": true/false, "reasoning": "2-3 sentences explaining the determination"}`,
    color: "#FFD600",
    glow: "rgba(255, 214, 0, 0.35)",
  },
];

function GateIndicator({ gate, status, result }) {
  const getStatusIcon = () => {
    if (status === "waiting") return "○";
    if (status === "running") return "◎";
    if (status === "pass") return "✓";
    if (status === "fail") return "✗";
    if (status === "skipped") return "—";
    return "○";
  };

  const getStatusColor = () => {
    if (status === "pass") return "#4CAF50";
    if (status === "fail") return gate.color;
    if (status === "running") return gate.color;
    if (status === "skipped") return "#555";
    return "#444";
  };

  return (
    <div
      style={{
        padding: "20px 24px",
        marginBottom: "2px",
        background:
          status === "running"
            ? `linear-gradient(135deg, ${gate.glow}, rgba(20,20,20,0.95))`
            : status === "pass"
            ? "linear-gradient(135deg, rgba(76,175,80,0.08), rgba(20,20,20,0.95))"
            : status === "fail"
            ? `linear-gradient(135deg, ${gate.glow.replace("0.3", "0.12")}, rgba(20,20,20,0.95))`
            : "rgba(20,20,20,0.6)",
        borderLeft: `3px solid ${getStatusColor()}`,
        transition: "all 0.5s ease",
        opacity: status === "skipped" ? 0.4 : 1,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
        <span
          style={{
            fontSize: "20px",
            fontWeight: 700,
            color: getStatusColor(),
            fontFamily: "'DM Mono', monospace",
            width: "28px",
            textAlign: "center",
            animation: status === "running" ? "pulse 1.2s infinite" : "none",
          }}
        >
          {getStatusIcon()}
        </span>
        <div style={{ flex: 1 }}>
          <div
            style={{
              display: "flex",
              alignItems: "baseline",
              gap: "10px",
              marginBottom: "2px",
            }}
          >
            <span
              style={{
                fontFamily: "'DM Mono', monospace",
                fontSize: "13px",
                fontWeight: 700,
                letterSpacing: "0.12em",
                color: getStatusColor(),
              }}
            >
              {gate.name}
            </span>
            <span
              style={{
                fontFamily: "'Source Serif 4', Georgia, serif",
                fontSize: "12px",
                color: "#888",
                fontStyle: "italic",
              }}
            >
              {gate.subtitle}
            </span>
          </div>
          {status === "running" && (
            <div
              style={{
                fontSize: "12px",
                color: "#777",
                fontFamily: "'DM Mono', monospace",
                marginTop: "4px",
              }}
            >
              Validating...
            </div>
          )}
          {result && (
            <div
              style={{
                fontSize: "13px",
                color: "#bbb",
                lineHeight: 1.6,
                marginTop: "6px",
                fontFamily: "'Source Serif 4', Georgia, serif",
              }}
            >
              {result}
            </div>
          )}
        </div>
        {status === "pass" && (
          <span
            style={{
              fontFamily: "'DM Mono', monospace",
              fontSize: "10px",
              letterSpacing: "0.15em",
              color: "#4CAF50",
              opacity: 0.7,
            }}
          >
            PASS
          </span>
        )}
        {status === "fail" && (
          <span
            style={{
              fontFamily: "'DM Mono', monospace",
              fontSize: "10px",
              letterSpacing: "0.15em",
              color: gate.color,
            }}
          >
            HALT
          </span>
        )}
      </div>
    </div>
  );
}

export default function FourGatesDemo() {
  const [input, setInput] = useState("");
  const [gateStatuses, setGateStatuses] = useState(
    GATES.map(() => ({ status: "waiting", result: null }))
  );
  const [isRunning, setIsRunning] = useState(false);
  const [finalVerdict, setFinalVerdict] = useState(null);
  const [error, setError] = useState(null);

  const runGates = async () => {
    if (!input.trim() || isRunning) return;
    setIsRunning(true);
    setFinalVerdict(null);
    setError(null);
    setGateStatuses(GATES.map(() => ({ status: "waiting", result: null })));

    for (let i = 0; i < GATES.length; i++) {
      const gate = GATES[i];

      setGateStatuses((prev) =>
        prev.map((s, idx) =>
          idx === i ? { status: "running", result: null } : s
        )
      );

      try {
        const response = await fetch("/api/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: [
              {
                role: "user",
                content: `${gate.prompt}\n\nProposed action to evaluate:\n"${input.trim()}"`,
              },
            ],
          }),
        });

        if (!response.ok) {
          throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();

        if (data.error) {
          throw new Error(data.error);
        }

        const text = data.content
          .filter((c) => c.type === "text")
          .map((c) => c.text)
          .join("");

        let parsed;
        try {
          const cleaned = text.replace(/```json|```/g, "").trim();
          parsed = JSON.parse(cleaned);
        } catch {
          parsed = {
            pass: false,
            reasoning: "Gate could not parse response. Halting.",
          };
        }

        const passed = parsed.pass === true;

        setGateStatuses((prev) =>
          prev.map((s, idx) =>
            idx === i
              ? { status: passed ? "pass" : "fail", result: parsed.reasoning }
              : s
          )
        );

        if (!passed) {
          setGateStatuses((prev) =>
            prev.map((s, idx) =>
              idx > i ? { status: "skipped", result: null } : s
            )
          );
          setFinalVerdict({
            passed: false,
            haltedAt: gate.id,
            message: `Halted at ${gate.name}. Action does not proceed.`,
          });
          setIsRunning(false);
          return;
        }

        await new Promise((r) => setTimeout(r, 600));
      } catch (err) {
        setError(err.message);
        setGateStatuses((prev) =>
          prev.map((s, idx) =>
            idx === i
              ? { status: "fail", result: "Connection error." }
              : idx > i
              ? { status: "skipped", result: null }
              : s
          )
        );
        setIsRunning(false);
        return;
      }
    }

    setFinalVerdict({
      passed: true,
      message: "All four gates passed. Action may proceed under authority.",
    });
    setIsRunning(false);
  };

  const reset = () => {
    setGateStatuses(GATES.map(() => ({ status: "waiting", result: null })));
    setFinalVerdict(null);
    setError(null);
    setInput("");
    setIsRunning(false);
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0D0D0D",
        color: "#e0e0e0",
        fontFamily: "'Source Serif 4', Georgia, serif",
      }}
    >
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        textarea:focus { outline: none; border-color: #555 !important; }
      `}</style>

      <div style={{ maxWidth: "640px", margin: "0 auto", padding: "48px 24px" }}>
        {/* Header */}
        <div style={{ marginBottom: "48px", textAlign: "center" }}>
          <div
            style={{
              fontFamily: "'DM Mono', monospace",
              fontSize: "10px",
              letterSpacing: "0.3em",
              color: "#555",
              marginBottom: "16px",
              textTransform: "uppercase",
            }}
          >
            Decision Validation Protocol
          </div>
          <h1
            style={{
              fontSize: "28px",
              fontWeight: 300,
              letterSpacing: "0.04em",
              margin: 0,
              color: "#e8e0d4",
            }}
          >
            The Four Gates
          </h1>
          <div
            style={{
              fontFamily: "'DM Mono', monospace",
              fontSize: "11px",
              color: "#666",
              marginTop: "12px",
              letterSpacing: "0.08em",
            }}
          >
            RED → FLOOR → BROTHERS → GOD
          </div>
        </div>

        {/* Input */}
        <div style={{ marginBottom: "32px" }}>
          <label
            style={{
              display: "block",
              fontFamily: "'DM Mono', monospace",
              fontSize: "10px",
              letterSpacing: "0.2em",
              color: "#666",
              marginBottom: "10px",
              textTransform: "uppercase",
            }}
          >
            Proposed Action
          </label>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Describe the decision, proposal, or action to validate..."
            disabled={isRunning}
            rows={3}
            style={{
              width: "100%",
              boxSizing: "border-box",
              padding: "14px 16px",
              background: "rgba(255,255,255,0.03)",
              border: "1px solid #333",
              borderRadius: "4px",
              color: "#ddd",
              fontSize: "14px",
              fontFamily: "'Source Serif 4', Georgia, serif",
              lineHeight: 1.6,
              resize: "vertical",
              transition: "border-color 0.3s",
            }}
          />
          <div style={{ display: "flex", gap: "10px", marginTop: "12px" }}>
            <button
              onClick={runGates}
              disabled={isRunning || !input.trim()}
              style={{
                flex: 1,
                padding: "12px 24px",
                background:
                  isRunning || !input.trim()
                    ? "rgba(255,255,255,0.03)"
                    : "rgba(255,255,255,0.08)",
                border: `1px solid ${
                  isRunning || !input.trim() ? "#222" : "#444"
                }`,
                borderRadius: "4px",
                color: isRunning || !input.trim() ? "#555" : "#ddd",
                fontFamily: "'DM Mono', monospace",
                fontSize: "12px",
                letterSpacing: "0.15em",
                cursor: isRunning || !input.trim() ? "default" : "pointer",
                transition: "all 0.3s",
                textTransform: "uppercase",
              }}
            >
              {isRunning ? "Validating..." : "Begin Validation"}
            </button>
            {finalVerdict && (
              <button
                onClick={reset}
                style={{
                  padding: "12px 20px",
                  background: "transparent",
                  border: "1px solid #333",
                  borderRadius: "4px",
                  color: "#777",
                  fontFamily: "'DM Mono', monospace",
                  fontSize: "12px",
                  letterSpacing: "0.1em",
                  cursor: "pointer",
                }}
              >
                Reset
              </button>
            )}
          </div>
        </div>

        {/* Gates */}
        <div
          style={{
            borderRadius: "6px",
            overflow: "hidden",
            border: "1px solid #222",
          }}
        >
          {GATES.map((gate, i) => (
            <GateIndicator
              key={gate.id}
              gate={gate}
              status={gateStatuses[i].status}
              result={gateStatuses[i].result}
            />
          ))}
        </div>

        {/* Verdict */}
        {finalVerdict && (
          <div
            style={{
              marginTop: "24px",
              padding: "20px 24px",
              background: finalVerdict.passed
                ? "rgba(76,175,80,0.06)"
                : "rgba(198,40,40,0.06)",
              border: `1px solid ${
                finalVerdict.passed
                  ? "rgba(76,175,80,0.2)"
                  : "rgba(198,40,40,0.2)"
              }`,
              borderRadius: "6px",
              animation: "fadeIn 0.5s ease",
            }}
          >
            <div
              style={{
                fontFamily: "'DM Mono', monospace",
                fontSize: "10px",
                letterSpacing: "0.2em",
                color: finalVerdict.passed ? "#4CAF50" : "#C62828",
                marginBottom: "8px",
                textTransform: "uppercase",
              }}
            >
              {finalVerdict.passed ? "Validated" : "Halted"}
            </div>
            <div
              style={{
                fontSize: "14px",
                color: "#bbb",
                lineHeight: 1.6,
              }}
            >
              {finalVerdict.message}
            </div>
          </div>
        )}

        {error && (
          <div
            style={{
              marginTop: "16px",
              padding: "12px 16px",
              background: "rgba(198,40,40,0.08)",
              border: "1px solid rgba(198,40,40,0.2)",
              borderRadius: "4px",
              fontFamily: "'DM Mono', monospace",
              fontSize: "12px",
              color: "#C62828",
            }}
          >
            {error}
          </div>
        )}

        {/* Footer */}
        <div
          style={{
            marginTop: "48px",
            textAlign: "center",
            fontFamily: "'DM Mono', monospace",
            fontSize: "10px",
            color: "#333",
            letterSpacing: "0.15em",
          }}
        >
          FOUR GATES PROTOCOL · CONCORDANCE ENGINE
        </div>
      </div>
    </div>
  );
}
