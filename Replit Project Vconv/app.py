from flask import Flask
from views.video_routes import video_routes

app = Flask(__name__)
app.register_blueprint(video_routes, url_prefix='')

if __name__ == '__main__':
  app.run(host='0.0.0.0', debug=True)