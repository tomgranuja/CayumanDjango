import random
from dataclasses import dataclass


@dataclass
class FakeWorkshop:
    """Helpful class to represent fake workshop data"""

    name: str
    teacher: str
    description: str


def generate_fake_workshops(n: int = 8):
    """Simple helper that returns fake workshops data based on a pool of fake info, so they can be used when no workshops are available"""

    name_pool = [
        "Algoritmos genéticos",
        "Análisis de algoritmos",
        "Inteligencia artificial",
        "Machine Learning",
        "Deep Learning",
        "Flores de Bach II",
        "Biología celular",
        "Trigonometría aplicada",
    ]
    teacher_pool = ["Salva", "Jano", "Grace", "Paula", "Carla", "Jocelyn"]
    description_pool = [
        (
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Proin ac justo venenatis, euismod diam sollicitudin, posuere sapien. "
            "Nam metus neque, gravida sit amet magna a, vestibulum lobortis elit. Nunc et nunc vitae quam cursus vestibulum."
        ),
        (
            # Harry Potter and the Sorcerer's Stone
            "Hagrid raised a gigantic fist and knocked three times on the castle door. The door swung open at once. "
            "A tall, black-haired witch in emerald-green robes stood there. She had a very stern face and Harry's first thought "
            "was that this was not someone to cross."
        ),
        (
            # Euclid's 5th postulate
            "If a straight line falling on two straight lines makes the interior angles on the same side of it taken together less than two "
            "right angles, then the two straight lines, if produced indefinitely, meet on that side on which the sum of angles is less than "
            "two right angles."
        ),
        (
            # Newton's Principia Mathematica
            "Every body perseveres in its state of being at rest or moving uniformly straight forward, except insofar as it is compelled "
            "to change its state by forces impressed."
        ),
        (
            # Godel's On Formally Undecidable Propositions of Principia Mathematica and Related Systems I
            "Any consistent formal system F within which a certain amount of elementary arithmetic can be carried out is incomplete; "
            "i.e. there are statements of the language of F which can neither be proved nor disproved in F."
        ),
    ]

    return [
        FakeWorkshop(
            name=random.choice(name_pool) or "Workshop Name",
            teacher=random.choice(teacher_pool) or "Teacher Name",
            description=random.choice(description_pool) or "Workshop Description",
        )
        for _ in range(n)
    ]
