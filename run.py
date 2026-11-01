"""PRISM AI — Application entry point.
Run:  python run.py
Seed: python seed.py   (first time only)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db


def main():
    app = create_app()
    with app.app_context():
        db.create_all()   # safe — only creates missing tables

    print("\n  ╔══════════════════════════════════════╗")
    print("  ║        PRISM AI is running           ║")
    print("  ║  http://127.0.0.1:5000               ║")
    print("  ║  Press Ctrl+C to stop                ║")
    print("  ╚══════════════════════════════════════╝\n")

    app.run(host='127.0.0.1', port=5000, debug=True)


if __name__ == '__main__':
    main()
