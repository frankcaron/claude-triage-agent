# Runbook: loan document or e-sign queue backed up

Applies to: loan-docs-svc. Owner: Lending Platform on-call.

## Symptoms
- Loan agreements aren't generated or e-sign envelopes aren't sent.
- Queue or dead-letter depth keeps growing, often after a template change.

## Diagnose (read-only)

    kubectl get pods -n lending -l app=loan-docs-svc
    kubectl logs deployment/loan-docs-svc -n lending --since=1h | grep -E 'render|esign_send'
    curl -s https://loan-docs-api.internal.example.com/v1/queues/esign/stats -H "Authorization: Bearer $DOCS_READONLY_TOKEN"

## Act (human only)
- Workers stuck but renders succeed: restart them.

    kubectl rollout restart deployment/loan-docs-svc -n lending

- Renders failing after a template change: roll the template back in the template
  repo. Never edit an agreement that has already been generated.
- Re-drive the dead-letter queue only after confirming no envelope already went
  out for those applications, so no borrower gets two agreements:

    curl -X POST https://loan-docs-api.internal.example.com/v1/queues/esign-dlq/redrive -H "Authorization: Bearer $DOCS_OPS_TOKEN"

## Verify
- Queue depth under 50 and the dead-letter queue empty.

## Escalate
- Compliance if any agreement already sent is missing a required disclosure.
