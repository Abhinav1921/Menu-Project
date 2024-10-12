from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from gtts import gTTS
import os
import time
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
import ctypes
import pythoncom
import smtplib
from twilio.rest import Client
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
import cv2
import numpy as np
import base64
import numpy as np
import matplotlib.pyplot as plt
import io
from PIL import Image, ImageDraw, ImageFilter
from botocore.exceptions import ClientError
import subprocess
app = Flask(__name__)
CORS(app)

def get_volume_interface():
    # Initialize COM
    pythoncom.CoInitialize()

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))

# Twilio credentials
TWILIO_ACCOUNT_SID = 'AC77f6fd14c7566f8dafa7969f7e03d85a'
TWILIO_AUTH_TOKEN = 'cd538e46b036fda6036d72892cea42bf'
TWILIO_PHONE_NUMBER = '+13204416134'
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def detect_and_crop_face():
    # Initialize the webcam
    cap = cv2.VideoCapture(0)
    time.sleep(5)  # Wait for 5 seconds before capturing the image

    # Capture frame-by-frame from the webcam
    ret, frame = cap.read()
    if not ret:
        return None, "Failed to capture image"

    # Convert frame to grayscale for face detection
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect faces in the frame
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

    for (x, y, w, h) in faces:
        # Crop the face from the frame
        face_crop = frame[y:y + h, x:x + w]
        
        # Encode the cropped image to base64 to send back to the frontend
        _, buffer = cv2.imencode('.png', face_crop)
        face_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return face_base64, None

    return None, "No face detected"


def google_search(query):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    query = query.replace(' ', '+')
    url = f"https://www.google.com/search?q={query}"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print("Failed to retrieve page")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    results = []

    for g in soup.find_all('div', class_='g', limit=5):
        title_element = g.find('h3')
        link_element = g.find('a')
        snippet_element = g.find('span', class_='aCOpRe')

        if title_element and link_element:
            title = title_element.get_text()
            link = link_element['href']

            if link.startswith('/url?q='):
                link = link.split('/url?q=')[1].split('&')[0]

            snippet = snippet_element.get_text() if snippet_element else ""

            results.append({"title": title, "link": link, "snippet": snippet})

    return results

@app.route('/search', methods=['POST'])
def search():
    data = request.json
    query = data.get('query')
    if not query:
        return jsonify({"error": "Query is required"}), 400

    results = google_search(query)
    return jsonify(results)

@app.route('/send_email', methods=['POST'])
def send_email():
    try:
        data = request.get_json()
        sender_email = data.get('sender_email')
        password = data.get('password')
        receiver_email = data.get('receiver_email')
        message = data.get('message')

        # Set up the SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, password)

        # Send the email
        email_body = f"Subject: New Message\n\n{message}"
        server.sendmail(sender_email, receiver_email, email_body)
        server.quit()

        return jsonify("Email sent successfully!"), 200
    except smtplib.SMTPAuthenticationError:
        return jsonify("Failed to authenticate. Check your email and password."), 401
    except Exception as e:
        return jsonify(f"An error occurred: {e}"), 500

@app.route('/text-to-speech', methods=['POST'])
def text_to_speech():
    data = request.get_json()
    text = data.get('text', '')

    if text.strip() == "":
        return jsonify({"error": "No text provided"}), 400

    # Generate the TTS file
    try:
        tts = gTTS(text=text, lang='en')
        filename = f"speech_{int(time.time())}.mp3"  # Create a unique filename using a timestamp
        filepath = os.path.join('static', filename)
        tts.save(filepath)

        return jsonify({"speech_url": f"/static/{filename}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/set_volume', methods=['POST'])
def set_volume():
    volume_level = request.json.get('volume')
    if volume_level is None:
        return jsonify({'error': 'No volume level provided'}), 400

    # Set the system volume
    volume_interface = get_volume_interface()
    volume_interface.SetMasterVolumeLevelScalar(int(volume_level) / 100, None)

    return jsonify({'success': True})
@app.route('/get_geo_location', methods=['GET'])
def get_geo_location():
    # Call the external API to get geolocation data
    response = requests.get("https://ipinfo.io")
    data = response.json()
    location = data['loc'].split(',')
    latitude = location[0]
    longitude = location[1]
    city = data.get('city')
    region = data.get('region')
    country = data.get('country')

    # Return the geolocation data as JSON
    return jsonify({
        'latitude': latitude,
        'longitude': longitude,
        'city': city,
        'region': region,
        'country': country
    })
@app.route('/send_sms', methods=['POST'])
def send_sms():
    data = request.get_json()
    to_number = data['to']
    message_body = data['message']

    try:
        message = client.messages.create(
            body=message_body,
            from_=TWILIO_PHONE_NUMBER,
            to=to_number
        )
        return jsonify({'status': 'success', 'sid': message.sid}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
@app.route('/make_call', methods=['POST'])
def make_call():
    data = request.json
    to_phone = data.get('to_phone')

    try:
        call = client.calls.create(
            to=to_phone,
            from_=TWILIO_PHONE_NUMBER,
            url="http://demo.twilio.com/docs/voice.xml"
        )
        return jsonify({"status": "success", "call_sid": call.sid}), 200
    except Exception as e:
        return jsonify({"status": "failed", "message": str(e)}), 500
@app.route('/send_bulk_email', methods=['POST'])
def send_bulk_email():
    try:
        data = request.get_json()
        sender_email = data.get('sender_email')
        password = data.get('password')
        receiver_emails = data.get('receiver_emails')  # List of emails
        message = data.get('message')

        # Set up the SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, password)

        # Email subject and message body
        email_body = f"Subject: New Message\n\n{message}"

        # Send email to each recipient
        for receiver_email in receiver_emails:
            server.sendmail(sender_email, receiver_email, email_body)

        server.quit()

        return jsonify("Bulk emails sent successfully!"), 200
    except smtplib.SMTPAuthenticationError:
        return jsonify("Failed to authenticate. Check your email and password."), 401
    except Exception as e:
        return jsonify(f"An error occurred: {e}"), 500
    
@app.route('/full_capture', methods=['POST'])
def full_capture():
    filter_type = request.form.get('filter')

    # Initialize the webcam
    cap = cv2.VideoCapture(0)
    time.sleep(5)  # Wait for 5 seconds to simulate timer

    # Capture the image from the webcam
    ret, frame = cap.read()
    cap.release()

    if not ret:
        return jsonify({'status': 'error', 'message': 'Failed to capture image'})

    # Apply the selected filter to the entire frame
    filtered_image = apply_filter(frame, filter_type)

    # Encode the filtered image to base64 format to send to the frontend
    _, buffer = cv2.imencode('.png', filtered_image)
    image_base64 = base64.b64encode(buffer).decode('utf-8')

    return jsonify({'status': 'success', 'image': image_base64})    
if __name__ == "__main__":
    app.run(port=5000, host='0.0.0.0')
