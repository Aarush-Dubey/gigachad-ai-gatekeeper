# 🚀 Deployment Guide (Vercel + Render)

Follow these steps exactly to deploy your **GIGACHAD AI Gatekeeper**.

## Phase 1: GitHub Setup
1. Create a new **Private Repository** on GitHub (e.g., `gigachad-gatekeeper`).
2. Push your code:
   ```bash
   git init
   git add .
   # IMPORTANT: Ensure .env, credentials.json, and firebase_credentials.json are NOT in .gitignore for the first PRIVATE push if you want the easiest path, 
   # BUT strict security practice says: Add them to .gitignore and assume manual upload.
   # For this guide, we will assume you add them via DASHBOARD controls.
   
   echo ".env" >> .gitignore
   echo "credentials.json" >> .gitignore
   echo "server/firebase_credentials.json" >> .gitignore
   
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/gigachad-gatekeeper.git
   git push -u origin main
   ```

---

## Phase 2: Deploy Backend (Render.com)
1. **Create Service**: Go to [dashboard.render.com](https://dashboard.render.com/) -> New + -> **Web Service**.
2. **Connect**: Select your `gigachad-gatekeeper` repo.
3. **Settings**:
   - **Name**: `gigachad-backend` (or similar)
   - **Root Directory**: `server`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. **Environment Variables** (Copy from your `.env`):
   - `GROQ_KEY_1`, `GROQ_KEY_2`, etc.
   - `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`... (All of them)
   - `ADMIN_SECRET`: `bits-gigachad-admin-2024`
5. **Secret Files (Critical)**:
   - Render has a "Secret Files" tab. You need to upload your specific credential files here.
   - **Filename**: `server/firebase_credentials.json` -> **Content**: Paste content of your local `firebase_credentials.json`.
   - **Filename**: `server/credentials.json` (if using sheets) -> **Content**: Paste content of your local `credentials.json`.
6. **Deploy**: Click **Create Web Service**.
7. **Copy URL**: Once live, copy the URL (e.g., `https://gigachad-backend.onrender.com`).

---

## Phase 3: Update Frontend Code
1. Open `client/script.js`.
2. Update the `API_URL` line:
   ```javascript
   const API_URL = (window.location.hostname === 'localhost' ...)
       ? "http://localhost:8000"
       : "https://gigachad-backend.onrender.com"; // <--- PASTE YOUR RENDER URL HERE
   ```
3. Commit and Push this change to GitHub.

---

## Phase 4: Deploy Frontend (Vercel)
1. Go to [vercel.com](https://vercel.com) -> **Add New...** -> **Project**.
2. **Import**: Select your `gigachad-gatekeeper` repo.
3. **Settings**:
   - **Framework Preset**: Other (or plain HTML)
   - **Root Directory**: Click "Edit" and select `client`.
4. **Deploy**: Click **Deploy**.

## Phase 5: Final Configuration
1. **CORS**: Go back to your Backend Code (`server/main.py`) and update `ALLOWED_ORIGINS` to include your new Vercel URL (e.g., `https://gigachad-gatekeeper.vercel.app`). Push to GitHub. Render will auto-redeploy.
2. **Auth Domain**: Go to **Firebase Console** -> Authentication -> Settings -> Authorized Domains. Add your `gigachad-gatekeeper.vercel.app` domain.

**✅ SYSTEM LIVE.**
