import os

from openai import OpenAI
# from g4f.client import Client
import os
import re
import sqlite3
import requests


from modules.base_generator import BaseGenerator
from modules.writer.writer import Writer
import json


class ScriptWriter(BaseGenerator):
    def __init__(self, project_folder, pollinations_api_key, gemini_api_key):
        super().__init__(project_folder)
        self.writer = Writer(pollinations_api_key=pollinations_api_key, gemini_api_key=gemini_api_key)

    def execute(self, prompt, more_scenes=False, max_scenes=100, length_limit=10000):
        # Try to structure and validate the JSON
        
        valid_json = False
        max_attempts = 20
        attempts = 0
        response = ""
        
        while not valid_json and attempts < max_attempts:
            try:
                response = self.writer.generate_text_gemini(prompt)

                if more_scenes:
                    # Check if response contains at least 5 instances of "scene"
                    scene_count = 0
                    if response:
                        scene_count = len(re.findall(r'scene', response, re.IGNORECASE))
                        
                    max_scene_attempts = 10
                    scene_attempts = 0
                    while scene_count < 3 and scene_attempts < max_scene_attempts:
                        response = self.writer.generate_text_gemini(prompt, " the last time it was less than 3 scenes, please generate 3 or more scenes")
                        if response:
                            scene_count = len(re.findall(r'scene', response, re.IGNORECASE))
                        scene_attempts += 1
                
                max_scene_attempts = 10
                scene_count = 0
                if response:
                    scene_count = len(re.findall(r'scene', response, re.IGNORECASE))
                while scene_count > max_scenes and max_scene_attempts < 10:
                    response = self.writer.generate_text_gemini(prompt, " the last time it was more than " + str(max_scenes) + " scenes, please generate " + str(max_scenes) + " or less scenes")
                    if response:
                        scene_count = len(re.findall(r'scene', response, re.IGNORECASE))
                    max_scene_attempts += 1

                max_length_attempts = 10
                while len(response) > length_limit and max_length_attempts < 10:
                    response = self.writer.generate_text_gemini(prompt, " the last time it was too long, please generate a shorter response. " + str(length_limit) + " characters or less")
                    max_length_attempts += 1
                
                response = self.writer.structure_script_gemini(response)
                json.loads(response)  # Validate JSON
                valid_json = True
                # put the whole response into a one line
                response = re.sub(r'\n', '', response)
            except json.JSONDecodeError:
                attempts += 1
                if attempts >= max_attempts:
                    # If all attempts fail, return the last structured attempt
                    break
        # file_path = self.script_file_path
        # self.write_csv(file_path, response)
        return response


