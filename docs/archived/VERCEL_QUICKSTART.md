# Deploy Frontend to Vercel - Quick Start

## 1️⃣ Prerequisites
- Vercel account: https://vercel.com/signup
- GitHub account with this repo
- Node.js 20+ installed locally

---

## 2️⃣ First-Time Setup (GitHub + Vercel)

### Step A: Sign up on Vercel
```bash
# Visit and sign up (free tier works great)
https://vercel.com/signup
```

### Step B: Import Project from GitHub
1. Login to https://vercel.com/dashboard
2. Click **"Add New Project"** or **"New Project"**
3. Click **"Import Git Repository"**
4. Authorize Vercel to access GitHub
5. Select **"AI-Observatory"** repo
6. Click **"Import"**

✅ Vercel auto-detects SvelteKit!

---

## 3️⃣ Build Settings (Verify in Vercel Dashboard)

After import, check **Project Settings → Build & Development**:

| Field | Value |
|-------|-------|
| Framework | SvelteKit |
| Build Command | `cd frontend && npm ci && npm run build` |
| Output Directory | `web` |
| Install Command | `npm install` |
| Node Version | 20.x or 18.x |

If settings look wrong, Vercel should auto-correct. If not:
1. Edit the values above
2. Click **"Save"**

---

## 4️⃣ Environment Variables (If Needed)

If frontend needs to connect to backend API:

1. In Vercel dashboard: **Project Settings → Environment Variables**
2. Click **"Add New Environment Variable"**
3. Add:
   - **Name**: `VITE_API_URL`
   - **Value**: `https://your-api-backend.com`
   - **Environments**: Select all (Production, Preview, Development)
4. Click **"Save"**

Otherwise, skip this step (frontend defaults to local `/data/`).

---

## 5️⃣ Deploy!

### Option A: Automatic (Recommended)
Just push to `main` branch:
```bash
git add .
git commit -m "Deploy frontend to Vercel"
git push origin main
```

Vercel watches and auto-deploys within 1-2 minutes.

### Option B: Manual Deploy
```bash
npm install -g vercel
cd c:\Users\strossi\Downloads\AI-Observatory
vercel --prod
```

---

## 6️⃣ Check Deployment

### See Build Logs
1. Go to Vercel dashboard
2. Click your project
3. **"Deployments"** tab shows latest build
4. Click on any deployment to see logs

### Test the URL
```bash
# Visit your deployment
https://ai-observatory.vercel.app
```

Replace `ai-observatory` with your Vercel project name.

---

## 7️⃣ Troubleshooting

**"Build failed"**
→ Check Vercel logs: **Deployments → [Latest] → Build tab**

**"Blank page after deploy"**
→ Open browser DevTools (F12) → Console tab, check for errors

**"Cannot find /data/*** → JSON 404**
→ Pipeline needs to run first. Run locally:
```bash
python run_pipeline.py
```
This populates `web/data/*.json`

**"CORS errors on API calls"**
→ Add `VITE_API_URL` environment variable pointing to backend

---

## 8️⃣ Custom Domain (Optional)

1. **Project Settings → Domains**
2. Click **"Add"**
3. Enter domain (e.g., `news.mycompany.com`)
4. Follow DNS setup instructions
5. SSL auto-provisioned ✅

---

## ✅ Done!

Your frontend is live on Vercel. Every `git push origin main` triggers a new deployment automatically.

### Useful Commands:
```bash
# View deployment status
vercel --prod

# Redeploy current version
vercel --prod --force

# View logs
vercel logs --prod

# Link to existing Vercel project (if needed)
vercel link
```

### Next:
- [ ] Test frontend loads
- [ ] Check `/data/` directory for JSON files
- [ ] Set up custom domain (optional)
- [ ] Add backend API URL if using external API
- [ ] Enable branch protection in GitHub to require successful Vercel deploy before merge

