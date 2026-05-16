from flask import Flask
from threading import Thread

# Initialize the Flask web application
app = Flask(__name__)

# Define the root route. This is what the external service will ping.
@app.route('/')
def home():
    return "The Discord bot is running!"

# Function to start the Flask server
def run():
    # host='0.0.0.0' allows external access (required for hosting platforms)
    app.run(host='0.0.0.0', port=8080)

# Function to run the server in a separate thread so it doesn't block the bot
def keep_alive():
    # Start the web server in a daemon thread
    t = Thread(target=run)
    t.daemon = True
    t.start()