# main.py
from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from prisma import Prisma
from contextlib import asynccontextmanager

db = Prisma()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 啟動時連線
    await db.connect()
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


@app.post("/vote")
async def vote(data: VoteRequest, request: Request):
    client_ip = request.client.host

    option = data.option.lower()
    vote = {
        "option": data.option,
        "ip": client_ip
    }
    existing = await db.vote.find_unique(where={"ip": client_ip})
    if existing:
        return {"error": "Already voted", "ip": client_ip}
    if option not in votes:
        return {"error": "Invalid option"}
    await db.vote.create(
        data=vote
    )
    return {"message": "Vote counted", "current": votes}


@app.get("/has_vote")
async def hasVote(request: Request):
    client_ip = request.client.host
    return await db.vote.find_unique(where={"ip": client_ip})


@app.get("/results")
async def result():
    votes = {
        "coffee": await db.vote.count(where={"option": "coffee"}),
        "tea": await db.vote.count(where={"option": "tea"})
    }

    return votes


@app.delete("/vote")
async def deleteVote(request: Request):
    client_ip = request.client.host
    await db.vote.delete(where={"ip": client_ip})
