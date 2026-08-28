from importlib.resources import files


class PromptCatalog:
    def load(self, name: str) -> str:
        if not name or ".." in name or name.startswith(("/", "\\")):
            raise ValueError("Invalid prompt name.")
        resource = files("rennew.prompts").joinpath("templates", f"{name}.md")
        if not resource.is_file():
            raise KeyError(name)
        return resource.read_text(encoding="utf-8").strip()
