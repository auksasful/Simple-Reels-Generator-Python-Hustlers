import re
import json
from modules.base_generator import BaseGenerator
from modules.writer.writer import Writer
from collections import defaultdict
from config import Config


class ScriptDivider(BaseGenerator):
    def __init__(self, project_folder, append=False):
        # Call the constructor of the base class
        super().__init__(project_folder)
        self.header = '"Scene" |^| "Duration" |^| "Text" |^| "Visuals" |^| "Hashtags" |^| "Description"'
        self.header_met = False
        self.videos = self.initialize_videos(self.script_videos_file_path, append)
        self.current_video_id = len(self.videos)

    def read_script_data(self):
        data = self.read_csv(self.script_file_path)
        return data
    
    def execute(self, shorten_speech=False):
        script_file_path = self.script_file_path


        with open(script_file_path, "r", encoding="utf-8") as f:
            old_json_strings = f.readlines()
            new_json_data = self.transform_data(old_json_strings, shorten_speech=shorten_speech)

        self.write_json(self.script_videos_file_path, new_json_data)

    def transform_data(self, old_json_strings, shorten_speech=False):
        """
        Accepts a list of JSON strings in the old format
        and returns a list of dictionaries in the new format.
        """
        result = []
        for index, json_str in enumerate(old_json_strings, start=1):
            json_str = json_str.strip()
            if json_str.startswith('"') and json_str.endswith('"'):
                json_str = json_str[1:-1].replace('""', '"').replace("*", "")
            old_data = json.loads(json_str)
    
            scene_objects = old_data.get("Scenes", [])
            
            scenes_list = []
            scenes_text = ""
            for i, s_obj in enumerate(scene_objects, start=1):
                text = s_obj.get("What_Speaker_Says_In_First_Person", "")
                if shorten_speech:
                    writer = Writer(Config.NAGA_AC_API_KEY, Config.GEMINI_API_KEY, Config.GROQ_API_KEY)
                    text = writer.generate_text_gemini(text + " the last time it was too long, please generate a way shorter text maintaining the same speaker tone and meaning. Separate the actual text you generated with symbol '|' from start to end, as if they were quotes. For example: 'Here is the text I generated: |This is very good! Check the link!|'. Another example: 'I shortened the text as you asked: |Get the product from the link!|'.", structure=False)
                    print('shorten_speech from prompt (not clean): ', text)
                    # get the text between the quotes
                    text = re.search(r"\|(.+?)\|", text)
                    if text:
                        text = text.group(1).strip()
                    else:
                        text = s_obj.get("What_Speaker_Says_In_First_Person", "")
                    
                scenes_list.append({
                    "scene": str(i),
                    # "duration": 3,
                    "text": self.remove_symbols_script(text.replace("'", "")),
                    "visuals": s_obj.get("Visuals", ""),
                    # "hashtags": old_data.get("Hashtags", ""),
                    # "description": old_data.get("Description", "")
                })
                scenes_text += f"{i}. {s_obj.get('What_Speaker_Says_In_First_Person', '')}\n"
                scenes_text += f"{s_obj.get('Visuals', '')}\n\n"

            writer = Writer(Config.NAGA_AC_API_KEY, Config.GEMINI_API_KEY, Config.GROQ_API_KEY)

            system_prompt = """Write an engaging caption for the video based on given description that will be posted on instagram. Make them quite short, but include all the parts recommended.

            HOOK (H): Grab attention in the first place with an awesome opening line which baits your audience to read into your caption...This could be the beginning of your storytelling, just one line which encourages readers to continue, you want to make sure as many people as possible go through your captions, you'll sell more!

            RELATABILITY (R): Be relatable, your beliefs must be similar to those of your audience. What I mean is, if you write a belief about how life-ruining a 9-5 job can be, you should know that your ideal customer is currently in a 9-5 job & will strongly resonate with what you are writing down! Be relatable all along, this works for writing captions but implement it everywhere, especially in your stories too, but we'll get into that later on.

            CALL TO ACTION (CTA): End your captions, and every single one of them, with a call to action. More often than not, this CTA must be towards selling your product, but in order to not have a selling CTA each time, you can make sure than out of 42 captions you write (so 3 a day for 2 weeks before starting over) 12 of them are not related to your products, so it can be a CTA such as "make sure to watch my stories to not miss out on exclusive motivation tips!" Or a CTA such as "Follow @xprofile for more content on X!"

            For all your other captions & CTAs make sure they are CTAs relating to your products & services, such as "If you're looking to build a business on Instagram & do not know where to start, make sure to DM me the word 'IGMONEY' and I'll get back to you to see if you fit to work 1 on 1 with me!"
            
            Do NOT explain what you are doing, just write the caption as if you were writing it for your own Instagram account.

            Make sure it is very shortened, less than 100 characters.
            """

            caption = writer.generate_text_pollinations(scenes_text)


            result.append({
                "video": index,
                "caption": caption,
                "scenes": scenes_list
            })

        return result


    def initialize_videos(self, json_file_path, append):
        videos = defaultdict(lambda: {"scenes": []}) 
        if not append:
            return videos 
        # Load the initial videos data from a JSON file 
        initial_videos = self.read_json(json_file_path)
        # Convert the list to a defaultdict 
        for video in initial_videos: 
            video_id = video["video"] 
            videos[video_id]["scenes"] = video["scenes"] 

        return videos

        