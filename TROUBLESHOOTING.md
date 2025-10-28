# Troubleshooting Vercel Deployment

## Issue: 500 Internal Server Error

If you're seeing a 500 error after deployment, here are the fixes that have been applied:

### Problem 1: Missing `zobrist_hash.py`
**Issue**: The file was excluded from deployment but was required by `chess_bot.py`

**Solution**: Removed `zobrist_hash.py` from `.vercelignore`

### Problem 2: Opening Book Path
**Issue**: The opening book file path wasn't resolving correctly in serverless environment

**Solution**: Updated the path to use absolute paths and check for file existence before loading

### Problem 3: Static Files
**Issue**: Static files need to be properly configured

**Solution**: Ensure static files are NOT in `.vercelignore` and are in the `static/` directory

## Files That Must Be Deployed

- ✅ `server.py`
- ✅ `chess_bot.py`
- ✅ `zobrist_hash.py` (was excluded, now fixed)
- ✅ `api/index.py`
- ✅ `templates/index.html`
- ✅ `static/` directory and all contents

## Files That Should Be Excluded

- ❌ `venv/`
- ❌ `__pycache__/`
- ❌ `*.pyc`
- ❌ `images/` (local images, static images are in static/)
- ❌ `chess_gui.py` (GUI version, not used for web)

## Testing Locally

Before deploying, test locally:

```bash
python server.py
```

Visit http://localhost:5000 and verify everything works.

## Common Issues

### Import Errors
If you see import errors:
1. Check that all required Python files are present
2. Verify `requirements.txt` has all dependencies
3. Check that files are not in `.vercelignore`

### Opening Book Warnings
If you see "Warning: Could not load opening book":
- This is expected on Vercel if the opening book file is not deployed
- The app will work without it, just won't use opening moves

### Static Files Not Loading
1. Verify files are in `static/` directory
2. Check that `static/` is not in `.vercelignore`
3. Verify paths in HTML use `/static/...`

### Module Not Found
If you see "ModuleNotFoundError":
1. Check that the file exists in the repository
2. Verify it's not excluded in `.vercelignore`
3. Check import statements use correct paths

## Deployment Checklist

- [ ] All Python files are present (server.py, chess_bot.py, zobrist_hash.py)
- [ ] API entry point exists (api/index.py)
- [ ] Vercel config is correct (vercel.json)
- [ ] Requirements are up to date (requirements.txt)
- [ ] Static files are in correct location (static/)
- [ ] Template is present (templates/index.html)
- [ ] .vercelignore doesn't exclude required files
- [ ] Tested locally before deploying

