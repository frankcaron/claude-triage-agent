# Runbook: loan disbursements rejected or returned

Applies to: funding-svc. Owner: Funding Operations on-call.
Approval: anything that moves money or changes a disbursement needs two people,
the on-call engineer and a Funding Operations approver.

## Symptoms
- Disbursement rejection or return rate jumps; funded loans aren't paid out.
- Processor responses carry ACH return codes such as R02, R03 or R04.

## Diagnose (read-only)
1. List rejected disbursements and count them by return code:

    curl -s "https://funding-api.internal.example.com/v1/disbursements?status=rejected&since=<iso-time>" -H "Authorization: Bearer $FUNDING_READONLY_TOKEN"
    psql "$LOANS_REPLICA_DSN" -c "select return_code, count(*) from disbursements where status = 'rejected' and updated_at > now() - interval '2 hours' group by 1;"

2. Check for a recent release:

    kubectl rollout history deployment/funding-svc -n lending
    kubectl logs deployment/funding-svc -n lending --since=2h | grep -E 'return_code=R0[234]'

3. Check the processor's status page before blaming your own code.

## Act (human only, two approvers)
1. Pause outbound ACH so no more disbursements fail:

    curl -X POST https://funding-api.internal.example.com/v1/queues/ach-outbound/pause -H "Authorization: Bearer $FUNDING_OPS_TOKEN"

2. If a release caused it, roll the release back:

    kubectl rollout undo deployment/funding-svc -n lending

3. Resubmit each rejected disbursement only after its bank details are confirmed,
   one at a time, with a second approver:

    curl -X POST https://funding-api.internal.example.com/v1/disbursements/<disbursement-id>/resubmit -H "Authorization: Bearer $FUNDING_OPS_TOKEN" -H "X-Second-Approver: <approver-id>"

Never bulk-resubmit, and never resubmit a disbursement whose status you haven't
confirmed: a duplicate pays a borrower twice, and repeat returns count against
your ACH return rates.

## Verify
- Rejection rate back to baseline; Funding Operations has resumed the ACH queue.
- Every affected loan is either funded exactly once or on hold with a reason.

## Escalate
- Funding Operations lead for any loan past its promised funding date.
- Compliance if borrower disclosures promised a funding date you'll miss.
