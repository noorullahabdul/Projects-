# Development

Python 3.10+; standard library only.

Run the existing suite before and after changing behavior. Preserve explicit
units, strict inputs, finite JSON outputs and distinction between measured
data and simulation. Add regressions for numerical, state-transition or input
validation changes. Do not replace missing evidence with a pass or hard-code
expected fault outcomes into the diagnostic algorithm.

Keep external tool executions separately identified from Python verification.
Record design changes, assumptions and source/model revisions in the docs.
