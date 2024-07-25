import csv
import io
import os
import random
from datetime import datetime

import pytz
import requests
from telegram import InputFile, Update
from telegram.ext import *
from telegram.ext import Application
from pydub import AudioSegment

TOKEN = os.environ['SILLYTANUS_KEY']
SBER = os.environ['SBER_API']
SBER_AUTH = os.environ['SBER_AUTH']
gemini_url = os.environ['GEMINI_URL']


def bot_check():
  return "Good-good"


def update_sber_token():
  rq_uid = "a251ed87-fcfa-11ec-860a-005056992257"
  api_scope = "SALUTE_SPEECH_PERS"
  """
  Отправляет POST запрос к серверу Sberbank для получения OAuth токена.

  :param auth_data: Авторизационные данные в формате Basic Auth.
  :param rq_uid: Значение UUID или GUID для уникальной идентификации запроса.
  :param api_scope: Версия API, к которой запрашивается доступ.
  :return: Словарь с токеном доступа и временем его истечения или сообщение об ошибке.
  """
  url = 'https://ngw.devices.sberbank.ru:9443/api/v2/oauth'
  headers = {
      'Authorization': f'Basic {SBER_AUTH}',
      'RqUID': rq_uid,
      'Content-Type': 'application/x-www-form-urlencoded',
  }
  data = {
      'scope': api_scope,
  }

  response = requests.post(url, headers=headers, data=data, verify='chain.pem')

  # Проверяем, успешно ли выполнен запрос
  if response.status_code == 200:
    # Преобразуем ответ от сервера в JSON и извлекаем данные
    response_data = response.json()
    return response_data.get('access_token')
  else:
    return f"Request failed with status code: {response.status_code}"


def add_he():
  # Генерируем случайное число с плавающей точкой в диапазоне от 0 до 1
  rand_number = random.random()

  # Определяем количество повторений строки "хе"
  if rand_number < 0.75:  # Вероятность 0 раз
    repetitions = 0
  elif rand_number < 0.8125:  # Вероятность 1 раз (0.75 + 0.0625)
    repetitions = 1
  elif rand_number < 0.875:  # Вероятность 2 раза (0.8125 + 0.0625)
    repetitions = 2
  elif rand_number < 0.9375:  # Вероятность 3 раза (0.875 + 0.0625)
    repetitions = 3
  else:  # Вероятность 4 раза (0.9375 + 0.0625)
    repetitions = 4

  # Генерируем и возвращаем итоговую строку
  return ", " + "хе" * repetitions


async def get_voice(prompt):
  global SBER
  headers = {
      "Authorization": "Bearer " + SBER,
      "Content-Type": "application/ssml"
  }
  rand_number = random.random()
  if rand_number < 0.75:
    laugh = ""
  else:
    laugh = "<audio text=\"sm-sounds-human-laugh-4\"/>"
  url = "https://smartspeech.sber.ru/rest/v1/text:synthesize?format=opus&voice=May_24000"
  prompt = "<speak><paint pitch=\"1\">" + prompt + "</paint>" + laugh + "</speak>"
  response = requests.post(url,
                           headers=headers,
                           data=prompt,
                           verify='chain.pem')

  if response.status_code == 200:
    return response.content

  SBER = update_sber_token()
  return await get_voice(prompt)


async def handle_voice(update: Update, context: CallbackContext):
  global SBER
  print("Voice received")
  url = "https://smartspeech.sber.ru/rest/v1/speech:recognize"
  audio_file = await update.message.voice.get_file()
  #audio_file_bytes = await audio_file.download_as_bytearray()
  '''
  audio = AudioSegment.from_file(io.BytesIO(audio_file_bytes), format="ogg")
  start_time = 0 * 1000  # начало обрезки в миллисекундах
  end_time = 5 * 1000  # конец обрезки в миллисекундах
  trimmed_audio = audio[start_time:end_time]
  output_io = io.BytesIO()
  trimmed_audio.export(output_io, format='ogg')
  output_io.seek(0)
  audio_file_bytes = output_io
  '''

  await audio_file.download_to_drive('voice.ogg')

  # Загрузка аудио и обрезка до 5 секунд
  audio = AudioSegment.from_file('voice.ogg')
  audio = audio[:3000]  # Обрезка до первых 5 секунд

  # Ускорение в 2 раза
  #audio = audio.speedup(playback_speed=1.5)

  # Сохранение обработанного файла
  audio.export('processed_voice.opus', format="opus")

  # Отправка файла обратно пользователю
  with open('processed_voice.opus', 'rb') as audio_file:
    audio_file_data = audio_file.read()
  audio_file_bytes = bytearray(audio_file_data)

  # Удаление временных файлов
  os.remove('voice.ogg')
  os.remove('processed_voice.opus')

  headers = {
      "Authorization": "Bearer " + SBER,
      "Content-Type": "audio/ogg;codecs=opus"
  }
  response = requests.post(url,
                           headers=headers,
                           data=audio_file_bytes,
                           verify='chain.pem')

  if response.status_code != 200:
    SBER = update_sber_token()
    headers = {
        "Authorization": "Bearer " + SBER,
        "Content-Type": "audio/ogg;codecs=opus"
    }
    response = requests.post(url,
                             headers=headers,
                             data=audio_file_bytes,
                             verify='chain.pem')
  print(response)
  response_data = response.json()
  # Проверяем, есть ли поле 'result' в ответе и оно не пустое
  if 'result' in response_data and isinstance(
      response_data['result'], list) and len(response_data['result']) > 0:
    # Склеиваем строки из массива 'result' в одну строку
    result_string = ' '.join(response_data['result'])
    reply = await chat_with_gpt(result_string)
    #reply += add_he()
    binary_data = await get_voice(reply)
    voice_file = InputFile(io.BytesIO(binary_data), filename="voice.opus")
    # Отправка голосового сообщения
    await update.message.reply_voice(voice=voice_file)
    return


async def restart(update: Update, context: CallbackContext):
  await update.message.reply_text("ухх бля ебать")


#-------------------------------------------------
async def handle_message(update: Update, context: CallbackContext):
  if not update.message:
    return

  chat_data = context.chat_data
  user_id = update.message.from_user.id
  reply_to_message = update.message.reply_to_message

  if update.message.text[:1].lower() == ".":
    return
  prompt = update.message.text
  reply = await chat_with_gpt(prompt)
  #reply += add_he()
  binary_data = await get_voice(reply)
  voice_file = InputFile(io.BytesIO(binary_data), filename="voice.opus")
  # Отправка голосового сообщения
  await update.message.reply_voice(voice=voice_file)
  return


async def handle_start(update: Update, context: CallbackContext):
  with open("starttext.txt", 'r') as file:
    starttext = file.read()
  await update.message.reply_text(starttext)
  return


async def chat_with_gpt(prompt):

  moscow_tz = pytz.timezone('Europe/Moscow')
  now = datetime.now(moscow_tz)
  date_string = now.strftime('%Y-%m-%d')
  time_string = now.strftime('%H:%M:%S')

  print("?: " + prompt)

  response_data = requests.get(gemini_url + "?e=" + prompt)

  # Проверяем, что запрос был успешным
  if response_data.status_code == 200:
    # Получаем содержимое ответа в виде строки
    response = response_data.text
  else:
    response = "что-то ничего не понимаю"
  print("!: " + response + "\n")

  filename = date_string + '_dialogues.csv'
  with open(filename, 'a', newline='') as file:
    writer = csv.writer(file, delimiter=';')
    writer.writerow([date_string, time_string, prompt, response])
  return response


#-------------------------------------------------


def main():
  application = Application.builder().token(TOKEN).build()

  application.add_handler(CommandHandler("start", handle_start))
  application.add_handler(CommandHandler("restart", restart))
  # application.add_handler(
  #     MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
  application.add_handler(MessageHandler(filters.VOICE, handle_voice))

  application.run_polling(allowed_updates=Update.ALL_TYPES)

  return ("I'm alive")


#t = threading.Thread(target=main)
#t.start()

if __name__ == '__main__':
  main()
