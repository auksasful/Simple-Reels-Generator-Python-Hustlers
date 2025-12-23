# modules/background_audio_generator.py

import os
import random
import math
import time # For unique temp audio filenames
from moviepy.editor import (VideoFileClip, AudioFileClip,
                            concatenate_audioclips, CompositeAudioClip)
from modules.base_generator import BaseGenerator # Assuming this path is correct
# from config import Config # Only if BackgroundAudioGenerator needs specific configs

class BackgroundAudioGenerator(BaseGenerator):
    def __init__(self, project_folder, bg_music_db=-30):
        """
        Initializes the BackgroundAudioGenerator.

        Args:
            project_folder (str): The root folder for the project.
            bg_music_directory (str): Directory containing background audio files.
                                      Can be an absolute path or relative to project_folder.
            bg_music_db (float): Desired volume level for background music in dB.
        """
        super().__init__(project_folder)
        self.bg_music_db = bg_music_db

        # Resolve bg_music_directory path
        # if not os.path.isabs(bg_music_directory):
        #     self.bg_music_directory = os.path.join(self.project_folder, bg_music_directory)
        # else:
        #     self.bg_music_directory = bg_music_directory

        if not os.path.isdir(self.bg_music_directory):
            # Log a warning or raise an error if the directory doesn't exist
            # For now, let's print a warning. You might want to raise an error
            # if this directory is critical for operation.
            print(f"Warning: Background music directory not found: {self.bg_music_directory}")
            # Or, you could create it:
            # os.makedirs(self.bg_music_directory, exist_ok=True)
            # print(f"Info: Created background music directory: {self.bg_music_directory}")

    
    def get_generated_videos(self):
        # the structure of the generated videos is:
        # self.generated_video/{video_id}/{scene}/final_video.mp4
        # so we need to put the paths to a list and return it
        generated_videos = []
        # only walk through the first level of the generated_video folder
        for video_id in os.listdir(self.generated_video):
            video_path = os.path.join(self.generated_video, video_id)
            if os.path.isdir(video_path):
                for scene in os.listdir(video_path):
                    final_video_path = os.path.join(video_path, "final_video.mp4")
                    if os.path.isfile(final_video_path):
                        generated_videos.append(final_video_path)
                    # if os.path.isdir(scene_path):
                    #     final_video_path = os.path.join(scene_path, "final_video.mp4")
                    #     if os.path.isfile(final_video_path):
                    #         generated_videos.append(final_video_path)
        
        return generated_videos
        

    def _get_random_audio_file(self):
        """
        Gets a random audio file from the specified background music directory.
        Internal helper method.
        """
        audio_extensions = ('.mp3', '.wav', '.aac', '.ogg', '.flac', '.m4a')
        try:
            if not os.path.isdir(self.bg_music_directory):
                print(f"Error: Background music directory does not exist: {self.bg_music_directory}")
                return None

            audio_files = [f for f in os.listdir(self.bg_music_directory)
                           if f.lower().endswith(audio_extensions)]
            if not audio_files:
                print(f"Error: No audio files found in directory: {self.bg_music_directory}")
                return None
            chosen_file = random.choice(audio_files)
            full_path = os.path.join(self.bg_music_directory, chosen_file)
            print(f"Selected background audio file: {full_path}")
            return full_path
        except FileNotFoundError: # Should be caught by isdir check, but good practice
            print(f"Error: Background music directory not found (should not happen): {self.bg_music_directory}")
            return None
        except Exception as e:
            print(f"Error accessing background music directory {self.bg_music_directory}: {e}")
            return None

    def execute(self, input_video_path, output_suffix="_with_bg_music"):
        """
        Adds background music to an existing video file.

        The output file will be saved in the same directory as the input_video_path,
        with the specified suffix appended to its name (before the extension).

        Args:
            input_video_path (str): Path to the input video file (e.g., from VideoGenerator).
            output_suffix (str): Suffix to add to the output filename.

        Returns:
            str: Path to the newly created video file with background music, or None on failure.
        """
        print(f"BackgroundAudioGenerator: Starting process for video: {input_video_path}")

        if not os.path.isfile(input_video_path):
            print(f"Error: Input video file not found: {input_video_path}")
            return None

        # --- 1. Determine Output File Path ---
        video_dir = os.path.dirname(input_video_path)
        base_name, extension = os.path.splitext(os.path.basename(input_video_path))
        output_file_name = f"{base_name}{output_suffix}{extension}"
        output_file_path = os.path.join(video_dir, output_file_name)
        print(f"BackgroundAudioGenerator: Output will be saved as: {output_file_path}")

        # --- 2. Get Random Background Audio File ---
        bg_audio_file_path = self._get_random_audio_file()
        if not bg_audio_file_path:
            print("BackgroundAudioGenerator: Could not select a background audio file. Aborting.")
            return None

        # --- Initialize MoviePy objects to None for finally block ---
        video_clip = None
        original_audio = None
        bg_audio_clip = None
        looped_bg_audio = None
        # quiet_bg_audio = None # This is just a modified version of trimmed_bg_audio
        trimmed_bg_audio = None
        final_audio_composite = None
        final_clip = None

        try:
            # --- 3. Load Video Clip and Extract Original Audio ---
            print("BackgroundAudioGenerator: Loading video clip...")
            video_clip = VideoFileClip(input_video_path)
            print(f"Video loaded. Duration: {video_clip.duration:.2f}s")

            original_audio = video_clip.audio
            if original_audio:
                print("Original audio track found and extracted.")
                # Ensure original audio is trimmed to video duration
                original_audio = original_audio.subclip(0, min(original_audio.duration, video_clip.duration))
            else:
                print("Warning: Input video file has no original audio track.")

            # --- 4. Load Background Audio ---
            print(f"BackgroundAudioGenerator: Loading background audio clip: {bg_audio_file_path}...")
            bg_audio_clip = AudioFileClip(bg_audio_file_path)
            print(f"Background audio loaded. Duration: {bg_audio_clip.duration:.2f}s")

            if bg_audio_clip.duration <= 0:
                print(f"Error: Selected background audio file '{bg_audio_file_path}' has zero or negative duration.")
                raise ValueError("Background audio has zero duration")

            # --- 5. Loop Background Audio ---
            if video_clip.duration > bg_audio_clip.duration:
                print("BackgroundAudioGenerator: Looping background audio...")
                loops_required = math.ceil(video_clip.duration / bg_audio_clip.duration)
                audio_clips_list = [bg_audio_clip] * int(loops_required) # Ensure it's an int
                looped_bg_audio = concatenate_audioclips(audio_clips_list)
            else:
                looped_bg_audio = bg_audio_clip

            # Trim precisely to video duration
            trimmed_bg_audio = looped_bg_audio.subclip(0, video_clip.duration)

            # --- 6. Adjust Volume of Background Audio ---
            print(f"BackgroundAudioGenerator: Adjusting background audio volume to {self.bg_music_db} dB...")
            volume_factor = 10**(self.bg_music_db / 20.0)
            # Apply volumex directly to the trimmed clip
            quiet_bg_audio = trimmed_bg_audio.volumex(volume_factor)
            print(f"Background audio volume adjusted (factor: {volume_factor:.4f}).")


            # --- 7. Combine Original Audio and Background Audio ---
            print("BackgroundAudioGenerator: Combining audio tracks...")
            audio_tracks_to_combine = []
            if original_audio:
                audio_tracks_to_combine.append(original_audio)
            if quiet_bg_audio: # quiet_bg_audio will always exist if we reach here and bg_audio_clip was valid
                audio_tracks_to_combine.append(quiet_bg_audio)

            if not audio_tracks_to_combine:
                print("Warning: No audio tracks (original or background) to set. Video will be silent.")
                final_audio_composite = None # Explicitly None
            elif len(audio_tracks_to_combine) == 1:
                final_audio_composite = audio_tracks_to_combine[0]
                print("Only one audio track available. Using it directly.")
            else:
                final_audio_composite = CompositeAudioClip(audio_tracks_to_combine)
                print("Original audio and background audio composited.")

            # --- 8. Set Combined Audio to Video ---
            print("BackgroundAudioGenerator: Setting audio to video clip...")
            final_clip = video_clip.set_audio(final_audio_composite)
            # If final_audio_composite is None, video_clip.audio will be set to None,
            # effectively removing any audio, which is correct if no tracks were found.

            # --- 9. Write Output File ---
            temp_audio_filename = f"temp-audio-bg-{int(time.time())}.m4a"
            print(f"BackgroundAudioGenerator: Writing final video to: {output_file_path} (using {temp_audio_filename})")
            final_clip.write_videofile(
                output_file_path,
                codec="libx264",
                audio_codec="aac",
                temp_audiofile=temp_audio_filename,
                remove_temp=True,
                verbose=False, # Set to True if debugging write issues
                logger='bar'   # Progress bar (or None for less output)
            )
            print(f"\nVideo with added background music saved successfully as:\n{output_file_path}")
            return output_file_path

        except Exception as e:
            print(f"\n--- An Error Occurred in BackgroundAudioGenerator ---")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {e}")
            import traceback
            traceback.print_exc()
            print("------------------------------------------------------\n")
            # Attempt to delete partially created output file if error occurred
            if os.path.exists(output_file_path):
                 print(f"Attempting to remove potentially incomplete output file: {output_file_path}")
                 try:
                     os.remove(output_file_path)
                 except Exception as remove_err:
                     print(f"Warning: Could not remove file {output_file_path}: {remove_err}")
            return None

        finally:
            # --- 10. Clean up MoviePy resources ---
            print("BackgroundAudioGenerator: Closing MoviePy clips...")
            # Close clips in a way that handles if they were successfully created
            if final_clip: final_clip.close()
            # CompositeAudioClip does not need explicit closing usually,
            # but its sources do.
            # quiet_bg_audio is derived, trimmed_bg_audio is derived.
            if looped_bg_audio and looped_bg_audio != bg_audio_clip: looped_bg_audio.close()
            if bg_audio_clip: bg_audio_clip.close()
            if original_audio: original_audio.close()
            if video_clip: video_clip.close()
            print("BackgroundAudioGenerator: MoviePy cleanup finished.")