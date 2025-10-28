# Static Files Fix for Vercel

## Issue
Chess board and pieces don't appear on the deployed website.

## Root Cause
Static files (images, CSS, JS) are not being served correctly on Vercel.

## Changes Made

### 1. Updated `server.py`
- Added explicit static folder configuration
- Added explicit route for serving static files
- Added proper path handling

### 2. Updated `api/index.py`
- Changed working directory to parent directory
- Ensures relative paths work correctly in serverless environment

### 3. Updated `vercel.json`
- Simplified routing to let Flask handle all requests including static files

### 4. Updated `.vercelignore`
- Made sure only root-level `images/` is excluded, not `static/images/`

## What You Need to Do

1. **Redeploy to Vercel**:
   ```bash
   vercel --prod
   ```

2. **Check the deployment**:
   - Visit your deployed URL
   - Open browser DevTools (F12)
   - Check the Console tab for errors
   - Check the Network tab to see if static files are loading (status 200) or failing (status 404)

3. **Verify static files are deployed**:
   - Check in Vercel dashboard > Deployments > Your latest deployment > Files
   - Look for `static/` directory with subdirectories `css/`, `js/`, `images/`

## Troubleshooting

### If pieces still don't appear:

1. **Check piece file naming**: 
   - Chessboard.js expects piece format: `wP.png`, `bK.png`, etc.
   - Your files are named: `wp.png`, `bk.png`, etc. (lowercase)
   
   **Fix needed**: Either rename files or update the `pieceTheme` path in `app.js`

2. **Check browser console**:
   - Look for 404 errors on image files
   - Look for CORS errors
   - Look for JavaScript errors

3. **Check that files are actually deployed**:
   - In Vercel dashboard, check if static files are present
   - If missing, verify `.vercelignore` doesn't exclude them

## Next Steps

After redeploying, if you still see issues, please share:
- Screenshot of browser console errors
- Which specific files are failing to load (from Network tab)
- Any CORS errors
