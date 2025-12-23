import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
# Add compatibility for newer Pillow versions
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS
from moviepy.editor import (
    AudioFileClip, ImageClip, VideoFileClip, 
    concatenate_videoclips, CompositeVideoClip,
    VideoClip
)
from config import Config

class VideoGenerator:
    def __init__(self, project_folder, brand_text="", width=1080, height=1920):
        self.project_folder = os.path.join('projects', project_folder)
        self.generated_images = os.path.join(self.project_folder, 'generated_images')
        self.generated_video = os.path.join(self.project_folder, 'generated_video')
        self.brand_text = brand_text
        self.width = width
        self.height = height
        self.fonts_folder = 'fonts'

    def create_pil_text_clip(self, text, fontsize, color, duration, font_path=None):
        """Creates a high-quality text image using Pillow"""
        # 1. Find a valid font
        if not font_path:
            # Common Fedora/Linux path
            font_path = "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf"
        
        try:
            font = ImageFont.truetype(font_path, fontsize)
        except OSError:
            try:
                # Try fallback
                font = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", fontsize)
            except OSError:
                font = ImageFont.load_default()

        # 2. Draw Text centered
        # Create a dummy image to measure text size
        dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        bbox = dummy_draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        # Canvas size (Video Size)
        W, H = self.width, self.height
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Position: Center Middle
        x_pos = (W - text_w) // 2
        y_pos = (H - text_h) // 2
        
        # Draw stroke (outline) and text
        stroke_width = 5
        draw.text((x_pos, y_pos), text, font=font, fill=color, stroke_width=stroke_width, stroke_fill="black")

        # 3. Convert to MoviePy
        img_np = np.array(img)
        clip = ImageClip(img_np, transparent=True).set_duration(duration)
        return clip

    def generate_linear_captions(self, text, total_duration):
        """
        Splits the original script text into word-by-word timings.
        Assumes AI speech is roughly linear based on character count.
        """
        words = text.split()
        if not words: return []
        
        # We calculate timing based on number of characters per word
        # (Longer words take longer to say)
        total_chars = sum(len(w) for w in words)
        if total_chars == 0: return []
        
        time_per_char = total_duration / total_chars
        
        captions = []
        current_time = 0.0
        
        for word in words:
            # Duration of this word
            word_duration = len(word) * time_per_char
            
            # Add a tiny buffer so words don't flash too fast on short words
            # (We steal a tiny bit of time from long words implicitly or just accept linear)
            
            captions.append({
                "text": word,
                "start": current_time,
                "end": current_time + word_duration
            })
            current_time += word_duration
            
        return captions

    def execute(self, video_dict, media_paths_dict):
        clip_paths = []

        for i, scene in enumerate(video_dict['scenes']):
            # Find media path
            media_path = ""
            for path in media_paths_dict:
                if str(scene['scene']) == str(path['scene']):
                    media_path = path['image_path'] if path['image_path'] else path['google_image_path']
                    break
            
            # Paths
            scene_dir = os.path.join(self.generated_images, str(video_dict['video']), str(scene['scene']))
            voiceover_path = os.path.join(scene_dir, "voiceover.mp3")
            video_output_path = os.path.join(self.generated_video, str(video_dict['video']), str(scene['scene']), "video.mp4")
            os.makedirs(os.path.dirname(video_output_path), exist_ok=True)

            print(f"Processing Scene {scene['scene']}...")

            if not os.path.exists(video_output_path):
                # 1. Get Audio Duration
                audio_duration = 5 # Default
                audio_clip = None
                if os.path.exists(voiceover_path):
                    audio_clip = AudioFileClip(voiceover_path)
                    audio_duration = audio_clip.duration

                # 2. Create Visual Background
                if media_path and media_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    image = Image.open(media_path)
                    image = self.scale_and_crop(image)
                    video_clip = self.zoom_in_effect(image, duration=audio_duration)
                elif media_path:
                    video_clip = self.create_video_clip(media_path, audio_duration)
                else:
                    from moviepy.editor import ColorClip
                    video_clip = ColorClip(size=(self.width, self.height), color=(0,0,0), duration=audio_duration)

                if audio_clip:
                    video_clip = video_clip.set_audio(audio_clip)

                # 3. Add Perfect Captions (No Whisper)
                text_clips = []
                if audio_duration > 0 and scene['text']:
                    # Use the ORIGINAL script text
                    captions = self.generate_linear_captions(scene['text'], audio_duration)
                    
                    for cap in captions:
                        duration = cap['end'] - cap['start']
                        txt_clip = self.create_pil_text_clip(
                            cap['text'], 
                            fontsize=110, # Large font for single words
                            color='white', 
                            duration=duration
                        )
                        txt_clip = txt_clip.set_start(cap['start']).set_position('center')
                        text_clips.append(txt_clip)

                # 4. Composite
                final_layers = [video_clip] + text_clips
                
                # Brand Text (Optional)
                if self.brand_text:
                    brand_clip = self.add_brand_text(video_clip, self.brand_text)
                    final_layers.append(brand_clip)

                final_clip = CompositeVideoClip(final_layers)
                final_clip.write_videofile(video_output_path, codec="libx264", fps=24, audio_codec="aac")
                
                final_clip.close()
                if audio_clip: audio_clip.close()
                video_clip.close()
            
            clip_paths.append(video_output_path)

        # Concatenate
        final_video_path = os.path.join(self.generated_video, str(video_dict['video']), "final_video.mp4")
        self.concatenate_video_clips(clip_paths, final_video_path)
        return final_video_path

    def add_brand_text(self, base_clip, text, fontsize=50):
        txt_clip = self.create_pil_text_clip(
            text, 
            fontsize=fontsize, 
            color='white', 
            duration=base_clip.duration
        )
        txt_clip = txt_clip.set_position(('center', 0.8), relative=True).set_opacity(0.6)
        return txt_clip

    # --- Standard Helpers ---
    def create_video_clip(self, media_path, audio_duration):
        if media_path.lower().endswith(('.mp4', '.mov', '.avi')):
            original_clip = VideoFileClip(media_path)
            original_clip = original_clip.resize(newsize=(self.width, self.height))
            if original_clip.duration < audio_duration:
                repeats = int(audio_duration / original_clip.duration) + 1
                clips = [original_clip] * repeats
                looped_clip = concatenate_videoclips(clips)
                video_clip = looped_clip.subclip(0, audio_duration)
            else:
                video_clip = original_clip.subclip(0, audio_duration)
            return video_clip
        else:
            image_clip = ImageClip(media_path, duration=audio_duration)
            image_clip = image_clip.resize(newsize=(self.width, self.height))
            return image_clip
        
    def concatenate_video_clips(self, clip_paths, final_video_path):
        video_clips = [VideoFileClip(clip_path) for clip_path in clip_paths]
        final_video = concatenate_videoclips(video_clips, method="compose")
        final_video.write_videofile(final_video_path, codec="libx264", fps=24, audio_codec="aac")
        final_video.close()
        return final_video_path
    
    def scale_and_crop(self, image):
        width = self.width
        height = self.height
        original_aspect = image.width / image.height
        target_aspect = width / height
        if original_aspect > target_aspect:
            new_width = int(target_aspect * image.height)
            left = (image.width - new_width) // 2
            right = left + new_width
            image = image.crop((left, 0, right, image.height))
        else:
            new_height = int(image.width / target_aspect)
            top = (image.height - new_height) // 2
            bottom = top + new_height
            image = image.crop((0, top, image.width, bottom))
        image = image.resize((width, height), Image.LANCZOS)
        return image

    def zoom_in_effect(self, image, duration, zoom_factor=1.2):
        w, h = image.size
        img_np = np.array(image)
        def make_frame(t):
            zoom = 1 + (zoom_factor - 1) * (t / duration)
            new_w, new_h = int(w * zoom), int(h * zoom)
            img_resized = Image.fromarray(img_np).resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - w) // 2
            top = (new_h - h) // 2
            right = left + w
            bottom = top + h
            return np.array(img_resized.crop((left, top, right, bottom)))
        return VideoClip(make_frame, duration=duration)