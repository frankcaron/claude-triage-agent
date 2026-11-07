# Runbook: credit bureau pulls timing out

Applies to: bureau-gateway. Owner: Decisioning on-call.

## Symptoms
- Credit report pulls time out or error; applications pile up in PENDING_CREDIT.

## Diagnose (read-only)

    kubectl logs deployment/bureau-gateway -n lending --since=30m | grep -c 'status=timeout'
    curl -s -o /dev/null -w '%{http_code} %{time_total}\n' https://bureau-a.partner.example.com/health
    psql "$LOANS_REPLICA_DSN" -c "select count(*) from applications where state = 'PENDING_CREDIT';"

Check the bureau's status page and the gateway's outbound connection pool first.

## Act (human only)
- If the queue passes its SLA, pause new application intake:

    curl -X POST https://decisioning-api.internal.example.com/v1/intake/pause -H "Authorization: Bearer $DECISIONING_OPS_TOKEN"

- Switch to the secondary bureau only with Credit Risk's approval: it changes
  the data that credit decisions run on.

Never re-pull credit automatically: a duplicate hard inquiry can show on the
applicant's credit report.

## Verify
- Timeout rate under 1% for 15 minutes; PENDING_CREDIT is draining.

## Escalate
- The bureau's account team after 30 minutes; Credit Risk before any bureau switch.
