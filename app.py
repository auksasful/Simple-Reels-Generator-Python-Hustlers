import os
import webbrowser
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'a_very_secure_secret_key_for_session'

# Configure upload folder for manual footage
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/', methods=['GET', 'POST'])
def step1():
    # Clear previous session data on load
    if request.method == 'GET':
        session.pop('scripts', None)

    if request.method == 'POST':
        # Initialize a single blank video with one blank scene
        session['scripts'] = {"video_1": [{"script": "", "media_type": "url", "media_source": ""}]}
        return redirect(url_for('step2'))

    return render_template('step1.html')

@app.route('/step2', methods=['GET', 'POST'])
def step2():
    if 'scripts' not in session:
        return redirect(url_for('step1'))

    if request.method == 'POST':
        scripts_data = {}
        # Identify unique video keys (video_1, video_2, etc.)
        video_keys = sorted(list(set(k.split('_script')[0] for k in request.form if '_script' in k)))
        
        has_content = False

        for key in video_keys:
            scripts = request.form.getlist(f'{key}_script')
            media_types = request.form.getlist(f'{key}_media_type')
            media_urls = request.form.getlist(f'{key}_media_url')
            # Files need to be handled differently (request.files)
            # Since file inputs are dynamic, we iterate by index
            
            video_scenes = []
            
            for index, script_text in enumerate(scripts):
                if script_text.strip():
                    media_type = media_types[index]
                    final_source = ""

                    # Handle URL
                    if media_type == 'url':
                        final_source = media_urls[index]
                    
                    # Handle File Upload
                    elif media_type == 'file':
                        # File inputs are named video_1_file_0, video_1_file_1, etc. (we need to enforce this naming in HTML)
                        file_input_name = f"{key}_file_{index}"
                        if file_input_name in request.files:
                            file = request.files[file_input_name]
                            if file and file.filename != '':
                                filename = secure_filename(f"{key}_scene_{index}_{file.filename}")
                                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                                file.save(file_path)
                                final_source = file_path
                                # If user didn't upload a NEW file, try to keep old one if it exists in session
                                # (Omitting complex state recovery for simplicity, assuming fresh upload for now)

                    video_scenes.append({
                        "script": script_text.strip(),
                        "media_type": media_type,
                        "media_source": final_source
                    })

            if video_scenes:
                scripts_data[key] = video_scenes
                has_content = True
        
        if not has_content:
            flash('You must have at least one video with one scene to proceed.')
            return redirect(url_for('step2'))

        session['scripts'] = scripts_data
        return redirect(url_for('step3'))

    return render_template('step2.html', scripts=session.get('scripts', {}))


@app.route('/step3', methods=['GET', 'POST'])
def step3():
    if 'scripts' not in session or not session['scripts']:
        return redirect(url_for('step2'))

    if request.method == 'POST':
        voiceover = request.form.get('voiceover')

        errors = False
        if voiceover == 'Pollinations':
            if not os.getenv('POLLINATIONS_API_KEY'):
                flash('Pollinations API Key is required for Pollinations voiceover.')
                errors = True

        if not errors:
            flash('Success! Ready to compile videos.')
            # Here you would call your ffmpeg/moviepy logic using:
            # session['scripts'] (contains script text + file paths/urls)
            # voiceover (choice)
            print("Processing Data:", session['scripts'])

        return render_template('step3.html', scripts=session.get('scripts', {}))

    return render_template('step3.html', scripts=session.get('scripts', {}))


if __name__ == '__main__':
    webbrowser.open_new('http://127.0.0.1:5000/')
    app.run(debug=True)