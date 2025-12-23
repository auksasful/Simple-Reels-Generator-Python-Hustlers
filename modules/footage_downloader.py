import random
import uuid
from modules.base_generator import BaseGenerator
import os
from urllib.parse import urlparse
import requests

class FootageDownloader(BaseGenerator):
    def __init__(self, project_folder, api_key):
        # Call the constructor of the base class
        super().__init__(project_folder)
        self.api_key = api_key
        self.results_folder = 'results'
        self.images_folder = self.downloaded_images
        self.videos_folder = self.downloaded_videos

    def read_script_videos_json(self):
        return self.read_json(self.script_videos_file_path)
    
    def read_image_paths_json(self):
        return self.read_json(self.image_paths_file_path)
    
    def update_image_path(self, video_id, scene, image_path, google_image_path):
        data = self.read_image_paths_json()
        for video in data:
            if video["video"] == video_id:
                for scene_data in video["scenes"]:
                    if scene_data["scene"] == scene:
                        scene_data["image_path"] = image_path
                        scene_data["google_image_path"] = google_image_path
                        break
                break
        self.write_json(self.image_paths_file_path, data)

    def execute(self, query, mode='video', pages=1, per_page=10, orientation=None,
                            photo_quality='original', video_quality='original'):
        pexels_file_path = ''
        google_file_path = ''
        page = random.randint(1, pages)
        per_page = 1
        # for page in range(1, pages + 1):
        if mode == 'photo':
            results = self.search_photos(query, page, per_page, orientation)
            folder_path = self.images_folder
        elif mode == 'video':
            results = self.search_videos(query, page, per_page, orientation)
            folder_path = self.videos_folder
        else:
            print(f"Invalid mode: {mode}")
            return

        if results:
            for item in results.get(mode + 's', []):
                if mode == 'photo':
                    download_url = self._choose_image_quality(item, photo_quality)
                else:
                    download_url = self._choose_video_quality(item, video_quality)
                if download_url:
                    return self._download_file(download_url, folder_path)

    @staticmethod
    def _choose_image_quality(item, quality):
        if quality in item["src"]:
            return item["src"][quality]
        else:
            print(f"Chosen image quality '{quality}' not available. Downloading original.")
            return item["src"]["original"]

    @staticmethod
    def _choose_video_quality(item, quality):
        if quality:
            if quality == 'original':
                return item['video_files'][0]['link']
            for video in item['video_files']:
                if video['quality'] == quality:
                    return video['link']
            print(f"Chosen video quality '{quality}' not available. Downloading default.")
        return item['video_files'][0]['link']

    def search_photos(self, query, page=1, per_page=10, orientation=None):
        endpoint = 'https://api.pexels.com/v1/search'
        params = {'query': query, 'page': page, 'per_page': per_page, 'orientation': orientation}
        return self._make_request(endpoint, params)

    def search_videos(self, query, page=1, per_page=10, orientation=None):
        endpoint = 'https://api.pexels.com/videos/search'
        params = {'query': query, 'page': page, 'per_page': per_page, 'orientation': orientation}
        return self._make_request(endpoint, params)

    def _make_request(self, endpoint, params):
        headers = {'Authorization': self.api_key}
        response = requests.get(endpoint, params=params, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Request failed with status code {response.status_code}")
            return None

    @staticmethod
    def _download_file(url, folder_path):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()

            # Extract the filename from the URL using urlparse
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)

            # Save the file in the specified folder
            file_path = os.path.join(folder_path, str(uuid.uuid4()) + filename)
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)

            print(f'File downloaded and saved: {file_path}')
        except requests.exceptions.RequestException as e:
            print(f'Error downloading file: {e}')

        return file_path