# Continuing development with an AI coding assistant

Run the tests first and inspect a report before choosing a task.

1. Add measurement-column mappings without weakening strict numeric/time checks.
   Acceptance: an oscilloscope-style CSV can be mapped explicitly; original file
   hashes remain recorded; unknown units require an explicit conversion.
2. Add redundant pack sensing and common-cause sensor-fault cases.
   Acceptance: observable faults inhibit activation; unobservable common bias is
   reported as a model limit, not asserted detected.
3. Add sampled auxiliary debounce and contact-bounce injection.
   Acceptance: transient chatter does not enable torque; persistent loss times out.
4. Parse both single-run and tabulated stepped LTspice measurement logs.
   Acceptance: failed measures remain failures; no omitted row becomes a pass.
5. Add parameter-fit support for measured RC traces.
   Acceptance: recover known synthetic R/C ranges with confidence bounds, and
   reject unidentifiable datasets instead of returning arbitrary estimates.

Suggested first terminal-assistant task:

    Extend the CSV importer with an explicit JSON column map. Preserve all
    existing validation and exit-code behavior. Start by explaining the
    failure cases, then implement the smallest correct change and run the
    regression suite. Show the diff and a mapped-file example.

When comparing AI responses, prioritize a defensible model, source traceability,
fault handling, numerical behavior, and meaningful verification. Keep your
actual decisions and commits as you develop; this bundle does not fabricate
past commit history or human review.
