import requests

API_URL = "http://localhost:8000/analyze-call"
AUDIO_FILE = "test_audio/student_call.wav"

with open(AUDIO_FILE, "rb") as f:
    files = {"file": f}
    response = requests.post(API_URL, files=files)

print(response.status_code)
print(response.json())