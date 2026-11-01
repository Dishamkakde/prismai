"""PRISM AI — Application entry point.
Run locally:  python run.py
Production:   gunicorn "run:app"
Seed DB:      python seed.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db

# Expose 'app' at module level for gunicorn
app = create_app()

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    print("\n  ╔══════════════════════════════════════╗")
    print("  ║        PRISM AI is running           ║")
    print("  ║  http://127.0.0.1:5000               ║")
    print("  ╚══════════════════════════════════════╝\n")
    app.run(host='127.0.0.1', port=5000, debug=True)
