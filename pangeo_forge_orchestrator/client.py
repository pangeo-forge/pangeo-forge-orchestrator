from dataclasses import dataclass

# mypy says stubs not installed but they are... hmm...
import requests  # type: ignore

from .models import HeroCreate


@dataclass
class Client:

    base_url: str

    def create_hero(self, hero: HeroCreate):
        """
        """
        response = requests.post(f"{self.base_url}/heroes/", json=hero.dict())
        return response
