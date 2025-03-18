from flask import Flask
from routes import bp as api_blueprint
from models import Base
from database import engine

# Create all tables if they don't already exist
Base.metadata.create_all(bind=engine)

# Initialize Flask, specifying the templates folder
app = Flask(__name__, template_folder='templates')

# Register the blueprint from routes.py
app.register_blueprint(api_blueprint)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
