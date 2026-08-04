# Vercel Deployment Guide

This guide explains how to deploy the AI-Observatory frontend to Vercel.

## Prerequisites

1. **Vercel Account**: Create one at https://vercel.com
2. **GitHub Repository**: Repo must be on GitHub (public or private)
3. **Node.js 20+** (for local testing)

---

## Step 1: Connect GitHub Repository to Vercel

### Option A: Via Vercel Dashboard (Recommended for first-time setup)

1. Go to https://vercel.com/dashboard
2. Click **"Add New..." → "Project"**
3. Click **"Import Git Repository"**
4. Authorize Vercel to access your GitHub account
5. Select the **AI-Observatory** repository
6. Click **"Import"**

### Option B: Via Vercel CLI

```bash
npm i -g vercel
cd c:\Users\strossi\Downloads\AI-Observatory
vercel --prod
```

Follow the prompts to link your Vercel account and GitHub repo.

---

## Step 2: Configure Build Settings

Vercel should auto-detect the SvelteKit setup, but verify these settings in **Project Settings → Build & Development Settings**:

| Setting | Value |
|---------|-------|
| **Framework Preset** | SvelteKit |
| **Build Command** | `cd frontend && npm ci && npm run build` |
| **Output Directory** | `web` |
| **Install Command** | `npm install` |
| **Node.js Version** | 20.x |

---

## Step 3: Environment Variables (Optional)

If your frontend needs to connect to a backend API:

### In Vercel Dashboard:
1. Go to **Project Settings → Environment Variables**
2. Add variables for each environment (Preview, Production, Development):

```
VITE_API_URL=https://your-backend-url.com
VITE_APP_NAME=AI News Aggregator
```

### Update `frontend/src/config.ts` (or similar):
```typescript
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';
```

### In `frontend/vite.config.ts`, expose env vars:
```typescript
import { defineConfig } from 'vite';
import svelte from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  define: {
    __VITE_API_URL__: JSON.stringify(process.env.VITE_API_URL || 'http://localhost:5000'),
  },
});
```

---

## Step 4: Deploy

### Automatic Deployment (Recommended)

Once linked to GitHub, Vercel automatically deploys when you push to `main`:

```bash
git add .
git commit -m "Deploy frontend to Vercel"
git push origin main
```

Vercel will:
1. Trigger a build
2. Run `cd frontend && npm ci && npm run build`
3. Deploy to `https://ai-observatory.vercel.app` (or your custom domain)

### Manual Deployment

```bash
vercel --prod
```

---

## Step 5: Verify Deployment

### Check Build Logs
1. Go to https://vercel.com/dashboard/projects/ai-observatory
2. Click the latest deployment
3. Click **"Deployments" tab**
4. Review build logs for errors

### Test the Site
- **Preview URL**: https://ai-observatory-staging.vercel.app (or equivalent)
- **Production URL**: https://your-domain.vercel.app

### Check Frontend loads
```bash
curl https://ai-observatory.vercel.app
```

---

## Step 6: Custom Domain (Optional)

1. Go to **Project Settings → Domains**
2. Click **"Add"**
3. Enter your domain (e.g., `news.example.com`)
4. Follow DNS configuration instructions for your domain registrar
5. Vercel auto-provisions SSL/TLS certificate

---

## Step 7: Cache & Performance

The `vercel.json` already configures:
- ✅ **Static assets** (JS/CSS): 1-year cache (immutable hash)
- ✅ **Data JSON files** (`/data/*.json`): 1-hour cache (refreshes frequently)
- ✅ **llms.txt & ai-index.json**: 30-minute cache
- ✅ **CORS headers** on `/data/` for cross-origin requests

No additional config needed.

---

## Step 8: Troubleshooting

### Build fails with "npm: not found"
→ Ensure `buildCommand` includes `npm ci` to install dependencies first.

### "Cannot find module" errors
→ Check that all dependencies are in `frontend/package.json`, not root `package.json`.

### Frontend loads but shows blank page
→ Check browser console for errors. Likely issues:
- `VITE_API_URL` not set correctly
- `/data/` files not present (run pipeline locally first)
- CSP headers too restrictive

### Deployment stuck at 50%
→ Check build logs in Vercel dashboard for timeout. May need to increase `maxDuration` if backend integration takes time.

### Frontend shows old data after deploy
→ Vercel cache may need clearing:
  1. Go to **Project Settings → Git**
  2. Under "Deployments", click **"Redeploy"** on the latest commit
  3. Or use Vercel CLI: `vercel --prod --force`

---

## Step 9: CI/CD Integration

To auto-deploy on every `main` branch push, Vercel is already integrated. No additional config needed.

Optional: Add deployment status checks in GitHub:
1. Go to **Settings → Branches → Main**
2. Require **"Vercel" check** before merge
3. PRs must pass Vercel preview deployment before merging

---

## Rollback & Revert

If deployment breaks production:

### Via Vercel Dashboard
1. Go to **Deployments**
2. Click any previous deployment
3. Click **"Promote to Production"**

### Via CLI
```bash
vercel --prod --target production <deployment-url>
```

---

## Next Steps

1. **Connect GitHub** via Vercel dashboard
2. **Verify build settings** (Framework: SvelteKit, Build: `cd frontend && npm ci && npm run build`, Output: `web`)
3. **Push to main** and watch deployment complete
4. **Test frontend** at your Vercel URL
5. _(Optional)_ **Add custom domain** and **set environment variables**

---

## Useful Links

- Vercel Docs: https://vercel.com/docs
- SvelteKit + Vercel: https://vercel.com/guides/build-a-blog-with-svelte-kit-and-vercel-postgres
- Environment Variables: https://vercel.com/docs/concepts/projects/environment-variables
- Deployment Monitoring: https://vercel.com/docs/concepts/deployments/build-view

