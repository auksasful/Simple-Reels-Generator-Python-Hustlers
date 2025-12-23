import os
import shutil
import webbrowser
import requests
import pyttsx3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from config import Config
import base64
from fish_audio_sdk import Session, TTSRequest

from moviepy.config import change_settings
if os.path.exists("/usr/bin/magick"):
    change_settings({"IMAGEMAGICK_BINARY": "/usr/bin/magick"})

# Import modules from your old project
# Ensure the 'modules' folder contains __init__.py and the files you provided
from modules.video_generator import VideoGenerator
from modules.pollinations_utils import PollinationsUtils
from modules.background_audio_generator import BackgroundAudioGenerator

load_dotenv()

app = Flask(__name__)
app.secret_key = 'super_secret_key'

# Setup Folders
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
UPLOAD_FOLDER = os.path.join(STATIC_FOLDER, 'uploads')
PROJECTS_FOLDER = os.path.join(BASE_DIR, 'projects')
MANUAL_PROJECT_NAME = "manual_project"
MANUAL_PROJECT_PATH = os.path.join(PROJECTS_FOLDER, MANUAL_PROJECT_NAME)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Helper Functions ---

def download_file(url, folder):
    """Downloads a file from a URL to the specified folder."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        filename = secure_filename(os.path.basename(url.split("?")[0]))
        if not filename: filename = "downloaded_media.mp4"
        file_path = os.path.join(folder, filename)
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return file_path
    except Exception as e:
        print(f"Download error: {e}")
        return None

def generate_voice_pyttsx3(text, output_path):
    """Generates offline voiceover."""
    engine = pyttsx3.init()
    engine.save_to_file(text, output_path)
    engine.runAndWait()

def generate_google_tts(text, output_path):
    """
    Generates audio using Google Cloud TTS API (Standard Free Tier).
    mimics the logic from the user's Apps Script.
    """
    # Ideally, put this key in your .env file as GOOGLE_TTS_API_KEY
    api_key = Config.GOOGLE_TTS_API_KEY
    
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    
    data = {
        "input": {"text": text},
        "voice": {
            "languageCode": "en-US", 
            "name": "en-US-Neural2-F"  # Female voice
            # Options: en-US-Standard-A (Male), en-US-Standard-F (Female), en-GB-Standard-A (Female)
        },
        "audioConfig": {
            "audioEncoding": "MP3", 
            "speakingRate": 15.0
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response_data = response.json()
        
        if 'audioContent' in response_data:
            audio_content = base64.b64decode(response_data['audioContent'])
            with open(output_path, 'wb') as f:
                f.write(audio_content)
            return True
        else:
            print(f"Google TTS Error: {response_data}")
            return False
    except Exception as e:
        print(f"Google TTS Request Failed: {e}")
        return False
    
def generate_fish_audio(text, output_path):
    """Generates audio using Fish Audio SDK with the Kiova British voice."""
    try:
        # Your specific API Key
        session = Session(Config.FISH_AUDIO_API_KEY) 
        # Your specific Voice ID
        ref_id = "b85455e9d73e492d95c554176a8913df" 
        
        # Stream the audio directly to the file
        with open(output_path, "wb") as f:
            for chunk in session.tts(TTSRequest(
                reference_id=ref_id,
                text=text
            )):
                f.write(chunk)
        
        print(f"✅ Fish Audio success: {output_path}")
        return True
    except Exception as e:
        print(f"❌ Fish Audio failed: {e}")
        return False

    
def get_next_project_name(base_name="manual_project"):
    """Finds the next available folder name (e.g., manual_project_1)."""
    if not os.path.exists(os.path.join(PROJECTS_FOLDER, base_name)):
        return base_name
    
    counter = 1
    while True:
        new_name = f"{base_name}_{counter}"
        if not os.path.exists(os.path.join(PROJECTS_FOLDER, new_name)):
            return new_name
        counter += 1

def clean_text_for_folder(text):
    """Matches the remove_symbols logic from your old generator."""
    import re
    return re.sub(r'[^\w\s]', '', text).strip()

# --- Routes ---

@app.route('/', methods=['GET', 'POST'])
def step1():
    if request.method == 'GET':
        session.pop('scripts', None)
    if request.method == 'POST':
        session['scripts'] = {"video_1": [{"script": "", "media_type": "url", "media_source": ""}]}
        return redirect(url_for('step2'))
    return render_template('step1.html')

@app.route('/step2', methods=['GET', 'POST'])
def step2():
    if 'scripts' not in session: return redirect(url_for('step1'))

    if request.method == 'POST':
        scripts_data = {}
        video_keys = sorted(list(set(k.split('_script')[0] for k in request.form if '_script' in k)))
        has_content = False

        for key in video_keys:
            scripts = request.form.getlist(f'{key}_script')
            media_types = request.form.getlist(f'{key}_media_type')
            media_urls = request.form.getlist(f'{key}_media_url')
            
            video_scenes = []
            for index, script_text in enumerate(scripts):
                if script_text.strip():
                    media_type = media_types[index]
                    final_source = ""
                    
                    if media_type == 'url':
                        final_source = media_urls[index]
                    elif media_type == 'file':
                        # Check file upload
                        file_input_name = f"{key}_file_{index}"
                        if file_input_name in request.files:
                            file = request.files[file_input_name]
                            if file and file.filename != '':
                                filename = secure_filename(f"{key}_scene_{index}_{file.filename}")
                                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                                file.save(file_path)
                                final_source = file_path
                            else:
                                # Preserve existing file if re-editing (simplified logic)
                                # For a robust app, check previous session data here
                                pass

                    video_scenes.append({
                        "scene": str(index + 1), # Use 1-based index for scene ID
                        "script": script_text.strip(),
                        "media_type": media_type,
                        "media_source": final_source
                    })

            if video_scenes:
                scripts_data[key] = video_scenes
                has_content = True
        
        if not has_content:
            flash('At least one scene is required.', 'danger')
            return redirect(url_for('step2'))

        session['scripts'] = scripts_data
        return redirect(url_for('step3'))

    return render_template('step2.html', scripts=session.get('scripts', {}))

@app.route('/step3', methods=['GET', 'POST'])
def step3():
    if 'scripts' not in session: return redirect(url_for('step2'))

    if request.method == 'POST':
        voice_option = request.form.get('voiceover')
        bg_music_file = request.files.get('bg_music')

        # 1. Auto-Increment Project Name (THIS IS CORRECT)
        current_project_name = get_next_project_name()
        current_project_path = os.path.join(PROJECTS_FOLDER, current_project_name)
        
        # Create directories for THIS specific run
        gen_video_dir = os.path.join(current_project_path, 'generated_video')
        gen_images_dir = os.path.join(current_project_path, 'generated_images')
        os.makedirs(gen_video_dir, exist_ok=True)
        os.makedirs(gen_images_dir, exist_ok=True)

        print(f"Generating into folder: {current_project_name}")

        # Prepare Utils
        pollinations_utils = PollinationsUtils(Config.POLLINATIONS_API_KEY if hasattr(Config, 'POLLINATIONS_API_KEY') else None)

        # --- DELETED THE ZOMBIE CODE HERE ---
        # (The lines that reset path to MANUAL_PROJECT_PATH were removed)
        # ------------------------------------

        # Handle Background Music Upload
        # Save to ROOT data folder so it is accessible across projects
        bg_music_path = None
        bg_music_folder = os.path.join(BASE_DIR, 'data', 'bg_music')
        
        if bg_music_file and bg_music_file.filename != '':
            os.makedirs(bg_music_folder, exist_ok=True)
            safe_audio_name = secure_filename(bg_music_file.filename)
            bg_music_path = os.path.join(bg_music_folder, safe_audio_name)
            bg_music_file.save(bg_music_path)

        generated_files = []

        # 2. Iterate Videos
        for vid_key, scenes in session['scripts'].items():
            vid_id = vid_key.split('_')[1] 
            
            # Prepare Data Structures
            video_dict = {'video': vid_id, 'scenes': []}
            media_paths_list = []

            for scene in scenes:
                scene_id = scene['scene']
                clean_scene_id = clean_text_for_folder(scene_id)
                
                # Create specific folder for this scene using the NEW path
                scene_folder = os.path.join(gen_images_dir, str(vid_id), clean_scene_id)
                os.makedirs(scene_folder, exist_ok=True)

                # A. Handle Voiceover
                vo_path = os.path.join(scene_folder, "voiceover.mp3")
                
                if voice_option == 'Pollinations':
                    pollinations_utils.generate_audio(scene['script'], scene_folder) 
                    files = [f for f in os.listdir(scene_folder) if f.startswith('audio_')]
                    if files:
                        latest_file = max([os.path.join(scene_folder, f) for f in files], key=os.path.getctime)
                        if os.path.exists(vo_path): os.remove(vo_path)
                        os.rename(latest_file, vo_path)
                elif voice_option == 'GoogleTTS':
                    if not generate_google_tts(scene['script'], vo_path):
                         # Fallback to gTTS if Google fails
                         from gtts import gTTS
                         tts = gTTS(text=scene['script'], lang='en', slow=False)
                         tts.save(vo_path)
                elif voice_option == 'FishAudio':
                    if not generate_fish_audio(scene['script'], vo_path):
                         # Fallback to gTTS if Fish fails (e.g. out of credits)
                         from gtts import gTTS
                         tts = gTTS(text=scene['script'], lang='en', slow=False)
                         tts.save(vo_path)
                else:
                    # Fallback (Offline/Pyttsx3 or gTTS)
                    from gtts import gTTS
                    tts = gTTS(text=scene['script'], lang='en', slow=False)
                    tts.save(vo_path)

                # B. Handle Visuals
                final_media_path = ""
                if scene['media_type'] == 'url':
                    final_media_path = download_file(scene['media_source'], scene_folder)
                else:
                    # It's a file path in static/uploads. Copy it to project folder
                    source_path = scene['media_source']
                    if os.path.exists(source_path):
                        ext = os.path.splitext(source_path)[1]
                        dest_path = os.path.join(scene_folder, f"media{ext}")
                        shutil.copy(source_path, dest_path)
                        final_media_path = dest_path

                # C. Build Dicts
                video_dict['scenes'].append({
                    'scene': scene_id,
                    'text': scene['script'],
                    'visuals': 'manual_input' 
                })

                media_paths_list.append({
                    'scene': scene_id,
                    'image_path': final_media_path,
                    'google_image_path': '' 
                })

            # 3. Generate Video
            try:
                # Pass the NEW project name so VG looks in the right place
                vg = VideoGenerator(current_project_name)
                final_video_path = vg.execute(video_dict, media_paths_list)
                
                if final_video_path and os.path.exists(final_video_path):
                    generated_files.append(final_video_path)
            except Exception as e:
                print(f"Video Gen Error: {e}")
                flash(f"Error generating video {vid_id}: {str(e)}", "danger")
                continue

        # 4. Add Background Audio
        if bg_music_path and generated_files:
            try:
                bg_gen = BackgroundAudioGenerator(current_project_name, bg_music_db=-25)
                # Force the generator to look in the root data folder
                bg_gen.bg_music_directory = bg_music_folder
                
                final_output_paths = []
                for vid_path in generated_files:
                    res = bg_gen.execute(vid_path)
                    if res: final_output_paths.append(res)
                
                if final_output_paths:
                    flash(f"Generated {len(final_output_paths)} videos with music!", "success")
                else:
                    flash("Generated videos (Music add failed).", "warning")

            except Exception as e:
                 print(f"BG Audio Error: {e}")
                 flash("Video generated, but background audio failed.", "warning")
        else:
             if generated_files:
                 flash(f"Successfully generated {len(generated_files)} videos!", "success")

        return render_template('step3.html', scripts=session.get('scripts', {}))

    return render_template('step3.html', scripts=session.get('scripts', {}))

if __name__ == '__main__':
    # Ensure fonts folder exists for VideoGenerator (TextClip)
    if not os.path.exists('fonts'):
        os.makedirs('fonts')
        print("WARNING: Please put 'ARIALBD.TTF' or 'Candara-Bold.ttf' in the /fonts folder, or update VideoGenerator path.")
        
    app.run(debug=True)