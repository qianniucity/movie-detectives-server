from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

import logging
import re

from api.config import GENERATION_CONFIG
from api.common import BaseQuestion, BaseAnswer

logger = logging.getLogger(__name__)

# 使用的时候，在 mian 中设置
# settings: Settings = _get_settings()

# groq_client: GroqClient = GroqClient(
#     settings.groq_model_name,
#     settings.groq_api_key,
# )

class QroqClient:

    def __init__(self, groq_model_name: str, groq_api_key: str):
        self.model = ChatGroq(temperature=0,groq_api_key=groq_api_key, model_name=groq_model_name)
        logger.info('generation config: %s', GENERATION_CONFIG)


    def start_chat(self) -> ChatGroq:
        # noinspection PyBroadException
        try:
            return self.model
        except Exception as e:
            logger.warning(
                'error while using model %s, using fallback model %s, error: %s',
                self.model,
                e
            )

    @staticmethod
    def get_chat_response(chat:ChatGroq, prompt: str,question: str) -> str:
        text_response = []
        prompt = ChatPromptTemplate.from_messages([("system", prompt),("human", "{user_input}"),])
        
        chain = prompt | chat
        for chunk in chain.stream({"user_input": question}):
            text_response.append(chunk.content)
        return ''.join(text_response)

    @staticmethod
    def parse_chat_question(chat_reply: str) -> BaseQuestion:
        result = re.findall(r'[^:]+: ([^\n]+)', chat_reply, re.MULTILINE)
        if len(result) != 3:
            msg = f'Chat replied with an unexpected format. chat_reply: {chat_reply}'
            logger.warning(msg)
            raise ValueError(msg)

        question = result[0]
        hint1 = result[1]
        hint2 = result[2]

        return BaseQuestion(question=question, hint1=hint1, hint2=hint2)

    @staticmethod
    def parse_chat_answer(chat_reply: str) -> BaseAnswer:
        result = re.findall(r'[^:]+: ([^\n]+)', chat_reply, re.MULTILINE)
        if len(result) != 2:
            msg = f'Chat replied with an unexpected format. chat_reply: {chat_reply}'
            logger.warning(msg)
            raise ValueError(msg)

        points = re.sub('[^0-9]', '', result[0])
        answer = result[1]

        return BaseAnswer(points=int(points), answer=answer)


