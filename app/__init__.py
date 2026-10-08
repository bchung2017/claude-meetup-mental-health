from flask import Flask, render_template

from .config import Config


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    from .api.routes import bp

    app.register_blueprint(bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    return app
