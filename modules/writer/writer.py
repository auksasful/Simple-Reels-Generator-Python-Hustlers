import time
from openai import OpenAI
from modules.pollinations_utils import PollinationsUtils
from modules.script_entity import Scene, Videos
from google import genai
from google.genai import types
import json
import re


class Writer:
    def __init__(self, pollinations_api_key, gemini_api_key):
        self.gemini_api_key = gemini_api_key
        self.pollinations_api_key = pollinations_api_key
        self.pollinations_utils = PollinationsUtils(api_key=pollinations_api_key)

        self.model_errors_file = "model_errors.txt"

        # Initialize or reset model error counters
        try:
            with open(self.model_errors_file, "w") as f:
                f.write("pollinations 0")
        except Exception as e:
            print(f"Error creating/resetting model errors file: {e}")
    
    def generate_text_pollinations(self, prompt, system_prompt=''):
        pollinations = PollinationsUtils(api_key=self.pollinations_api_key)
        response = pollinations.generate_text(prompt, system_prompt)
        return response

    def generate_text_gemini(self, prompt, system_prompt=''):
        client = genai.Client(api_key=self.gemini_api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction='generate structure: Visuals and What_Speaker_Says_In_First_Person',
            )
        )
        time.sleep(10)
        return response.text
    
    def structure_script_gemini(self, prompt):
        client = genai.Client(api_key=self.gemini_api_key)
        prompt = f"""
        Get text from the script based on the schema given. 

        {prompt}"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Videos
            )
        )

        try:
            # Attempt to parse the response text as JSON
            json.loads(response.text)

        except json.JSONDecodeError as e:
            # If parsing fails, print the error and the raw response text
            print(f"Error decoding JSON: {e}")
            print(f"Raw response text: {response.text}")
        # wait 10 seconds so that the server would not be overloaded
        time.sleep(10)
        return response.text
    
    @staticmethod
    def remove_symbols(text):
        # Remove asterisks and underscores and the text between them
        # Process asterisks: remove *content*
        text = re.sub(r'\*.*?\*', '', text, flags=re.DOTALL)
        # Process underscores: remove _content_
        text = re.sub(r'_.*?_', '', text, flags=re.DOTALL)
        # process brackets: remove [content]
        text = re.sub(r'\[.*?\]', '', text, flags=re.DOTALL)
        return text.replace("*", "").replace("_", "").replace ("[", "").replace("]", "")

    