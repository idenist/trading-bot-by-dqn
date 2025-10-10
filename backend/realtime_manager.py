from fastapi import WebSocket
from collections import defaultdict
import asyncio

from kiwoom_python.realtime import *

class DataManager:
    _instance = None
    
    # 싱글톤 패턴 적용
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DataManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.connected_clients = defaultdict(set) # {'A': {client1, client2}, 'B': {client2}}
            self.websocket_client = None
            self.current_subscriptions = set()
            self.event_queue = asyncio.Queue()
            self.initialized = True

    async def connect_to_outer_server(self, app_key, secret_key, mock):
        self.websocket_client = WebSocket(app_key, secret_key, mock)
        await self.websocket_client.run()
        pass

    async def subscribe(self, item: str, client: WebSocket):
        self.connected_clients[item].add(client)
        # 종목 코드 등록
        if item not in self.current_subscriptions:
            self.current_subscriptions.add(item)
            await self.update_outer_server_subscriptions()

    async def unsubscribe(self, item: str, client: WebSocket):
        if client in self.connected_clients[item]:
            self.connected_clients[item].remove(client)
        # 종목 코드 해지
        if not self.connected_clients[item]:
            self.current_subscriptions.discard(item)
            await self.update_outer_server_subscriptions()

    async def distribute_data(self):
        # 외부 서버로부터 데이터를 수신하고 분배하는 코루틴
        # 데이터를 받으면 self.event_queue에 넣음
        while True:
            data = await self.websocket_client.receive_json()
            # 데이터 처리 및 큐에 넣기
            await self.event_queue.put(data)