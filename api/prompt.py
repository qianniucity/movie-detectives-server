from enum import StrEnum
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape
from pydantic.v1 import validate_arguments

PERSONALITY_PATH = 'personality'
LANGUAGE_PATH = 'language'


class Personality(StrEnum):
    DEFAULT = 'default_cn.jinja'
    CHRISTMAS = 'christmas_cn.jinja'
    SCIENTIST = 'scientist_cn.jinja'
    DAD = 'dad_cn.jinja'


class Language(StrEnum):
    DEFAULT = 'cn.jinja'
    GERMAN = 'de.jinja'
    CHINESE = 'en.jinja'


def get_personality_by_name(name: str) -> Personality:
    try:
        return Personality[name.upper()]
    except KeyError:
        return Personality.DEFAULT


def get_language_by_name(name: str) -> Language:
    try:
        return Language[name.upper()]
    except KeyError:
        return Language.DEFAULT


class PromptGenerator:

    def __init__(self):
        self.env = Environment(
            loader=PackageLoader('api'),
            autoescape=select_autoescape()
        )

    @validate_arguments
    def generate_question_prompt(
        self,
        movie_title: str,
        language: Language,
        personality: Personality,
        **kwargs: Any
    ) -> str:
        template = self.env.get_template('prompt_question_cn.jinja')

        # noinspection PyTypeChecker
        language = self.env.get_template(f'{LANGUAGE_PATH}/{language.value}').render()

        # noinspection PyTypeChecker
        personality = self.env.get_template(f'{PERSONALITY_PATH}/{personality.value}').render()

        return template.render(
            language=language,
            personality=personality,
            title=movie_title,
            **kwargs
        )

    def generate_answer_prompt(self, answer: str) -> str:
        template = self.env.get_template('prompt_answer_cn.jinja')
        return template.render(answer=answer)
