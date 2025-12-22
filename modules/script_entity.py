from typing_extensions import TypedDict

class Scene(TypedDict):
    What_Speaker_Says_In_First_Person: str
    Visuals: str

class Videos(TypedDict):
    Video: int
    Scenes: list[Scene]