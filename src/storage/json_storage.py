import json
import os

class JSONStorage:
    def __init__(self, output_dir="output"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def save(self, data, filename):
        """Saves dictionary data to a JSON file."""
        filepath = os.path.join(self.output_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"--- Data successfully saved to {filepath} ---")
        except Exception as e:
            print(f"Error saving JSON file: {e}")
