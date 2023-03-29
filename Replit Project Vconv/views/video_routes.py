import os
import boto3
import uuid

from flask import Blueprint, request, render_template, redirect, url_for
from werkzeug.utils import secure_filename
from moviepy.editor import *


video_routes = Blueprint('video_routes', __name__, url_prefix='')

s3 = boto3.client('s3', region_name='us-east-1')
sqs = boto3.client('sqs', region_name='us-east-1')

client = boto3.client('cloudwatch')

response = client.put_metric_alarm(
    AlarmName='ProcessingTimeAlarm',
    ComparisonOperator='GreaterThanThreshold',
    EvaluationPeriods=1,
    MetricName='ProcessingTime',
    Namespace='Custom',
    Period=60,
    Statistic='Average',
    Threshold=5.0,
    ActionsEnabled=True,
    AlarmActions=[
        'arn:aws:autoscaling:us-east-1:978020407782:autoScalingGroup:a1aecf58-3fd7-4343-87de-9886ec4ba051:autoScalingGroupName/Autoscaling-videoconv'
    ]
)

def upload_video_to_s3(file, desired_format):
  # corrigindo qualquer problema que haja no nome do arquivo original que será enviado ao S3
  file_name = secure_filename(file.filename)
  # gerando um nome exclusivo para o arquivo no bucket com UUID, adicionando a extensão do arquivo original 
  object_key = str(uuid.uuid4()) + os.path.splitext(file_name)[1]
  # diretório local onde o arquivo será salvo temporariamente
  local_directory = 'tmp'
  # salvando o arquivo de vídeo no diretório local
  file.save(os.path.join(local_directory, file_name))
  # nome do bucket onde o arquivo será armazenado e da fila na qual será enviada a mensagem
  bucket_name = 'source-bucket-videoconv'
  queue_url = 'https://sqs.us-east-1.amazonaws.com/978020407782/my-queue-videoconv.fifo'
  # caminho completo do objeto no bucket
  s3_object_key = f'{object_key}'
  # envia o arquivo de vídeo para o s3 chamado 'source-bucket-videoconv'
  s3.upload_file(os.path.join(local_directory, file_name), bucket_name, s3_object_key)
  # cria a mensagem que será enviada para a fila
  message = {
    'bucket_name': 'source-bucket-videoconv',
    'object_key': s3_object_key,
    'output_format': desired_format
}
  # envia a mensagem para a fila
  response = sqs.send_message(QueueUrl=queue_url, MessageBody=str(message))
  # remove o arquivo local
  os.remove(os.path.join(local_directory, file_name))
  return s3_object_key

def convert_video(s3_object_key, desired_format):
  # Extrai o nome do arquivo original do objeto no S3
  original_filename = os.path.splitext(os.path.basename(s3_object_key))[0]
  # Cria o nome do arquivo de saída usando o nome original e o formato desejado, ex: video01.avi
  output_filename = f"{original_filename}.{desired_format}"
  # Cria o caminho completo do arquivo de saída, ex: tmp/video01.avi
  output_path = os.path.join('tmp', output_filename)
  # Baixa o arquivo de vídeo do S3 para o diretório local
  local_path = os.path.join('tmp', original_filename + os.path.splitext(s3_object_key)[1])
  s3.download_file('source-bucket-videoconv', s3_object_key, local_path)
  # Carrega o arquivo de vídeo do diretório local usando o MoviePy
  video = VideoFileClip(local_path)
  # Converte o arquivo de vídeo para o formato desejado e salva na pasta 'tmp', ex: 
  video.write_videofile(output_path, codec='libx264')
  video.close()
  # Envia o arquivo de saída para o S3
  bucket_name = 'destination-bucket-videoconv'
  s3_final_object_key = f"{output_filename}"
  s3.upload_file(output_path, bucket_name, s3_final_object_key)
  # Remove o arquivo local de entrada e saída
  os.remove(local_path)
  os.remove(output_path)
  # Retorna o caminho do objeto S3 do arquivo de saída
  return s3_final_object_key

# definindo a rota raiz
@video_routes.route('/')
def index():
  return render_template('index.html')

@video_routes.route('/convert', methods=['POST'])
def convert():
  # recebendo o arquivo de vídeo do formulário, atenção ao 'name'
  file = request.files['video']
  # recebendo o formato escolhido
  desired_format = request.form['desired_format']
  # enviar o arquivo para o bucket do S3
  s3_object_key = upload_video_to_s3(file)
  # Converte o vídeo para o formato desejado
  output_key = convert_video(s3_object_key, desired_format)
  # redirecionando o usuário para a página de resultados
  return redirect(url_for('video_routes.results', s3_object_key=output_key))

@video_routes.route('/results/<s3_object_key>')
def results(s3_object_key):
    # Obter o nome do arquivo a partir da URL do objeto S3
    filename = os.path.basename(s3_object_key)
    # Obter um URL de download temporário para o arquivo
    download_link = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': 'destination-bucket-videoconv', 'Key': f'{filename}'},
        ExpiresIn=3600
    )
    # Passar o link de download para o template 'results.html'
    return render_template('results.html', download_link=download_link)