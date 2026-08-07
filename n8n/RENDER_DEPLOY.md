# n8n on Render.com — Deployment Guide

## What This Does
This deploys a **self-hosted n8n** instance on Render.com for free.
LeadGen sends high-score lead webhooks to your n8n URL automatically.

## Step-by-Step Setup

### 1. Create Render.com Web Service

1. Go to **https://render.com** → Sign in with GitHub
2. Click **New +** → **Web Service**
3. Select **Deploy an existing image from a registry**
4. Image URL: `docker.n8n.io/n8nio/n8n`
5. Service name: `n8n-leadgen`
6. Region: Choose closest (Singapore for India)
7. Instance Type: **Free**
8. Port: `5678`

### 2. Set Environment Variables in Render Dashboard

Add these in the **Environment** tab:

| Key | Value |
|:---|:---|
| `N8N_HOST` | `your-n8n-service.onrender.com` |
| `N8N_PORT` | `5678` |
| `N8N_PROTOCOL` | `https` |
| `N8N_BASIC_AUTH_ACTIVE` | `true` |
| `N8N_BASIC_AUTH_USER` | `admin` |
| `N8N_BASIC_AUTH_PASSWORD` | `YourStrongPassword123` |
| `WEBHOOK_URL` | `https://your-n8n-service.onrender.com/` |
| `GENERIC_TIMEZONE` | `Asia/Kolkata` |
| `NODE_ENV` | `production` |

### 3. Deploy & Get Your Webhook URL

After deploy, your n8n will be at:
```
https://your-n8n-service.onrender.com
```

In n8n dashboard:
1. Create **New Workflow**
2. Add **Webhook** node → HTTP Method: `POST`
3. Copy the webhook URL (e.g. `https://your-n8n-service.onrender.com/webhook/lead-alert`)

### 4. Add to LeadGen `.env`

```env
WEBHOOK_URL=https://your-n8n-service.onrender.com/webhook/lead-alert
```

---

## UptimeRobot Setup (Prevent Render Sleep)

Render free tier sleeps after **15 minutes of inactivity**.
UptimeRobot pings it every 5 minutes to keep it awake — 100% free.

### Steps:
1. Go to **https://uptimerobot.com** → Create free account
2. Click **Add New Monitor**
3. Monitor Type: **HTTP(s)**
4. Friendly Name: `n8n-leadgen`
5. URL: `https://your-n8n-service.onrender.com/`
6. Monitoring Interval: **5 minutes**
7. Click **Create Monitor**

That's it! n8n will now stay alive 24/7. 🟢

---

## n8n Workflow for LeadGen Webhooks

Once n8n is running, set up this workflow:

```
[Webhook] → [IF: score > 85] → [Slack/Discord Notify]
                             → [Google Sheets: Log Lead]
                             → [Gmail: Auto-Reply]
```

### Payload you receive in n8n:
```json
{
  "event": "high_score_lead_found",
  "timestamp": "2026-08-07T11:00:00Z",
  "lead": {
    "title": "Need Python dev for AI automation project",
    "url": "https://upwork.com/jobs/...",
    "score": 92,
    "category": "AI Automation",
    "email_found": "client@company.com",
    "tech_stack": ["Python", "AI/LLM"]
  },
  "sender": {
    "name": "Shweta Mishra",
    "gmail": "shweta@gmail.com"
  }
}
```

Access in n8n nodes:
- `{{ $json.lead.title }}` → Lead title
- `{{ $json.lead.score }}` → Lead score
- `{{ $json.lead.email_found }}` → Client email
- `{{ $json.lead.tech_stack }}` → Tech stack array
- `{{ $json.timestamp }}` → When lead was found
