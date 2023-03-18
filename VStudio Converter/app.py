import boto3
import uuid

from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from moviepy.editor import *

# definindo os formatos de vídeo aceitos
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'flv', 'mov', 'mkv', 'mpeg'}

# verificando se o vídeo está dentro do formato aceito
def allowed_file(filename):
  return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# definindo a função que irá fazer a conversão do formato do vídeo
def convert_video(uploaded_file, format):
  video = VideoFileClip(uploaded_file)
  output_file = uploaded_file.split('.')[0] + '.' + format
  video.write_videofile(output_file)
  return output_file

# instanciando um banco de dados para guardar os registros dos arquivos que foram feitos upload/download
db = SQLAlchemy()

# criando um modelo da tabela na qual vamos armazenar os dados dos arquivos
class File(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  original_filename = db.Column(db.String(200))
  filename = db.Column(db.String(200))

# inicializando a aplicação FLASK
def create_app():
  app = Flask(__name__)
  app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"

  db.init_app(app)

  @app.route("/", methods=['GET', 'POST'])
  def index():
    if request.method == 'POST':
      uploaded_file = request.files["file-to-upload"]
      if not allowed_file(uploaded_file.filename):
        return "Formato de arquivo não compatível!"
      
      # gerando um nome único para o novo arquivo que será upado
      new_filename = uuid.uuid4().hex + '.' + uploaded_file.filename.rsplit('.', 1)[1].lower()

      bucket_name = "source-bucket-videoconv"
      s3 = boto3.resource("s3")
      s3.Bucket(bucket_name).upload_fileobj(uploaded_file, new_filename)

      file = File(original_filename=uploaded_file.filename, filename=new_filename)
      db.session.add(file)
      db.session.commit()

      return redirect(url_for("index"))

    # exibindo os arquivos upados em tela
    files = File.query.all()

    return render_template("index.html", files=files)

  return app