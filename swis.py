import speech_recognition as sr
from pydub import AudioSegment
from get_key import get_key

def swis() -> str:
    path = get_key()

    wav = "/tmp/key.wav"
    AudioSegment.from_mp3(path).export(wav, format="wav")

    r = sr.Recognizer()
    with sr.AudioFile(wav) as source:
        r.adjust_for_ambient_noise(source, duration=0.5)
        data = r.record(source)

    text = r.recognize_google(data)
    print(f"  📝  Text  ➜  \033[1;33m{text}\033[0m\n")
    return text

if __name__ == "__main__":
    swis()
