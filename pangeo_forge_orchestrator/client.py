from dataclasses import dataclass

# mypy says stubs not installed but they are... hmm...
import requests  # type: ignore


@dataclass
class Client:

    base_url: str

    def post(self, endpoint: str, json: dict):
        """
        """
        response = requests.post(f"{self.base_url}{endpoint}", json=json)
        return response
