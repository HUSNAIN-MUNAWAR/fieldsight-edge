# Inspection workflow

## Guided Solar Farm Alpha scenario

1. The operations user opens Mission Control and sees a new critical finding count and pending review queue.
2. On the map, they select a Zone C finding and open visual evidence.
3. In Image Review, they inspect metadata, model version, confidence, polygon/box overlay, and evidence chain.
4. They approve, reject, or correct the finding. The decision becomes an audit event.
5. An approved finding can create a work order with severity, assignee, and SLA due date.
6. The asset workspace shows capture timeline, defect history, current risk, and linked maintenance work.
7. A report compiles summary, metrics, priority evidence, recommendations, and a download audit event.

Review decisions exist to capture human corrections as active-learning signals. The current demo represents that decision trail but does not write a retraining dataset yet.
