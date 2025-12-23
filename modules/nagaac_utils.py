import sqlite3
import requests

class NagaACUtils():
    def __init__(self, api_key, db_name="naga_ac.db", text_model_whitelist=["default-gemini-1.5-pro", "default-gpt-3.5-turbo"], image_model_whitelist = ["sdxl", "kandinsky-3.1"], voice_model_whitelist = ['default-eleven-monolingual-v1', 'default-eleven-turbo-v2', 'default-eleven-multilingual-v1', 'default-eleven-multilingual-v2'], api_url="https://api.naga.ac/v1"):
        self.api_key = api_key
        self.db_name = db_name
        self.api_url = api_url
        self.init_create_db()
        self.text_model_whitelist = text_model_whitelist
        self.image_model_whitelist = image_model_whitelist
        self.voice_model_whitelist = voice_model_whitelist
        self.current_model_id = 0
        # self.update_db_limits()


    def init_create_db(self):
        # Connect to SQLite database (or create it if it doesn't exist)
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Create table if it doesn't exist
        cursor.execute('''CREATE TABLE IF NOT EXISTS naga_ac_limits (
            id TEXT PRIMARY KEY,
            perminute INTEGER,
            perday INTEGER
        )''')

        # Create table if it doesn't exist
        cursor.execute('''CREATE TABLE IF NOT EXISTS api_usage (
            model_id TEXT,
            exceeded BOOLEAN DEFAULT 0,
            creationdate TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # Commit changes and close the connection
        conn.commit()
        conn.close()

    def update_db_limits(self):
        # Connect to SQLite database (or create it if it doesn't exist)
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        #drop table if exists
        cursor.execute('''DROP TABLE IF EXISTS naga_ac_limits''')

        #drop api_usage
        # cursor.execute('''DROP TABLE IF EXISTS api_usage''')

        # Create table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS naga_ac_limits (
            id TEXT PRIMARY KEY,
            perminute INTEGER,
            perday INTEGER
        )
        ''')


        # Create table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_usage (
            model_id TEXT,
            exceeded BOOLEAN DEFAULT 0,
            creationdate TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        data = self.get_limiters_json()

        # Insert or update data
        for item in data["data"]:
            if item['id'] in self.text_model_whitelist or item['id'] in self.image_model_whitelist or item['id'] in self.voice_model_whitelist:
                # First, try to update the existing record
                cursor.execute('''
                    UPDATE naga_ac_limits
                    SET perminute = ?, perday = ?
                    WHERE id = ?;
                ''', (int(item["data"][0][0]), int(item["data"][1][0]), str(item['id'])))

                # Then, insert the record if it does not exist
                cursor.execute('''
                    INSERT OR IGNORE INTO naga_ac_limits (id, perminute, perday)
                    VALUES (?, ?, ?);
                ''', (str(item['id']), int(item["data"][0][0]), int(item["data"][1][0])))


        # Commit changes and close the connection
        conn.commit()
        conn.close()

    def update_api_usage(self, current_model_id, exceeded=False, voice_model=False):
        # Connect to SQLite database (or create it if it doesn't exist)
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Create table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_usage (
            model_id TEXT,
            exceeded BOOLEAN DEFAULT 0,
            creationdate TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        if voice_model:
            # get the amount of entries for the current model during the last minute
            cursor.execute('''
                SELECT COUNT(*) FROM api_usage
                WHERE model_id = ?;
            ''', (str(current_model_id),))
            count = cursor.fetchone()[0]
            if count >= 2:
                exceeded = True

            #create adjusted voice_model_whitelist: each value should not have 'default-' prefix
            voice_model_whitelist_new = [model.replace('default-', '') for model in self.voice_model_whitelist]
            
            # check if all the models from voice_model_whitelist have exceeded the limits
            exceeded_models_count = 0
            for model_id in voice_model_whitelist_new:
                cursor.execute('''
                    SELECT COUNT(*) FROM api_usage
                    WHERE model_id = ?;
                ''', (model_id,))
                count = cursor.fetchone()[0]
                if count >= 2:
                    exceeded_models_count += 1
            
            # if all exceeded, delete all entries in the whitelist
            if len(voice_model_whitelist_new) == exceeded_models_count:
                for model_id in voice_model_whitelist_new:
                    cursor.execute('''
                        DELETE FROM api_usage
                        WHERE model_id = ?;
                    ''', (model_id,))

        # Insert new entry with current_model_id
        cursor.execute('''
            INSERT INTO api_usage (model_id, exceeded)
            VALUES (?, ?);
        ''', (str(current_model_id), int(exceeded)))

        # Delete entries older than 1 minute
        cursor.execute('''
            DELETE FROM api_usage
            WHERE creationdate <= datetime('now','-1 minute');
        ''')

        # Commit changes and close the connection
        conn.commit()
        conn.close()

    def get_best_model(self, image_model=False, voice_model=False):
        if image_model:
            model_whitelist = self.image_model_whitelist
        elif voice_model:
            model_whitelist = self.voice_model_whitelist
        else:
            model_whitelist = self.text_model_whitelist

        self.current_model_id += 1
        if self.current_model_id >= len(model_whitelist):
            self.current_model_id = 0

        model_whitelist_new = [model.replace('default-', '') for model in model_whitelist]
        
        return model_whitelist_new[self.current_model_id]


        # Connect to SQLite database (or create it if it doesn't exist)
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        # print('connected to db')
        # Create table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_usage (
            model_id TEXT,
            exceeded BOOLEAN DEFAULT 0,
            creationdate TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Get all models from naga_ac_limits table sorted by perday in ascending order
        cursor.execute('''
            SELECT * FROM naga_ac_limits
            ORDER BY perday ASC;
        ''')
        models = cursor.fetchall()
        # print('fetched models')

        # Iterate over the models
        for model in models:
            model_id, perminute, perday = model
            if image_model:
                model_whitelist = self.image_model_whitelist
            elif voice_model:
                model_whitelist = self.voice_model_whitelist
            else:
                model_whitelist = self.text_model_whitelist
            if model_id in model_whitelist:
                cursor.execute('''
                    SELECT COUNT(*) FROM api_usage
                    WHERE model_id = ? AND exceeded > 0;
                ''', (self.get_model_by_limiter(model_id),))

                # print('checking exceeded', model_id)
                count = cursor.fetchone()[0]
                if count > 0:
                    continue

                # If the model has not exceeded the limits, return its id
                return self.get_model_by_limiter(model_id)

        # If all models have exceeded the limits, return None
        return None


    def get_model_by_limiter(self, limiter):
        data = self.get_models_json()

        # Insert or update data
        for item in data["data"]:
            if item["object"] == "model":
                if item['limiter'] == limiter:
                    return item['id']
                
    def get_image_model_max_images_count(self, model_id):
        data = self.get_models_json()

        # Insert or update data
        for item in data["data"]:
            if item["object"] == "model":
                if item['id'] == model_id:
                    return item['max_images']


    def get_limiters_json(self):
        api_path = self.api_url + "/limits"
        # Make the HTTP GET request
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        response = requests.get(api_path, headers=headers)
        return response.json()
    
    def get_models_json(self):
        api_path = self.api_url + "/models"
        # Make the HTTP GET request
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        response = requests.get(api_path, headers=headers)
        return response.json()
