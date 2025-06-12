from main import app

if __name__ == "__main__":
    app.run()

# This is needed for Gunicorn
application = app 