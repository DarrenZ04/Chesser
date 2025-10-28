# Deployment Guide for Chesser on Vercel

## Prerequisites

1. **Node.js** installed (for Vercel CLI)
2. **Vercel account** (sign up at [vercel.com](https://vercel.com))
3. Git repository (if deploying from Git)

## Quick Deploy

### Option 1: Using Vercel CLI

1. Install Vercel CLI:
   ```bash
   npm install -g vercel
   ```

2. Navigate to your project directory:
   ```bash
   cd chessBot
   ```

3. Deploy:
   ```bash
   vercel
   ```

4. Follow the prompts to:
   - Link your project to Vercel
   - Select your organization
   - Configure project settings

5. For production deployment:
   ```bash
   vercel --prod
   ```

### Option 2: Using GitHub

1. Push your code to GitHub (if not already)

2. Go to [vercel.com](https://vercel.com) and click "Add New Project"

3. Import your GitHub repository

4. Vercel will automatically detect the Python runtime and deploy

5. Click "Deploy"

## Project Structure for Vercel

```
chessBot/
├── api/
│   └── index.py          # Vercel entry point
├── static/               # Static files
│   ├── css/
│   ├── js/
│   └── images/
├── templates/            # HTML templates
├── chess_bot.py          # AI engine
├── server.py             # Flask app
├── vercel.json           # Vercel configuration
├── requirements.txt      # Python dependencies
└── README.md

```

## Important Notes

1. **Opening Book**: The opening book (`openings/book.bin`) has been made optional. If it doesn't exist, the AI will play without it.

2. **Pygame**: Pygame has been made optional for web deployment since it's not needed for the web UI.

3. **Static Files**: All static files in the `static/` directory are automatically served by Vercel.

## Environment Variables

No environment variables are required for basic deployment.

## Troubleshooting

### Import Errors

If you encounter import errors, ensure all Python files are in the correct locations and that `requirements.txt` includes all dependencies.

### Static Files Not Loading

Verify that:
- Static files are in the `static/` directory
- The paths in your HTML reference `/static/...` correctly
- The Vercel routes in `vercel.json` are configured properly

### Build Failures

Check the build logs in Vercel dashboard for:
- Missing Python packages (add to `requirements.txt`)
- Syntax errors in Python files
- Missing dependencies

## Testing Locally

Before deploying, test your application locally:

```bash
python server.py
```

Then visit `http://localhost:5000` in your browser.

## Continuous Deployment

After linking to Git, Vercel will automatically deploy:
- Every push to the main branch (production)
- All pull requests (preview deployments)

## Monitoring

- View deployment logs in the Vercel dashboard
- Check function logs for serverless function execution
- Monitor performance and usage in the Analytics tab

## Custom Domain

To add a custom domain:
1. Go to your project settings in Vercel
2. Navigate to "Domains"
3. Add your custom domain
4. Update DNS records as instructed
