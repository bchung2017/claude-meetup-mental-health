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
        return render_template("dashboard.html")

    @app.get("/tracker")
    def tracker():
        return render_template("tracker.html")

    # "1": seed only an empty entries table. "replace": wipe entries and reseed on every boot.
    seed_mode = os.environ.get("SEED_SAMPLE_DATA")
    if seed_mode in ("1", "replace"):
        from .importer import seed_patients_if_empty
        from .sample_data import reseed, seed_if_empty
        from .stores import get_store

        (reseed if seed_mode == "replace" else seed_if_empty)(get_store())
        seed_patients_if_empty(get_store())

    return app
