from collections import defaultdict
from datetime import datetime
import random
import time
import os
import re
import uuid
from PIL import Image
import requests
from modules.base_generator import BaseGenerator
from modules.pollinations_utils import PollinationsUtils


class ImageGenerator(BaseGenerator):
    def __init__(self, project_folder, width=1080, height=1920):
        # Call the constructor of the base class
        super().__init__(project_folder)
        self.width = width
        self.height = height
        self.videos = self.initialize_videos()
        self.pollinations_utils = PollinationsUtils()

    def read_image_prompts_json(self):
        return self.read_json(self.image_prompts_file_path)
    
    def read_script_videos_json(self):
        return self.read_json(self.script_videos_file_path)
    
    def write_json_data(self):
        json_data = [{"video": video_id, **video_data} for video_id, video_data in self.videos.items()]
        self.write_json(self.image_paths_file_path, json_data)

    def execute(self, video_id, scene, prompt, generation_chance=0.3):
        save_path = os.path.join(self.generated_images, str(video_id), self.remove_symbols(scene))
        os.makedirs(save_path, exist_ok=True)
        if random.random() <= generation_chance:
            self.pollinations_utils = PollinationsUtils()
            image_path = self.pollinations_utils.generate_image(prompt, save_path, self.width, self.height, False)
            if image_path == None:
                image_path = ""
            # image_path = self.generate_images_pollynation_ai_legacy(prompt=prompt, save_path=save_path)
            # self.trim_and_resize_image(image_path, self.width, self.height)
        else:
            image_path = ""

        scene_data = { 
            "scene": scene, 
            "image_path": image_path,
            "google_image_path": ""
        } 
        if "scenes" not in self.videos[video_id]:
            self.videos[video_id]["scenes"] = []
        self.videos[video_id]["scenes"].append(scene_data)


    def generate_images_pollynation_ai_legacy(self, prompt, save_path):
        # Format the prompt for the URL
        prompt += str(uuid.uuid4())
        formatted_prompt = prompt.replace(" ", "-")
        url = f"https://image.pollinations.ai/prompt/{formatted_prompt}"

        while True:
            try:
                # Make the request to the API
                response = requests.get(url)
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
                    # Open the saved image
                    image = Image.open(image_save_path)

                    # Crop 50 pixels from the bottom
                    image = image.crop((0, 0, image.width, image.height - 48))

                    # Calculate the new dimensions for cropping
                    width, height = image.size
                    # crop_height = int((width - 170) * 1.2)

                    # Crop the image to the new dimensions
                    left = 0
                    top = 0
                    right = width
                    bottom = height - 100
                    cropped_image = image.crop((left, top, right, bottom))

                    # Save the cropped image
                    cropped_image.save(image_save_path)
                    return image_save_path
                else:
                    print(f"Failed to generate image. Status code: {response.status_code}. Retrying...")
            except requests.RequestException as e:
                print(f"Request failed: {e}. Retrying...")
            time.sleep(5)  # Wait for 5 seconds before retrying


    def trim_and_resize_image(self, image_path, width, height):
        # Open the image
        image = Image.open(image_path)
        
        # Calculate the aspect ratios
        original_aspect = image.width / image.height
        target_aspect = width / height
        
        # Determine the new dimensions
        if original_aspect > target_aspect:
            # Trim the sides
            new_width = int(target_aspect * image.height)
            left = (image.width - new_width) // 2
            right = left + new_width
            top = 0
            bottom = image.height
        else:
            # Trim the top and bottom
            new_height = int(image.width / target_aspect)
            top = (image.height - new_height) // 2
            bottom = top + new_height
            left = 0
            right = image.width
        
        # Crop the image
        image = image.crop((left, top, right, bottom))
        
        # Resize the image
        image = image.resize((width, height), Image.LANCZOS)
        
        # Save the image, replacing the original
        image.save(image_path)
        print(f"Image saved to {image_path}")
    

    def initialize_videos(self):
        videos = defaultdict(lambda: {"scenes": []}) 
        return videos 
