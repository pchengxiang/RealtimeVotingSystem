# main.py
from fastapi import FastAPI, Query, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from prisma import Prisma
import requests
from contextlib import asynccontextmanager
from google.oauth2.service_account import Credentials
import gspread
import asyncio

# 用剛剛下載的 JSON 金鑰
creds = Credentials.from_service_account_file(
    "voting-system-469011-33eda3d5fc7c.json",  # 金鑰路徑
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)

gc = gspread.authorize(creds)
sheet = gc.open_by_key("1WcjnFN_uOOHVs-tc5ZDFNxKDpv1E32MTeSmemLS-iGw").sheet1


db = Prisma()


async def update_topics_periodically():
    global topics_cache
    while True:
        try:
            topics_cache = sheet.get_all_records()
        except Exception as e:
            print("更新題目時發生錯誤:", e)
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 啟動時連線
    await db.connect()
    asyncio.create_task(update_topics_periodically())
    yield
    # 關閉時斷線
    await db.disconnect()

app = FastAPI(lifespan=lifespan)


# 允許前端跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 實際上線要改成你的前端網址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 假資料：選項與票數
votes = {
    "coffee": 0,
    "tea": 0
}

voted_ips = set()


class VoteRequest(BaseModel):
    option: str
    topic_id: str


@app.post("/vote")
async def vote(data: VoteRequest, request: Request):
    client_ip = request.client.host

    option = data.option.lower()
    vote = {
        "option": data.option,
        "topic_id": data.topic_id,
        "ip": client_ip
    }
    existing = await db.vote.find_unique(where={"ip_topic_id": {"ip": client_ip, "topic_id": data.topic_id}})
    if existing:
        return {"error": "Already voted", "ip": client_ip}
    await db.vote.create(
        data=vote
    )
    return {"message": "Vote counted", "current": votes}


@app.get("/has_vote/{topic_id}")
async def hasVote(topic_id: str, request: Request):
    client_ip = request.client.host
    return await db.vote.find_unique(where={"ip_topic_id": {"ip": client_ip, "topic_id": topic_id}})


@app.get("/results/{topic_id}")
async def result(vote1: str = Query("咖啡"), vote2: str = Query("茶")):
    votes = {
        vote1: await db.vote.count(where={"option": vote1}),
        vote2: await db.vote.count(where={"option": vote2})
    }

    return votes


@app.get("/topics")
async def topics():
    return topics_cache


@app.delete("/vote/{topic_id}")
async def deleteVote(topic_id: str, request: Request):
    client_ip = request.client.host
    await db.vote.delete(where={"ip_topic_id": {"ip": client_ip, "topic_id": topic_id}})
