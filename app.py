import os
import webbrowser
from flask import Flask, render_template, request, redirect, url_for, flash, session
from dotenv import load_dotenv
import json
from modules.writer.script_writer import ScriptWriter

load_dotenv()

app = Flask(__name__)
app.secret_key = 'a_very_secure_secret_key_for_session'

@app.route('/', methods=['GET', 'POST'])
def step1():
    if request.method == 'GET':
        session.pop('scripts', None)

    if request.method == 'POST':
        if 'generate' in request.form:
            prompts = request.form.getlist('prompt')
            valid_prompts = [p.strip() for p in prompts if p.strip()]

            if not valid_prompts:
                flash('You must provide at least one prompt to generate scripts.')
                return redirect(url_for('step1'))

            generated_scripts_data = {}

            writer = ScriptWriter("project", os.getenv('POLLINATIONS_API_KEY'), os.getenv('GOOGLE_GEMINI_API_KEY'))

            for i, prompt in enumerate(valid_prompts):
                video_key = f"video_{i + 1}"
                json_string_output = writer.execute(prompt="Generate a short video script for this prompt:" + prompt)
                try:
                    # 2. Parse the JSON string
                    data = json.loads(json_string_output)
                    
                    # 3. Transform it into the structure needed for Step 2
                    scenes_list = []
                    for scene in data.get("Scenes", []):
                        scenes_list.append({
                            "script": scene.get("What_Speaker_Says_In_First_Person", ""),
                            "visuals": scene.get("Visuals", "")
                        })
                    
                    if scenes_list:
                        generated_scripts_data[video_key] = scenes_list

                except json.JSONDecodeError:
                    flash(f"Error decoding the script JSON for prompt: '{prompt}'. Please check the output format.")
                    return redirect(url_for('step1'))

            session['scripts'] = generated_scripts_data
            return redirect(url_for('step2'))

        elif 'manual' in request.form:
            # For manual entry, start with one empty script and visual field
            session['scripts'] = {"video_1": [{"script": "", "visuals": ""}]}
            return redirect(url_for('step2'))

    return render_template('step1.html')

@app.route('/step2', methods=['GET', 'POST'])
def step2():
    if 'scripts' not in session:
        return redirect(url_for('step1'))

    if request.method == 'POST':
        scripts_data = {}
        # Find unique video keys from the form (e.g., video_1, video_2)
        video_keys = sorted(list(set(k.split('_script')[0] for k in request.form if k.endswith('_script'))))
        
        has_content = False
        for key in video_keys:
            # Get the parallel lists of scripts and visuals for the current video
            scripts = request.form.getlist(f'{key}_script')
            visuals = request.form.getlist(f'{key}_visuals')
            
            video_scenes = []
            # Combine the lists into the desired structure
            for script_text, visual_text in zip(scripts, visuals):
                # Only add a scene if the script part has content
                if script_text.strip():
                    video_scenes.append({
                        "script": script_text.strip(),
                        "visuals": visual_text.strip()
                    })
            
            if video_scenes:
                scripts_data[key] = video_scenes
                has_content = True
        
        if not has_content:
            flash('You must have at least one video with one scene to proceed.')
            # To prevent data loss on failed validation, we must reconstruct the state.
            # This is complex, so we just redirect back to the GET page which uses the last valid session data.
            return redirect(url_for('step2'))

        session['scripts'] = scripts_data
        return redirect(url_for('step3'))

    return render_template('step2.html', scripts=session.get('scripts', {}))


@app.route('/step3', methods=['GET', 'POST'])
def step3():
    if 'scripts' not in session or not session['scripts']:
        return redirect(url_for('step2'))

    if request.method == 'POST':
        visuals = request.form.get('visuals')
        voiceover = request.form.get('voiceover')

        errors = False
        if 'AI' in visuals:
            if not os.getenv('POLLINATIONS_API_KEY'):
                flash('Pollinations API Key is required for AI footage and must be in your .env file.')
                errors = True
        if 'pexels' in visuals:
            if not os.getenv('PEXELS_API_KEY'):
                flash('Pexels API Key is required for Pexels footage and must be in your .env file.')
                errors = True
        if voiceover == 'Pollinations':
            if not os.getenv('POLLINATIONS_API_KEY'):
                flash('Pollinations API Key is required for Pollinations voiceover and must be in your .env file.')
                errors = True

        if not errors:
            flash('Validation successful! Your videos would be generated now.')
            print("Final Scripts:", session['scripts'])
            print("Visuals:", visuals)
            print("Voiceover:", voiceover)

        return render_template('step3.html', scripts=session.get('scripts', {}))

    return render_template('step3.html', scripts=session.get('scripts', {}))


if __name__ == '__main__':
    webbrowser.open_new('http://127.0.0.1:5000/')
    app.run(debug=True)