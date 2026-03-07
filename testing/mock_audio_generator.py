import pyttsx3
import os

OUTPUT_DIR = "test_audio"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_mock_audio(filename="student_call.wav"):
    text = (
        "Hello, I have a few questions about the Computer Science course. "
        "How much is the tuition fee? "
        "I also want to know about placement statistics. "
        "Can my parents attend the orientation? "
        "When is the admission deadline?"
    )

    engine = pyttsx3.init()
    engine.save_to_file(text, os.path.join(OUTPUT_DIR, filename))
    engine.runAndWait()
    print(f"Mock audio generated: {os.path.join(OUTPUT_DIR, filename)}")

if __name__ == "__main__":
    generate_mock_audio()