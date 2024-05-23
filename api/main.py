import logging
import os
import pickle
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache
from functools import wraps
from pathlib import Path
from time import sleep

from cachetools import TTLCache
from fastapi import FastAPI
from fastapi import HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from google.api_core.exceptions import GoogleAPIError


from .config import Settings, TmdbImagesConfig, load_tmdb_images_config, QuizConfig
from .models.qwen import qwenClient
from .prompt import PromptGenerator, get_personality_by_name, get_language_by_name
from .tmdb import TmdbClient
from .common import FinishQuizResponse, LimitResponse, SessionData, SessionResponse, StartQuizResponse, Stats, StatsResponse, UserAnswer

logger: logging.Logger = logging.getLogger(__name__)


@lru_cache
def _get_settings() -> Settings:
    return Settings()


@lru_cache
def _get_tmdb_images_config() -> TmdbImagesConfig:
    return load_tmdb_images_config(_get_settings())


settings: Settings = _get_settings()

tmdb_client: TmdbClient = TmdbClient(settings.tmdb_api_key, _get_tmdb_images_config())

chat_client:qwenClient = qwenClient(
    settings.qwen_model_name,
    settings.qwen_api_key
)
# chat_client: Llama3Client = Llama3Client(
#     settings.ollama_base_url
# )

# chat_client: QroqClient = QroqClient(
#     settings.groq_model_name,
#     settings.groq_api_key,
# )

# chat_client: AzureClient = AzureClient()


prompt_generator: PromptGenerator = PromptGenerator()


stats = Stats()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global stats
    path = Path(settings.stats_path)

    # load stats on startup
    if path.exists():
        with open(settings.stats_path, 'rb') as f:
            stats = pickle.load(f)
    yield

    # persist stats on shutdown
    os.makedirs(path.parent.absolute(), exist_ok=True)
    with path.open('wb') as f:
        pickle.dump(stats, f)


app: FastAPI = FastAPI(lifespan=lifespan)

# for local development
origins = [
    'http://localhost',
    'http://localhost:5173',
    'http://localhost:9091',
    'https://movie.qianniu.city',
]

# noinspection PyTypeChecker
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# cache for quiz session, ttl = max session duration in seconds
session_cache: TTLCache = TTLCache(maxsize=100, ttl=600)


def _get_page_min(popularity: int) -> int:
    return {
        3: 1,
        2: 10,
        1: 50
    }.get(popularity, 1)


def _get_page_max(popularity: int) -> int:
    return {
        3: 5,
        2: 100,
        1: 300
    }.get(popularity, 3)


call_count: int = 0
last_reset_time: datetime = datetime.now()


def rate_limit(func: callable) -> callable:
    @wraps(func)
    def wrapper(*args, **kwargs) -> callable:
        global call_count
        global last_reset_time

        # reset call count if the day has changed
        if datetime.now().date() > last_reset_time.date():
            call_count = 0
            last_reset_time = datetime.now()

        if call_count >= settings.quiz_rate_limit:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Daily limit reached')

        call_count += 1
        return func(*args, **kwargs)

    return wrapper


def retry(max_retries: int) -> callable:
    def decorator(func) -> callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            for _ in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except ValueError as e:
                    logger.error(f'Error in {func.__name__}: {e}')
                    if _ < max_retries - 1:
                        logger.warning(f'Retrying {func.__name__}...')
                        sleep(1)
                    else:
                        raise e

        return wrapper

    return decorator

@app.get("/api")
def read_root():
    return {"Hello": "World"}

@app.get('/api/movies')
def get_movies(page: int = 1, vote_avg_min: float = 5.0, vote_count_min: float = 1000.0):
    return tmdb_client.get_movies(page, vote_avg_min, vote_count_min)


@app.get('/api/movies/random')
def get_random_movie(page_min: int = 1, page_max: int = 3, vote_avg_min: float = 5.0, vote_count_min: float = 1000.0):
    return tmdb_client.get_random_movie(page_min, page_max, vote_avg_min, vote_count_min)


@app.get('/api/sessions')
def get_sessions():
    return [SessionResponse(
        quiz_id=session.quiz_id,
        question=session.question,
        movie=session.movie,
        started_at=session.started_at
    ) for session in session_cache.values()]


@app.get('/api/limit')
def get_limit():
    return LimitResponse(
        daily_limit=settings.quiz_rate_limit,
        quiz_count=call_count,
        last_reset_time=last_reset_time,
        last_reset_date=last_reset_time.date(),
        current_date=datetime.now().date()
    )


@app.get('/api/stats')
def get_stats():
    return StatsResponse(
        stats=stats,
        limit=get_limit()
    )


@app.post('/api/quiz')
@rate_limit
@retry(max_retries=settings.quiz_max_retries)
def start_quiz(quiz_config: QuizConfig = QuizConfig()):
    movie = tmdb_client.get_random_movie(
        page_min=_get_page_min(quiz_config.popularity),
        page_max=_get_page_max(quiz_config.popularity),
        vote_avg_min=quiz_config.vote_avg_min,
        vote_count_min=quiz_config.vote_count_min
    )

    if not movie:
        logger.info('could not find movie with quiz config: %s', quiz_config.dict())
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No movie found with given criteria')

    try:
        genres = [genre['name'] for genre in movie['genres']]

        prompt = prompt_generator.generate_question_prompt(
            movie_title=movie['title'],
            language=get_language_by_name(quiz_config.language),
            personality=get_personality_by_name(quiz_config.personality),
            tagline=movie['tagline'],
            overview=movie['overview'],
            genres=', '.join(genres),
            budget=movie['budget'],
            revenue=movie['revenue'],
            average_rating=movie['vote_average'],
            rating_count=movie['vote_count'],
            release_date=movie['release_date'],
            runtime=movie['runtime']
        )
        
        logger.warning('generated prompt: %s', prompt)
        
        question = """
            您的回复只能包含三行!您只能严格使用以下三行模板进行回复:
            问题: <您的问题>
            提示1: <对参与者有帮助的第一个提示>
            提示2: <更轻松获得称号的第二个提示>
        """
        # question = """
        #     Your reply must only consist of three lines! You must only reply strictly using the following template for the three lines:
        #     Question: <Your question>
        #     Hint 1: <The first hint to help the participants>
        #     Hint 2: <The second hint to get the title more easily>
            
        # """
        
        chat = chat_client.start_chat()
        
        
        chat_reply = chat_client.get_chat_response(chat,prompt,question)
        
        logger.warning('chat_reply: %s', chat_reply)
        

        logger.debug('starting quiz with generated prompt: %s', prompt)
        llama3_question = chat_client.parse_chat_question(chat_reply)

        quiz_id = str(uuid.uuid4())
        session_cache[quiz_id] = SessionData(
            quiz_id=quiz_id,
            question=llama3_question,
            movie=movie,
            started_at=datetime.now()
        )

        stats.quiz_count_total += 1
        return StartQuizResponse(quiz_id=quiz_id, question=llama3_question, movie=movie)
    except GoogleAPIError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Google API error: {e}')
    except BaseException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Internal server error: {e}')


@app.post('/api/quiz/{quiz_id}/answer')
@retry(max_retries=settings.quiz_max_retries)
def finish_quiz(quiz_id: str, user_answer: UserAnswer):
    session_data = session_cache.get(quiz_id)
    
    if not session_data:
        logger.info('session not found: %s', quiz_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Session not found')

    try:
        prompt = prompt_generator.generate_answer_prompt(answer=user_answer.answer)

        # chat = session_data.chat
        del session_cache[quiz_id]
        
        
        question = """
            参与者获得多少积分由您决定。根据这个定义，他们得到 0、1、2 或 3 分:

            0: 无分，与原标题相差甚远
            1-2: 足够接近，取决于你的决定
            3: 最好的结果，标题准确，小拼写错误没关系

            友善点，如果靠近的话就好了。以有趣且友善的方式回答。

            您的回复只能包含两行！您只能严格使用以下两行模板进行回复:
            分数: <0-3>
            答案: <您对参与者的回答>
        """
        
        # question = """
        #     It is your decision how many points the participants get. They get 0, 1, 2 or 3 points based on this definition:

        #     0: no points, to far away from original title
        #     1-2: close enough, depends on your decision
        #     3: best result, got exact title, small spelling mistakes are ok

        #     Be nice, if it is close, it is fine. Answer in a funny and nice way.

        #     Your reply must only consist of two lines! You must only reply strictly using the following template for the two lines:
        #     Points: <0-3>
        #     Answer: <your answer to the participants>
            
        # """

        logger.debug('evaluating quiz answer with generated prompt: %s', prompt)
        
        chat = chat_client.start_chat()
        
        chat_reply = chat_client.get_chat_response(chat,prompt,question)
        
        llama3_answer = chat_client.parse_chat_answer(chat_reply)

        stats.points_total += llama3_answer.points
        
        return FinishQuizResponse(
            quiz_id=quiz_id,
            question=session_data.question,
            movie=session_data.movie,
            user_answer=user_answer.answer,
            result=llama3_answer
        )
    except GoogleAPIError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Google API error: {e}')
    except BaseException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Internal server error: {e}')
