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
from azure.storage.blob import BlobServiceClient, ContentSettings

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

AZURE_CONNECTION_STRING = Config.AZURE_CONNECTION_STRING
AZURE_CONTAINER_NAME = Config.AZURE_CONTAINER_NAME

if AZURE_CONNECTION_STRING:
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
else:
    print("WARNING: AZURE_CONNECTION_STRING not found in .env. Cloud uploads will fail.")
    blob_service_client = None

# --- Helper Functions ---

def upload_to_azure(local_file_path, blob_name):
    """Uploads a local file to Azure Blob Storage and returns the public URL."""
    if not blob_service_client:
        return None
    
    try:
        blob_client = blob_service_client.get_blob_client(container=AZURE_CONTAINER_NAME, blob=blob_name)
        
        # Determine content type
        content_type = 'video/mp4' if blob_name.endswith('.mp4') else 'application/octet-stream'
        
        with open(local_file_path, "rb") as data:
            blob_client.upload_blob(
                data, 
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type)
            )
        return blob_client.url
    except Exception as e:
        print(f"Azure Upload Error: {e}")
        return None


def download_file(url, folder):
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

def get_next_project_name(base_name="manual_project"):
    if not os.path.exists(os.path.join(PROJECTS_FOLDER, base_name)):
        return base_name
    counter = 1
    while True:
        new_name = f"{base_name}_{counter}"
        if not os.path.exists(os.path.join(PROJECTS_FOLDER, new_name)):
            return new_name
        counter += 1

def clean_text_for_folder(text):
    import re
    return re.sub(r'[^\w\s]', '', text).strip()

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
    
def generate_fish_audio(text, output_path, ref_id="b85455e9d73e492d95c554176a8913df"):
    """Generates audio using Fish Audio SDK with the Kiova British voice."""
    try:
        # Your specific API Key
        session = Session(Config.FISH_AUDIO_API_KEY) 
        
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

@app.route('/reset')
def reset_project():
    """Clears session and redirects to home to start fresh."""
    session.clear()
    return redirect(url_for('step1'))

@app.route('/', methods=['GET', 'POST'])
def step1():
    if request.method == 'GET':
        session.pop('scripts', None)
        session.pop('generated_videos', None) # Clear previous results
    if request.method == 'POST':
        session['scripts'] = {"video_1": [{"script": "", "media_type": "url", "media_source": ""}]}
        return redirect(url_for('step2'))
    return render_template('step1.html')

@app.route('/step2', methods=['GET', 'POST'])
def step2():
    if 'scripts' not in session: return redirect(url_for('step1'))

    # 1. Grab existing data to use as fallback
    previous_scripts = session.get('scripts', {})

    if request.method == 'POST':
        scripts_data = {}
        video_keys = sorted(list(set(k.split('_script')[0] for k in request.form if '_script' in k)))
        has_content = False

        for key in video_keys:
            scripts = request.form.getlist(f'{key}_script')
            media_types = request.form.getlist(f'{key}_media_type')
            media_urls = request.form.getlist(f'{key}_media_url')
            
            # Get the list of previous scenes for this specific video (if any)
            previous_video_scenes = previous_scripts.get(key, [])

            video_scenes = []
            for index, script_text in enumerate(scripts):
                if script_text.strip():
                    media_type = media_types[index]
                    final_source = ""
                    
                    if media_type == 'url':
                        final_source = media_urls[index]
                    elif media_type == 'file':
                        # Check for NEW file upload
                        file_input_name = f"{key}_file_{index}"
                        file = request.files.get(file_input_name)
                        
                        if file and file.filename != '':
                            # CASE A: User uploaded a new file -> Save it
                            filename = secure_filename(f"{key}_scene_{index}_{file.filename}")
                            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                            file.save(file_path)
                            final_source = file_path
                        else:
                            # CASE B: No new file -> Try to keep the OLD file path
                            # We check if this scene index existed in the previous session
                            if index < len(previous_video_scenes):
                                old_scene = previous_video_scenes[index]
                                # Only keep it if the previous type was also 'file'
                                if old_scene.get('media_type') == 'file':
                                    final_source = old_scene.get('media_source', '')

                    video_scenes.append({
                        "scene": str(index + 1),
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
        
        # Clear previous video results because the script has changed
        session.pop('generated_videos', None) 
        
        return redirect(url_for('step3'))

    return render_template('step2.html', scripts=session.get('scripts', {}))

@app.route('/step3', methods=['GET', 'POST'])
def step3():
    if 'scripts' not in session: return redirect(url_for('step2'))

    # Load previously saved settings (if any)
    saved_settings = session.get('step3_settings', {})

    # If we already generated videos in this session, show results
    if request.method == 'GET' and 'generated_videos' in session:
        return render_template('step3.html', 
                             scripts=session.get('scripts', {}), 
                             generated_videos=session['generated_videos'],
                             settings=saved_settings) # Pass settings

    if request.method == 'POST':
        voice_option = request.form.get('voiceover')
        
        # Capture custom Ref ID, default to Kiova if empty
        custom_ref_id = request.form.get('fish_ref_id')
        if not custom_ref_id or not custom_ref_id.strip():
            custom_ref_id = "b85455e9d73e492d95c554176a8913df"

        # --- FIX: Save these settings to session ---
        session['step3_settings'] = {
            'voiceover': voice_option,
            'fish_ref_id': custom_ref_id
        }
        saved_settings = session['step3_settings']
        # -------------------------------------------

        # 1. Project Setup
        current_project_name = get_next_project_name()
        current_project_path = os.path.join(PROJECTS_FOLDER, current_project_name)
        
        gen_video_dir = os.path.join(current_project_path, 'generated_video')
        gen_images_dir = os.path.join(current_project_path, 'generated_images')
        os.makedirs(gen_video_dir, exist_ok=True)
        os.makedirs(gen_images_dir, exist_ok=True)

        print(f"Generating into folder: {current_project_name}")

        # Utils
        pollinations_utils = PollinationsUtils(Config.POLLINATIONS_API_KEY if hasattr(Config, 'POLLINATIONS_API_KEY') else None)
        vg = VideoGenerator(current_project_name)
        bg_gen = BackgroundAudioGenerator(current_project_name, bg_music_db=-25)

        azure_links = [] 

        # 2. Iterate Videos
        for vid_key, scenes in session['scripts'].items():
            vid_id = vid_key.split('_')[1] 
            
            # --- A. Handle Specific Music Upload ---
            music_file_input_name = f"bg_music_{vid_key}"
            music_file = request.files.get(music_file_input_name)
            
            specific_music_path = None
            if music_file and music_file.filename != '':
                music_folder = os.path.join(current_project_path, 'data', 'bg_music')
                os.makedirs(music_folder, exist_ok=True)
                safe_name = secure_filename(f"{vid_key}_{music_file.filename}")
                specific_music_path = os.path.join(music_folder, safe_name)
                music_file.save(specific_music_path)

            # --- B. Prepare Video Generation Data ---
            video_dict = {'video': vid_id, 'scenes': []}
            media_paths_list = []

            for scene in scenes:
                scene_id = scene['scene']
                clean_scene_id = clean_text_for_folder(scene_id)
                scene_folder = os.path.join(gen_images_dir, str(vid_id), clean_scene_id)
                os.makedirs(scene_folder, exist_ok=True)

                # Voiceover Logic
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
                         from gtts import gTTS
                         tts = gTTS(text=scene['script'], lang='en', slow=False)
                         tts.save(vo_path)
                elif voice_option == 'FishAudio':
                    # USE SAVED ID
                    if not generate_fish_audio(scene['script'], vo_path, ref_id=custom_ref_id):
                         from gtts import gTTS
                         tts = gTTS(text=scene['script'], lang='en', slow=False)
                         tts.save(vo_path)
                else:
                    from gtts import gTTS
                    tts = gTTS(text=scene['script'], lang='en', slow=False)
                    tts.save(vo_path)

                # Media Logic
                final_media_path = ""
                if scene['media_type'] == 'url':
                    final_media_path = download_file(scene['media_source'], scene_folder)
                else:
                    source_path = scene['media_source']
                    if os.path.exists(source_path):
                        ext = os.path.splitext(source_path)[1]
                        dest_path = os.path.join(scene_folder, f"media{ext}")
                        shutil.copy(source_path, dest_path)
                        final_media_path = dest_path

                video_dict['scenes'].append({'scene': scene_id, 'text': scene['script'], 'visuals': 'manual'})
                media_paths_list.append({'scene': scene_id, 'image_path': final_media_path, 'google_image_path': ''})

            # --- C. Generate Video & Apply Music ---
            try:
                raw_video_path = vg.execute(video_dict, media_paths_list)
                final_output_path = raw_video_path

                if specific_music_path and os.path.exists(raw_video_path):
                    music_video_path = bg_gen.execute(raw_video_path, specific_audio_path=specific_music_path)
                    if music_video_path:
                        final_output_path = music_video_path

                if final_output_path and os.path.exists(final_output_path):
                    filename = os.path.basename(final_output_path)
                    blob_name = f"{current_project_name}/{vid_key}_{filename}"
                    cloud_url = upload_to_azure(final_output_path, blob_name)
                    azure_links.append(cloud_url if cloud_url else f"Upload Failed: {final_output_path}")

            except Exception as e:
                print(f"Gen Error {vid_key}: {e}")
                continue

        session['generated_videos'] = azure_links
        flash(f"Generation Complete! Created {len(azure_links)} videos.", "success")

        # Pass settings back to template
        return render_template('step3.html', 
                             scripts=session.get('scripts', {}), 
                             generated_videos=azure_links,
                             settings=saved_settings)

    # GET Request (First load)
    return render_template('step3.html', 
                         scripts=session.get('scripts', {}), 
                         settings=saved_settings)
    
if __name__ == '__main__':
    # Ensure fonts folder exists for VideoGenerator (TextClip)
    if not os.path.exists('fonts'):
        os.makedirs('fonts')
        print("WARNING: Please put 'ARIALBD.TTF' or 'Candara-Bold.ttf' in the /fonts folder, or update VideoGenerator path.")
        
    app.run(debug=True)