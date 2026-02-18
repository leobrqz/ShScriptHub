import os

class ScriptManager:
    """Finds all .sh files under the project folder. Category is chosen per script in the UI."""

    def __init__(self, project_path):
        self.project_path = project_path

    def get_scripts(self):
        scripts = []
        for root, dirs, files in os.walk(self.project_path):
            for f in files:
                if f.endswith(".sh"):
                    full_path = os.path.join(root, f)
                    scripts.append({"name": f, "path": full_path})
        return scripts
