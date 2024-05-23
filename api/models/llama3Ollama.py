from langchain_core.prompts import ChatPromptTemplate

import logging
import re

from langchain_community.chat_models import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from api.common import BaseQuestion, BaseAnswer

logger = logging.getLogger(__name__)





class Llama3Client:

    def __init__(self,ollama_base_url:str):
        # 连接本地 llama3 模型，则 不需要设置 base_url
        self.model = ChatOllama(model="llama3",base_url=ollama_base_url)


    def start_chat(self) -> ChatOllama:
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
    def get_chat_response(chat:ChatOllama, prompt: str,question: str) -> str:
        text_response = []
        
        prompt = ChatPromptTemplate.from_messages([("system", prompt),("human", "{user_input}"),])
        
        chain = prompt | chat | StrOutputParser()
        for chunk in chain.stream({"user_input": question}):
            text_response.append(chunk)
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


