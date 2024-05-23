from functools import lru_cache
from langchain_community.chat_models import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from api.config import Settings
from api.models.azure import AzureClient

@lru_cache
def _get_settings() -> Settings:
    return Settings()

settings: Settings = _get_settings()

llm_client: AzureClient = AzureClient()


chat_session = ChatOllama(model="llama3")

def get_chat_response(chat:ChatOllama, prompt: str) -> str:
        template = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful AI bot. Your name is Carl,All your replies in this session, also for follow-up conversations, must be in Chinese, even if I communicate in English."),
            ("human", "{user_input}"),
        ])
        chain = template | chat | StrOutputParser()
        prompt_value = chain.invoke(prompt)
        return ''.join(prompt_value)


response = get_chat_response(
    chat_session,
    "How to say 'you are awesome' in Chinese-simplified?"
)
print(response)