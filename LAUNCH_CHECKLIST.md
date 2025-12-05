# WEBSITE ASSISTANT v3 - PRODUCTION LAUNCH CHECKLIST

## Pre-Launch (Do These First)

### 1. Database Setup
- [ ] Create PostgreSQL instance (Neon/Supabase/Cloud SQL)
- [ ] Run `backend/sql/init.sql` to create schema
- [ ] Verify tables: sessions, orders, briefs, cards, system_events
- [ ] Test connection from local machine
- [ ] Note DATABASE_URL for secrets

### 2. Stripe Configuration
- [ ] Create Stripe account (if not exists)
- [ ] Create 3 Products + Prices:
  - Starter: $2,500
  - Professional: $5,000
  - Enterprise: $15,000
- [ ] Copy Price IDs to environment
- [ ] Note STRIPE_SECRET_KEY for secrets
- [ ] Create webhook endpoint (after backend deploy)
- [ ] Subscribe to events: payment_intent.succeeded, payment_intent.payment_failed

### 3. Message Queue Setup
- [ ] Create CloudAMQP instance (free tier OK for start)
- [ ] Note the AMQP URL (RABBITMQ_URL)
- [ ] Test connection

### 4. Cache Setup
- [ ] Create Upstash Redis instance
- [ ] Note the Redis URL (REDIS_URL)
- [ ] Test connection

### 5. AI Keys
- [ ] Verify Anthropic API key has credits (ANTHROPIC_API_KEY)
- [ ] (Optional) OpenAI API key for fallback (OPENAI_API_KEY)

---

## Deployment

### 6. Google Cloud Setup
- [ ] Create GCP project (if not exists): `barrios-a2i`
- [ ] Enable Cloud Run API
- [ ] Enable Container Registry API
- [ ] Enable Secret Manager API
- [ ] Create service account for GitHub Actions
- [ ] Download service account key JSON

### 7. Configure Secrets in Google Cloud
```bash
# Create secrets (run each command and paste your values)
gcloud secrets create DATABASE_URL --replication-policy="automatic"
gcloud secrets versions add DATABASE_URL --data-file=-

gcloud secrets create STRIPE_SECRET_KEY --replication-policy="automatic"
gcloud secrets versions add STRIPE_SECRET_KEY --data-file=-

gcloud secrets create STRIPE_WEBHOOK_SECRET --replication-policy="automatic"
gcloud secrets versions add STRIPE_WEBHOOK_SECRET --data-file=-

gcloud secrets create ANTHROPIC_API_KEY --replication-policy="automatic"
gcloud secrets versions add ANTHROPIC_API_KEY --data-file=-

gcloud secrets create OPENAI_API_KEY --replication-policy="automatic"
gcloud secrets versions add OPENAI_API_KEY --data-file=-

gcloud secrets create RABBITMQ_URL --replication-policy="automatic"
gcloud secrets versions add RABBITMQ_URL --data-file=-

gcloud secrets create REDIS_URL --replication-policy="automatic"
gcloud secrets versions add REDIS_URL --data-file=-
```

### 8. Configure GitHub Secrets
Go to: Settings → Secrets → Actions → Add:
- [ ] `GCP_SA_KEY` - Google Cloud service account JSON (entire file contents)
- [ ] `VERCEL_TOKEN` - From Vercel Settings → Tokens
- [ ] `VERCEL_ORG_ID` - From `.vercel/project.json` or Vercel Dashboard
- [ ] `VERCEL_PROJECT_ID` - From `.vercel/project.json` or Vercel Dashboard

### 9. Deploy Backend
- [ ] Push code to GitHub main branch
- [ ] GitHub Action triggers automatically
- [ ] Wait for Cloud Run deployment (~5 minutes)
- [ ] Verify backend URL is accessible
- [ ] Test health endpoint: `curl https://[BACKEND_URL]/health`

### 10. Deploy Frontend
- [ ] Connect repo to Vercel (if not done)
- [ ] Set environment variables in Vercel:
  - `NEXT_PUBLIC_API_URL` = Backend URL from step 9
  - `NEXT_PUBLIC_STRIPE_KEY` = pk_live_... (publishable key)
- [ ] Deploy triggers automatically after backend
- [ ] Verify site loads at your domain

### 11. Configure Stripe Webhook
- [ ] Go to Stripe Dashboard → Webhooks → Add endpoint
- [ ] Endpoint URL: `https://[BACKEND_URL]/webhook/stripe`
- [ ] Select events:
  - `payment_intent.succeeded`
  - `payment_intent.payment_failed`
  - `checkout.session.completed`
- [ ] Copy webhook signing secret
- [ ] Add to Google Cloud secrets as STRIPE_WEBHOOK_SECRET
- [ ] Redeploy backend to pick up secret

### 12. DNS Configuration
- [ ] Point barriosa2i.com to Vercel
- [ ] Add CNAME record: www → cname.vercel-dns.com
- [ ] Verify SSL certificate (automatic with Vercel)

---

## Post-Launch Verification

### 13. End-to-End Test
- [ ] Open https://barriosa2i.com
- [ ] Start conversation with assistant
- [ ] Generate all 4 card types:
  - [ ] Persona card ("show me buyer personas")
  - [ ] Competitor card ("compare to Synthesia")
  - [ ] Script card ("write a 30 second commercial")
  - [ ] ROI card ("calculate my ROI")
- [ ] Proceed to checkout
- [ ] Use test card: 4242 4242 4242 4242
- [ ] Verify order in database
- [ ] Verify event in system_events table
- [ ] Check admin dashboard shows order

### 14. Start Admin Dashboard
```bash
cd admin
streamlit run dashboard.py
```
Or deploy to Streamlit Cloud:
- [ ] Connect to GitHub repo
- [ ] Set secrets in Streamlit Cloud
- [ ] Verify dashboard loads

### 15. Monitoring Setup
- [ ] Verify revenue dashboard shows data
- [ ] Verify agent health shows all green
- [ ] Test resurrection (create stuck order, wait 5 min)
- [ ] Check event log shows activity

### 16. Go Live
- [ ] Switch Stripe to live mode
- [ ] Update webhook to live endpoint
- [ ] Test with real payment ($1 test)
- [ ] Announce launch!

---

## Emergency Contacts

- **Database (Neon)**: https://neon.tech/docs/support
- **Hosting (Google Cloud)**: https://cloud.google.com/support
- **Payments (Stripe)**: https://support.stripe.com/
- **AI (Anthropic)**: https://support.anthropic.com/
- **Frontend (Vercel)**: https://vercel.com/support

---

## Quick Commands

### Health Checks
```bash
# Backend health
curl https://[BACKEND_URL]/health

# Database check
psql $DATABASE_URL -c "SELECT count(*) FROM system_events"

# Redis check
redis-cli -u $REDIS_URL ping
```

### Logs
```bash
# Cloud Run logs
gcloud run logs read website-assistant-backend --region us-central1

# Stream logs
gcloud run logs tail website-assistant-backend --region us-central1
```

### Rollback
```bash
# List revisions
gcloud run revisions list --service website-assistant-backend --region us-central1

# Rollback to previous
gcloud run services update-traffic website-assistant-backend \
  --to-revisions [PREVIOUS_REVISION]=100 \
  --region us-central1
```

---

## Success Metrics

| Milestone | Revenue | Status |
|-----------|---------|--------|
| First customer | $2,500 | [ ] |
| First 10 customers | $25,000 | [ ] |
| First month | $50,000 | [ ] |
| Automated @ scale | $100,000/mo | [ ] |

---

**The Ferrari is built. Time to drive.**
