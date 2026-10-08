import os

from flask import Flask, render_template

from .config import Config


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    from .api.routes import bp as api_bp
    from .tether.routes import bp as tether_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(tether_bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    if os.environ.get("SEED_SAMPLE_DATA") == "1":
        from .sample_data import seed_if_empty
        from .stores import get_store

        seed_if_empty(get_store())

    return app
