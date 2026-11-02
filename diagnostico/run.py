"""Execução isolada para testes: python diagnostico/run.py  (porta 5055)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flask import Flask, redirect
from bp import bp

app = Flask(__name__)
app.register_blueprint(bp)
app.add_url_rule("/", "raiz", lambda: redirect("/diagnostico/"))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5055)))
