import os
import re
from modules.base_generator import BaseGenerator
from openai import OpenAI
from modules.nagaac_utils import NagaACUtils
from modules.pollinations_utils import PollinationsUtils
from fish_audio_sdk import Session, TTSRequest, ReferenceAudio
from io import BytesIO
from config import Config
from pedalboard.io import AudioFile
from pedalboard import Pedalboard, NoiseGate, Compressor, LowShelfFilter, Gain
import noisereduce as nr
import soundfile as sf
import numpy as np


class VoiceGenerator(BaseGenerator):
    def __init__(self, project_folder, api_key, use_fish=False, use_nagaac=False, api_url="https://api.naga.ac/v1", voice_model_whitelist=['default-eleven-monolingual-v1', 'default-eleven-turbo-v2', 'default-eleven-multilingual-v1', 'default-eleven-multilingual-v2']):
        # Call the constructor of the base class
        super().__init__(project_folder)

        self.client = OpenAI(base_url=api_url,api_key=api_key)

        self.nagaac_utils = NagaACUtils(api_key, api_url=api_url, text_model_whitelist=[], image_model_whitelist=[], voice_model_whitelist=voice_model_whitelist)

        self.use_nagaac = use_nagaac
        self.use_fish = use_fish
        self.pollinations_utils = PollinationsUtils()



    def read_json_data(self):
        return self.read_json(self.script_videos_file_path)


    def execute(self, video_id, scene, prompt, voice):
        save_path = os.path.join(self.generated_images, str(video_id), self.remove_symbols(scene))
        os.makedirs(save_path, exist_ok=True)

        if self.use_nagaac:
            response = self.generate_voice_nagaac(prompt, voice=voice)
        elif self.use_fish:
            response = self.generate_trump_voice_fish(prompt)
        else:
            response = self.pollinations_utils.generate_audio(prompt, save_path)
        # print(response)
        # save the audio file
        file_name = os.path.join(save_path, "voiceover.mp3")
        with open(file_name, "wb") as f:
            if self.use_nagaac:
                f.write(response.content)
            else:
                f.write(response)

        # Enhance the audio file
        self.enhance_audio_overwrite(file_name)


    def generate_trump_voice_fish(self, prompt):

        # Create a session with the API key
        session = Session(Config.FISH_API_KEY)
        
        # Use a BytesIO object to store the audio content
        audio_content = BytesIO()
        
        # Generate the TTS using Trump's reference ID
        for chunk in session.tts(TTSRequest(
            reference_id="5196af35f6ff4a0dbf541793fc9f2157",
            text=prompt
        )):
            audio_content.write(chunk)
        
        # Return the audio content
        return audio_content.getvalue()

    def generate_voice_nagaac(self, prompt, voice, system_prompt=''):
        current_model_id = self.nagaac_utils.get_best_model(image_model=False, voice_model=True)
        print(current_model_id)
        rate_limit_cheked = False
        rate_limit_exceeded = False
        while not rate_limit_cheked:
            try:
                response = self.client.audio.speech.create(model=current_model_id,
                                            input=prompt,
                                            voice=voice,
                                            speed=1)
                rate_limit_exceeded = False
                self.nagaac_utils.update_api_usage(current_model_id, exceeded=rate_limit_exceeded, voice_model=True)
            except Exception as e:
                print(e)
                if 'rate_limit_exceeded' or 'Invalid model' or 'no_sources_available' or 'Input should be' in str(e):
                    rate_limit_exceeded = True
                    self.nagaac_utils.update_api_usage(current_model_id, exceeded=rate_limit_exceeded, voice_model=True)
                    current_model_id = self.nagaac_utils.get_best_model(image_model=False, voice_model=True)
            rate_limit_cheked = not rate_limit_exceeded
        return response

    @staticmethod
    def remove_symbols(text): 
        # Replace non-space symbols with an empty string 
        return re.sub(r'[^\w\s]', '', text)
    

    @staticmethod
    def enhance_audio_overwrite(file_path: str, sr: int = 44100):
        """
        Enhances the audio file at the given path using noise reduction
        and pedalboard effects, then overwrites the original file.

        Args:
            file_path (str): The path to the audio file (e.g., 'sound.mp3').
            sr (int): The target sample rate. Defaults to 44100.
        """
        try:
            # Loading audio
            with AudioFile(file_path).resampled_to(sr) as f:
                audio = f.read(f.frames)
                # Ensure audio is mono for noisereduce if it expects 1D array
                # If stereo, process channels separately or average
                if audio.shape[0] > 1:
                    # Process first channel or average channels
                    # Example: process first channel
                    audio_mono = audio[0, :]
                    # Or average: audio_mono = np.mean(audio, axis=0)
                else:
                    audio_mono = audio.flatten() # Ensure it's 1D

            # Noisereduction
            # Note: noisereduce might work better with float arrays
            reduced_noise = nr.reduce_noise(y=audio_mono, sr=sr, stationary=True, prop_decrease=0.75)

            # If original was stereo, duplicate the processed mono channel back to stereo
            # Or apply effects channel-wise if needed
            if audio.shape[0] > 1:
                # This creates a stereo file from the processed mono track
                # For more sophisticated stereo processing, apply effects per channel
                # or use stereo-aware effects if available in pedalboard
                reduced_noise_stereo = np.vstack((reduced_noise, reduced_noise))
                input_to_board = reduced_noise_stereo
            else:
                input_to_board = reduced_noise # Keep as mono if original was mono

            # Enhancing through pedalboard
            board = Pedalboard([
                NoiseGate(threshold_db=-30, ratio=1.5, release_ms=250),
                Compressor(threshold_db=-16, ratio=4),
                LowShelfFilter(cutoff_frequency_hz=400, gain_db=10, q=1),
                Gain(gain_db=2)
            ])

            # Apply effects
            # Pedalboard expects shape (num_channels, num_samples)
            # Ensure input_to_board matches this if it's not already
            if input_to_board.ndim == 1:
                input_to_board = input_to_board[np.newaxis, :] # Reshape mono to (1, num_samples)


            effected = board(input_to_board, sr)

            # Saving enhanced audio, overwriting the original file
            # Ensure the number of channels matches the original or desired output format
            num_channels_out = effected.shape[0]
            with AudioFile(file_path, 'w', sr, num_channels_out) as f:
                f.write(effected)

            print(f"Successfully enhanced and overwrote {file_path}")

        except Exception as e:
            print(f"An error occurred while processing {file_path}: {e}")
