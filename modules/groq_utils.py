import json
import time
import os

class GroqUtils():
    def __init__(self, api_key, text_model_whitelist=["llama-3.3-70b-versatile", "llama3-70b-8192", "llama3-8b-8192", "llama-3.1-8b-instant"]):
        self.api_key = api_key
        self.text_model_whitelist = text_model_whitelist
        self.current_model_id = 0
        self.history_file = "model_history.json"
        self._load_history()
        self.update_current_model_id()


    def _load_history(self):
        self.model_history = {}
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r') as f:
                self.model_history = json.load(f)

        for model in self.text_model_whitelist:
            if model not in self.model_history or not isinstance(self.model_history[model], dict):
                self.model_history[model] = {"timestamp": 0, "flagged": False}
            elif not all(k in self.model_history[model] for k in ["timestamp", "flagged"]):
                self.model_history[model] = {"timestamp": 0, "flagged": False}

    def _save_history(self):
        with open(self.history_file, 'w') as f:
            json.dump(self.model_history, f)
    
    def get_best_model(self):
        while True:
            current_model = self.text_model_whitelist[self.current_model_id]
            current_time = time.time()
            
            # Ensure model data exists and is in the correct format
            if current_model not in self.model_history or not isinstance(self.model_history[current_model], dict):
                self.model_history[current_model] = {"timestamp": 0, "flagged": False}
            
            # Check if model is in history and unflag it if the timeout period has passed
            if self.model_history[current_model].get("flagged", True):
                if current_time - self.model_history[current_model].get("timestamp", 0) >= 600:  # 10 minutes passed
                    self.model_history[current_model]["flagged"] = False
                    self._save_history()

            # Return current model if it's not flagged or not in history
            if not self.model_history[current_model].get("flagged", False):
                return current_model
            # if self.model_history[current_model]["flagged"]:
            #     return current_model
            
            self.update_current_model_id()
            # Check if all models are flagged and still within timeout period
            all_flagged = all(model_data["flagged"] and current_time - model_data["timestamp"] < 600 
                             for model_data in self.model_history.values())
            if all_flagged:
                time.sleep(120)  # Wait 2 minutes if all models are timed out
            else:
                # Try next model
                self.current_model_id = (self.current_model_id + 1) % len(self.text_model_whitelist)
                
    def update_current_model_id(self):
        current_model = self.text_model_whitelist[self.current_model_id]
        
        # Check if model exists in history and create structure if needed
        if current_model not in self.model_history:
            self.model_history[current_model] = {"timestamp": 0, "flagged": False}
        
        current_time = time.time()
        # Only update timestamp and flag if more than 10 minutes passed or it was not flagged
        if (current_time - self.model_history[current_model]["timestamp"] >= 600) or not self.model_history[current_model]["flagged"]:
            self.model_history[current_model]["timestamp"] = current_time
            self.model_history[current_model]["flagged"] = True
            self._save_history()
        else:
            # Move to next model if current one is flagged and less than 10 minutes passed
            self.current_model_id = (self.current_model_id + 1) % len(self.text_model_whitelist)
