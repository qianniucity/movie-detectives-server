import logging
import re

import vertexai
from google.oauth2.service_account import Credentials
from vertexai.generative_models import GenerativeModel, ChatSession

from api.config import GENERATION_CONFIG
from api.common import BaseQuestion, BaseAnswer

logger = logging.getLogger(__name__)


class GeminiClient:

    FALLBACK_MODEL = 'gemini-1.0-pro'

    def __init__(self, project_id: str, location: str, credentials: Credentials, model: str):
        vertexai.init(project=project_id, location=location, credentials=credentials)

        logger.info('loading model: %s', model)
        logger.info('generation config: %s', GENERATION_CONFIG)
        self.model = GenerativeModel(model)
        self.fallback_model = GenerativeModel(self.FALLBACK_MODEL)

    def start_chat(self) -> ChatSession:
        # noinspection PyBroadException
        try:
            return self.model.start_chat(response_validation=False)
        except Exception as e:
            logger.warning(
                'error while using model %s, using fallback model %s, error: %s',
                self.model,
                self.FALLBACK_MODEL,
                e
            )
            return self.fallback_model.start_chat(response_validation=False)

    @staticmethod
    def get_chat_response(chat: ChatSession, prompt: str) -> str:
        text_response = []
        responses = chat.send_message(prompt, generation_config=GENERATION_CONFIG, stream=True)
        for chunk in responses:
            text_response.append(chunk.text)
        return ''.join(text_response)

    @staticmethod
    def parse_gemini_question(gemini_reply: str) -> BaseQuestion:
        result = re.findall(r'[^:]+: ([^\n]+)', gemini_reply, re.MULTILINE)
        if len(result) != 3:
            msg = f'Gemini replied with an unexpected format. Gemini reply: {gemini_reply}'
            logger.warning(msg)
            raise ValueError(msg)

        question = result[0]
        hint1 = result[1]
        hint2 = result[2]

        return BaseQuestion(question=question, hint1=hint1, hint2=hint2)

    @staticmethod
    def parse_gemini_answer(gemini_reply: str) -> BaseAnswer:
        result = re.findall(r'[^:]+: ([^\n]+)', gemini_reply, re.MULTILINE)
        if len(result) != 2:
            msg = f'Gemini replied with an unexpected format. Gemini reply: {gemini_reply}'
            logger.warning(msg)
            raise ValueError(msg)

        points = re.sub('[^0-9]', '', result[0])
        answer = result[1]

        return BaseAnswer(points=int(points), answer=answer)
