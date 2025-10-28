# Chesser

**Chesser** is a Python-based chess game built with **Pygame** and **python-chess**, offering smooth graphics, intuitive controls, and easy extensibility.  
It can be played locally (human vs. human) or expanded with an AI opponent, opening books, and advanced chess features.

A demo of the project can be tested at: https://chesser-bot.vercel.app/
We recommend only a layer of 3 for reasonable run speed.

## Web Deployment (Vercel)

This application has been configured to deploy to Vercel as a web application.

### Deployment Instructions

1. **Install Vercel CLI** (if not already installed):
   ```bash
   npm install -g vercel
   ```

2. **Deploy to Vercel**:
   ```bash
   vercel
   ```

3. **For production deployment**:
   ```bash
   vercel --prod
   ```

### Local Development

To run the server locally:
```bash
python server.py
```

Then navigate to `http://localhost:5000` in your browser.

### Project Structure

- `server.py` - Flask web server
- `chess_bot.py` - AI chess engine
- `api/index.py` - Vercel entry point
- `vercel.json` - Vercel configuration
- `templates/index.html` - Web UI
- `static/` - Static assets (CSS, JS, images)
