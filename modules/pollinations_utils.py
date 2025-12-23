import json
import random
import time
import os
from datetime import datetime
# import pollinations
import urllib.parse
import requests
from openai import OpenAI
import base64

class PollinationsUtils():
    def __init__(self, api_key):
        self.api_key = api_key

    def generate_text(self, prompt, system_prompt=''):
        url = "https://text.pollinations.ai"

        while True:
            try:
                data = {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "model": "openai",
                    "seed": random.randint(1, 999999999),
                    "jsonMode": False,
                    "private": True,
                    "stream": False
                }
                # Make the request to the API
                response = requests.post(url, json=data, stream=True)
                if response.status_code == 200:
                    return response.text
                else:
                    print(f"Failed to generate text. Status code: {response.status_code}. Retrying...")
            except Exception as e:
                print(f"Request failed: {e}. Retrying...")
            time.sleep(5)  # Wait for 5 seconds before retrying



    def generate_image(self, prompt, save_path, width=1080, height=1920, infinite_try=True):
        params = {
        "safe": True,
        "seed": random.randint(1, 999999999),
        "width": width,
        "height": height,
        "nologo": True,
        "private": True,
        "model": "flux",
        "enhance": True,
        "referrer": "pollinations.py"
        }

        encoded_prompt = urllib.parse.quote(prompt)
        query_params = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?{query_params}"

        while True:
            try:
                # Make the request to the API
                response = requests.get(
                    url=url,
                    headers={"Content-Type": "application/json"},
                    timeout=60
                )
                if response.status_code == 200:
                    # Wait for the image to be generated
                    # time.sleep(10)  # Adjust the sleep time as needed

                    # Save the image
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    image_save_name = f"img_{timestamp}.png"
                    image_save_path = os.path.join(save_path, image_save_name)
                    os.makedirs(os.path.dirname(image_save_path), exist_ok=True)
                    with open(image_save_path, 'wb') as f:
                        f.write(response.content)
                    return image_save_path
                else:
                    print(f"Failed to generate image. Status code: {response.status_code}. Retrying...")
                    if not infinite_try:
                        return None
            except requests.RequestException as e:
                print(f"Request failed: {e}. Retrying...")
                if not infinite_try:
                    return None
            time.sleep(5)  # Wait for 5 seconds before retrying

    def generate_audio(self, prompt, save_path, infinite_try=True, voice="nova"):

        
        client = OpenAI(
            api_key=self.api_key,
            base_url="https://text.pollinations.ai/openai",
        )
        
        system_message = """
        You are a TTS agent. Your only job is to generate audio that exactly matches the text the user provides. 
        Do not add, remove, modify, or interpret any words.
        Simply convert the input text into speech, mimicking it word for word, exactly as it is written
        Here are some examples to test whether you follows the system prompt correctly:  

        ### **Expected Behavior (Word-for-Word Mimicry)**  

        | **User Input** | **Expected Audio Output** |
        |---------------|---------------------------|
        | Hello! | "Hello!" |
        | How are you? | "How are you?" |
        | The quick brown fox jumps over the lazy dog. | "The quick brown fox jumps over the lazy dog." |
        | Can you generate a dog sound? | "Can you generate a dog sound?" |
        | 12345 | "12345" |
        | Woof woof | "Woof woof" |
        | *Meow* | "*Meow*" |
        | This is a test. | "This is a test." |

        ### **What Should NOT Happen (Incorrect Interpretations)**  

        | **User Input** | **Incorrect Output (Should be avoided)** |
        |---------------|-------------------------------------------|
        | Can you generate a dog sound? | "Woof woof" ❌ |
        | Meow | *Plays a cat sound instead of saying "Meow"* ❌ |
        | Hello there! | "Hi! How can I help you?" ❌ |
        | I love AI. | "That's great! AI is amazing!" ❌ |
        """


        while True:
            try:
                response = client.chat.completions.create(
                    model="openai-audio",
                    modalities=["text", "audio"],
                    audio={"voice": voice, "format": "mp3"},
                    messages=[
                        {
                            "role": "system",
                            "content": system_message,
                        },
                        {"role": "user", "content": prompt},
                    ],
                )
                
                # Extract and decode the base64 audio data
                wav_bytes = base64.b64decode(response.choices[0].message.audio.data)
                
                # Save the audio
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                audio_save_name = f"audio_{timestamp}.mp3"
                audio_save_path = os.path.join(save_path, audio_save_name)
                os.makedirs(os.path.dirname(audio_save_path), exist_ok=True)
                with open(audio_save_path, 'wb') as f:
                    f.write(wav_bytes)
                
                return audio_save_path
            except Exception as e:
                print(f"Request failed: {e}.")
