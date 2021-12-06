from dataclasses import dataclass

# mypy says stubs not installed but they are... hmm...
import requests  # type: ignore


@dataclass
class Client:

    base_url: str

    def post(self, endpoint: str, json: dict):
        """ """
        response = requests.post(f"{self.base_url}{endpoint}", json=json)
        return response

    def get(self, endpoint: str):
        """ """
        response = requests.get(f"{self.base_url}{endpoint}")
        return response

    def patch(self, endpoint: str, json: dict):
        """ """
        response = requests.patch(f"{self.base_url}{endpoint}", json=json)
        return response

    def delete(self, endpoint: str):
        """ """
        response = requests.delete(f"{self.base_url}{endpoint}")
        return response
